"""Eén ophaalronde: bronnen ophalen, posts indelen, opslaan, nieuwe bronnen zoeken."""
from __future__ import annotations

import hashlib
import logging
import threading
from datetime import timedelta

import requests

from . import (budget, classify, config, db, discovery, lexicon, nieuwezaken, onderhoud, ownposts, seeds, signals,
               snackspert, trefkans)
from .sources import apify, meta_graph, news, supermarket

log = logging.getLogger(__name__)
_run_lock = threading.Lock()

AI_BATCH = 20
AI_MAX_PER_RUN = 300
APIFY_BATCH = 10


def is_running() -> bool:
    return _run_lock.locked()


class Run:
    def __init__(self, trigger: str):
        self.trigger = trigger
        self.lines: list[dict] = []
        self.results = 0
        self.new_posts = 0
        self.cost = 0.0
        self.ai_cost = 0.0
        self.errors = 0
        self.offline = 0      # bronnen die niet konden door een netwerkfout
        with db.session() as conn:
            cur = conn.execute("INSERT INTO runs(started_at, trigger) VALUES (?, ?)",
                               (db.iso(db.now()), trigger))
            self.id = cur.lastrowid

    def note(self, msg: str, level: str = "info") -> None:
        msg = config.redact(msg)
        log.log(logging.WARNING if level == "fout" else logging.INFO, msg)
        if level == "fout":
            self.errors += 1
        self.lines.append({"t": db.iso(db.now()), "niveau": level, "tekst": msg})
        with db.session() as conn:
            conn.execute("UPDATE runs SET log = ? WHERE id = ?", (config.dumps(self.lines), self.id))

    def finish(self) -> None:
        if not self.errors and not self.offline:
            status = "klaar"
        elif self.results or self.new_posts:
            status = "deels"
        else:
            # Niets opgehaald door fouten of geen internet: over een half uur opnieuw (zie due()).
            status = "fout"
        with db.session() as conn:
            conn.execute(
                "UPDATE runs SET finished_at = ?, status = ?, results = ?, new_posts = ?, "
                "cost_usd = ?, ai_cost_usd = ?, log = ? WHERE id = ?",
                (db.iso(db.now()), status, self.results, self.new_posts, self.cost,
                 self.ai_cost, config.dumps(self.lines), self.id))


# --- opslaan ---------------------------------------------------------------

def store_posts(conn, posts: list[dict], source_id: int | None,
                demo: bool = False) -> tuple[int, int, int]:
    """Slaat posts op (of werkt cijfers bij). Geeft (nieuw, relevant, nieuw én relevant)."""
    now = db.iso(db.now())
    new = relevant = new_relevant = 0
    for p in posts:
        existing = conn.execute("SELECT id, ai_done FROM posts WHERE id = ?", (p["id"],)).fetchone()
        if existing:
            conn.execute(
                "UPDATE posts SET likes = MAX(likes, ?), comments = MAX(comments, ?), "
                "shares = MAX(shares, ?), views = MAX(views, ?), fetched_at = ?, "
                "thumbnail = COALESCE(thumbnail, ?), location = COALESCE(location, ?), "
                "author = COALESCE(author, ?), "
                "author_followers = MAX(author_followers, ?) WHERE id = ?",
                (p.get("likes", 0), p.get("comments", 0), p.get("shares", 0), p.get("views", 0),
                 p.get("snapshot_at", now), p.get("thumbnail"), p.get("location"), p.get("author"),
                 p.get("author_followers") or 0, p["id"]))
            row = conn.execute("SELECT relevance FROM posts WHERE id = ?", (p["id"],)).fetchone()
            relevant += row["relevance"] >= 0.35
        else:
            c = classify.classify_rules(p)
            conn.execute(
                "INSERT INTO posts(id, platform, source_id, author, author_name, author_followers, "
                "text, url, thumbnail, location, posted_at, first_fetched, likes, comments, shares, "
                "views, hashtags, mentions, relevance, nl_score, categories, brands, products, "
                "places, phrases, city, demo, fetched_at, flags) "
                "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (p["id"], p["platform"], source_id, p.get("author"), p.get("author_name"),
                 p.get("author_followers") or 0, p.get("text") or "", p.get("url"),
                 p.get("thumbnail"), p.get("location"), p["posted_at"], now,
                 p.get("likes", 0), p.get("comments", 0), p.get("shares", 0), p.get("views", 0),
                 config.dumps(c["hashtags"]), config.dumps(c["mentions"]), c["relevance"],
                 c["nl_score"], config.dumps(c["categories"]), config.dumps(c["brands"]),
                 config.dumps(p.get("products") or c["products"]), config.dumps(c["places"]),
                 config.dumps(c["phrases"]), c["city"], int(demo), p.get("snapshot_at", now),
                 config.dumps(c["flags"])))
            new += 1
            relevant += c["relevance"] >= 0.35
            new_relevant += c["relevance"] >= 0.35 and c["nl_score"] >= 0.4
        conn.execute(
            "INSERT OR REPLACE INTO metric_snapshots(post_id, taken_at, likes, comments, shares, views) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (p["id"], p.get("snapshot_at", now), p.get("likes", 0), p.get("comments", 0),
             p.get("shares", 0), p.get("views", 0)))
    return new, relevant, new_relevant


def _attribute(posts: list[dict], kind: str, values: list[str]) -> dict[str, list[dict]]:
    """Wijs posts uit één Apify-run toe aan de bron waar ze vandaan kwamen.

    Elke betaalde post wordt opgeslagen. Is niet te zien bij welke bron een post
    hoort (de hashtag staat alleen in de eerste reactie, een zoekresultaat bevat
    de zoekwoorden niet letterlijk), dan verdelen we die posts eerlijk over de bronnen.
    """
    out: dict[str, list[dict]] = {v: [] for v in values}
    rest: list[dict] = []
    for p in posts:
        target = None
        if kind == "hashtag":
            target = next((v for v in values if v.lower() in (p.get("hashtags") or [])), None)
        elif kind == "account":
            author = (p.get("author") or "").lower()
            target = next((v for v in values if v.lower() == author), None) or \
                next((v for v in values if v.lower() in author), None)
        elif kind == "zoekterm":
            text = (p.get("text") or "").lower()
            scores = [(sum(w in text for w in v.lower().split()) / max(1, len(v.split())), v) for v in values]
            best = max(scores, default=(0, None))
            target = best[1] if best[0] > 0 else None
        if target is None and len(values) == 1:
            target = values[0]
        if target is None:
            rest.append(p)
        else:
            out[target].append(p)
    for i, p in enumerate(rest):
        out[values[i % len(values)]].append(p)
    return out


# --- stappen ---------------------------------------------------------------

def step_graph(run: Run, settings: dict) -> set[int]:
    """Instagram via de gratis Meta-API. Geeft de bron-id's terug die klaar zijn."""
    done: set[int] = set()
    if not meta_graph.available():
        return done
    with db.session() as conn:
        tags = [dict(r) for r in conn.execute(
            "SELECT * FROM sources WHERE platform='instagram' AND kind='hashtag' AND status='actief'")]
        accounts = [dict(r) for r in conn.execute(
            "SELECT * FROM sources WHERE platform='instagram' AND kind='account' AND status='actief'")]
        used, free = meta_graph.hashtag_slots(conn)
    # Eerst de hashtags die deze week al een plek hebben, dan nieuwe zolang er plek is.
    tags.sort(key=lambda s: (s["value"] not in used, -(s["yield_score"] or 0.6)))
    for s in tags:
        if s["value"] not in used:
            if free <= 0:
                continue
            free -= 1
        try:
            # Internet buiten de database-sessie, anders wacht de interface op Meta.
            with db.session() as conn:
                hid = meta_graph.cached_hashtag_id(conn, s["value"])
            if not hid:
                hid = meta_graph.search_hashtag_id(s["value"])
                with db.session() as conn:
                    meta_graph.remember_hashtag_id(conn, s["value"], hid)
            posts = meta_graph.hashtag_media(hid)
            with db.session() as conn:
                new, rel, useful = store_posts(conn, posts, s["id"])
                discovery.update_source_stats(conn, s["id"], len(posts), rel, new, useful,
                                              0.0, settings["interval_uren"])
            run.results += len(posts)
            run.new_posts += new
            done.add(s["id"])
        except Exception as exc:  # noqa: BLE001 - per bron doorgaan
            run.note(f"Meta-API #{s['value']}: {exc}", "waarschuwing")
    ok = 0
    for s in accounts:
        try:
            posts, _ = meta_graph.fetch_account(s["value"])
            with db.session() as conn:
                new, rel, useful = store_posts(conn, posts, s["id"])
                discovery.update_source_stats(conn, s["id"], len(posts), rel, new, useful,
                                              0.0, settings["interval_uren"])
            run.results += len(posts)
            run.new_posts += new
            done.add(s["id"])
            ok += 1
        except Exception:  # noqa: BLE001 - privé/persoonlijk account: valt terug op Apify
            pass
    run.note(f"Meta-API: {len(done)} bronnen gratis opgehaald "
             f"({ok} accounts, rest hashtags)")
    return done


def step_apify(run: Run, settings: dict, skip: set[int]) -> None:
    if not apify.available():
        run.note("Geen APIFY_TOKEN: TikTok, Facebook en extra Instagram overgeslagen", "waarschuwing")
        return
    step_reconcile_apify(run, settings)
    with db.session() as conn:
        p = budget.plan(conn, settings)
        sources = [dict(r) for r in conn.execute("SELECT * FROM sources WHERE status='actief'")]
    run.note(f"Budget deze ronde: ${p['per_run_usd']:.2f} "
             f"(nog ${p['left_usd']:.2f} voor {p['runs_left']} rondes deze maand)")
    # Het budget in de tool is iets anders dan het tegoed op je Apify-account
    # (net opgevraagd door step_reconcile_apify).
    with db.session() as conn:
        acct = db.get_state(conn, "apify_account")
        if acct and db.now() - db.parse_iso(acct["checked"]) > timedelta(minutes=10):
            acct = None
    if acct:
        left = acct["limit_usd"] - acct["used_usd"]
        if left < 0.05:
            run.note(f"Apify-tegoed op: ${acct['used_usd']:.2f} van ${acct['limit_usd']:.2f} gebruikt deze maand. "
                     "Het budget in de tool verhoogt je Apify-tegoed niet: dat doe je met een betaald plan op "
                     "apify.com (Billing). Deze ronde haalt de tool niets op via Apify.", "fout")
            return
        if left < p["per_run_usd"]:
            factor = left / p["per_run_usd"]
            for plan in p["platforms"].values():
                plan["usd"], plan["results"] = plan["usd"] * factor, int(plan["results"] * factor)
            run.note(f"Apify-account: nog ${left:.2f} tegoed, deze ronde haalt de tool daarom minder op", "waarschuwing")
    for platform in budget.PLATFORMS:
        plan = p["platforms"][platform]
        price = settings[f"prijs_{platform}_per_1000"]
        now_iso = db.iso(db.now())
        eligible = [s for s in sources if s["platform"] == platform and s["id"] not in skip
                    and apify.supports(platform, s["kind"])
                    and (not s["next_due"] or s["next_due"] <= now_iso)]
        chosen = budget.allocate(eligible, plan["results"], settings["min_per_bron"],
                                 settings["max_per_bron"])
        if not chosen:
            if eligible:
                run.note(f"{platform}: budget te klein voor deze ronde, volgende keer weer", "info")
            continue
        usd_left = plan["usd"]
        groups: dict[tuple[str, int], list[dict]] = {}
        for s, n in chosen:
            groups.setdefault((s["kind"], n), []).append(s)
        for (kind, per_value), group in groups.items():
            for i in range(0, len(group), APIFY_BATCH):
                batch = group[i:i + APIFY_BATCH]
                values = [s["value"] for s in batch]
                cap = min(usd_left, per_value * len(values) * price / 1000 * 1.25)
                if cap < 0.01:
                    break
                since = None
                if settings.get("alleen_nieuwe_posts", True):
                    # Vanaf de dag van de oudste laatste ophaalbeurt in deze groep. Het filter werkt
                    # per dag, dus die dag zelf zit er nog in: genoeg marge, minder dubbel betalen.
                    fetched = [db.parse_iso(s["last_fetched"]) for s in batch if s["last_fetched"]]
                    start = min(fetched) if len(fetched) == len(batch) else db.now() - timedelta(days=3)
                    since = start.strftime("%Y-%m-%d")
                try:
                    items, cost = apify.run_actor(platform, kind, values, per_value, cap, since,
                                                  price_per_1000=price)
                except apify.ApifyLimitError:
                    run.note("Apify weigert: het tegoed of de limiet van je Apify-account is op. Het budget in de "
                             "tool verhoogt je Apify-tegoed niet: dat doe je met een betaald plan op apify.com "
                             "(Billing). De rest van deze ronde slaat Apify over.", "fout")
                    return
                except apify.ApifyRunFailed as exc:
                    _remember_failed_run(run, exc, platform, kind, values)
                    usd_left -= exc.max_usd
                    continue
                except (requests.ConnectionError, requests.Timeout) as exc:
                    # Internet of DNS even weg vóór de start: de bronnen tellen niet als leeg en
                    # komen de volgende ronde gewoon weer aan de beurt. Er is niets betaald.
                    run.offline += len(values)
                    run.note(f"Apify {platform}/{kind}: geen verbinding met Apify (internet even weg?), ook niet "
                             f"na een tweede poging. {len(values)} bronnen komen de volgende ronde weer aan de beurt.",
                             "waarschuwing")
                    with db.session() as conn:
                        conn.executemany("UPDATE sources SET last_error = ? WHERE id = ?",
                                         [(config.redact(str(exc))[:300], s["id"]) for s in batch])
                    continue
                except Exception as exc:  # noqa: BLE001
                    run.note(f"Apify {platform}/{kind}: {exc}", "fout")
                    with db.session() as conn:
                        conn.executemany("UPDATE sources SET last_error = ? WHERE id = ?",
                                         [(config.redact(str(exc))[:300], s["id"]) for s in batch])
                    continue
                usd_left -= cost
                run.cost += cost
                # Eerst de kosten vastleggen, in een eigen sessie: wat er daarna ook misgaat,
                # betaald is betaald.
                with db.session() as conn:
                    budget.record(conn, "apify", cost, platform, f"{kind}: {', '.join(values)}")
                posts = _normalize_all(run, platform, items)
                by_value = _attribute(posts, kind, values)
                batch_new = 0
                for s in batch:
                    mine = by_value.get(s["value"], [])
                    share = cost * (len(mine) / len(posts) if posts else 1 / len(batch))
                    try:
                        with db.session() as conn:
                            new, rel, useful = store_posts(conn, mine, s["id"])
                            discovery.update_source_stats(conn, s["id"], len(mine), rel, new, useful,
                                                          share, settings["interval_uren"],
                                                          filtered=since is not None)
                    except Exception as exc:  # noqa: BLE001 - één bron mag de ronde niet stoppen
                        run.note(f"Opslaan mislukt voor {s['value']}: {exc}", "fout")
                        continue
                    run.new_posts += new
                    batch_new += new
                run.results += len(posts)
                dup = 1 - batch_new / len(posts) if posts else 0
                run.note(f"Apify {platform}/{kind}: {len(posts)} posts uit {len(values)} bronnen, "
                         f"{batch_new} nieuw ({dup:.0%} al bekend), ${cost:.3f}")


def _normalize_all(run: Run, platform: str, items: list[dict]) -> list[dict]:
    """Zet Apify-resultaten om; één vreemd resultaat mag de rest niet tegenhouden."""
    posts, bad = [], 0
    for it in items:
        try:
            p = apify.normalize(platform, it)
        except Exception:  # noqa: BLE001
            bad += 1
            continue
        if p:
            posts.append(p)
    if bad:
        run.note(f"{platform}: {bad} resultaten konden niet worden gelezen en zijn overgeslagen", "waarschuwing")
    return posts


def _remember_failed_run(run: Run, exc, platform: str, kind: str, values: list[str]) -> None:
    """Een gestarte run ging mis: tel voorlopig het maximum en zet hem recht in de volgende ronde."""
    run.cost += exc.max_usd
    with db.session() as conn:
        spend_id = budget.record(conn, "apify", exc.max_usd, platform,
                                 f"voorlopig (run {exc.run_id} onderbroken): {kind}: {', '.join(values)}")
        pending = db.get_state(conn, "apify_pending", []) or []
        pending.append({"run_id": exc.run_id, "platform": platform, "kind": kind, "values": values,
                        "provisional": exc.max_usd, "spend_id": spend_id, "at": db.iso(db.now())})
        db.set_state(conn, "apify_pending", pending)
    run.offline += len(values)
    run.note(f"Apify {platform}/{kind}: de run liep al, maar daarna ging er iets mis ({exc}). De tool telt "
             f"voorlopig ${exc.max_usd:.2f} en haalt de resultaten en echte kosten de volgende ronde op.",
             "waarschuwing")


def step_reconcile_apify(run: Run, settings: dict) -> None:
    """Zet de kosten recht: onderbroken runs ophalen, en de telling vergelijken met Apify zelf."""
    with db.session() as conn:
        pending = db.get_state(conn, "apify_pending", []) or []
    keep = []
    for item in pending:
        info = apify.run_info(item["run_id"])
        age_h = (db.now() - db.parse_iso(item["at"])).total_seconds() / 3600
        if not info or info["status"] not in apify.FINAL:
            if info and age_h > 2:
                apify.abort(item["run_id"])
            if age_h < 72:
                keep.append(item)
            continue
        posts = []
        if info["dataset"]:
            try:
                posts = _normalize_all(run, item["platform"], apify.dataset_items(info["dataset"]))
            except Exception:  # noqa: BLE001 - dan alleen de kosten rechtzetten
                posts = []
        price = settings[f"prijs_{item['platform']}_per_1000"]
        actual = max(info["usage_usd"], len(posts) * price / 1000)
        with db.session() as conn:
            budget.record(conn, "apify", round(actual - item["provisional"], 4), item["platform"],
                          f"correctie run {item['run_id']}", correction=True)
            by_value = _attribute(posts, item["kind"], item["values"])
            new = 0
            for value, mine in by_value.items():
                src = conn.execute("SELECT id FROM sources WHERE platform = ? AND kind = ? AND value = ?",
                                   (item["platform"], item["kind"], value)).fetchone()
                new += store_posts(conn, mine, src["id"] if src else None)[0]
        run.new_posts += new
        run.note(f"Onderbroken run van {item['platform']} rechtgezet: {len(posts)} posts ({new} nieuw), "
                 f"echte kosten ${actual:.2f} in plaats van ${item['provisional']:.2f}")
    with db.session() as conn:
        db.set_state(conn, "apify_pending", keep)
    _reconcile_account(run)


def _reconcile_account(run: Run) -> None:
    """Vergelijk wat de tool telde met wat Apify zelf rekende, sinds de vorige ronde.

    Sommige actors rekenen extra (startkosten, filters, proxy) of melden hun kosten
    niet: dan klopt de eigen telling niet en loopt het budget ongemerkt uit.
    """
    acct = apify.account_usage()
    if not acct:
        return
    with db.session() as conn:
        last = db.get_state(conn, "apify_usage_mark")
        # Het meetpunt is het laatste kostenregelnummer: exacter dan een tijdstip per seconde.
        mark_id = conn.execute("SELECT COALESCE(MAX(id), 0) FROM spend").fetchone()[0]
        db.set_state(conn, "apify_usage_mark", {"used": acct["used_usd"], "cycle_end": acct.get("cycle_end"),
                                                "spend_id": mark_id, "at": db.iso(db.now())})
        db.set_state(conn, "apify_account", {**acct, "checked": db.iso(db.now())})
        if (not last or "spend_id" not in last or last.get("cycle_end") != acct.get("cycle_end")
                or acct["used_usd"] < last["used"]):
            return  # eerste keer of nieuwe Apify-periode: alleen het meetpunt bewaren
        actual = acct["used_usd"] - last["used"]
        counted = conn.execute("SELECT COALESCE(SUM(usd), 0) FROM spend WHERE kind = 'apify' AND id > ?",
                               (last["spend_id"],)).fetchone()[0]
        diff = round(actual - counted, 2)
        if abs(diff) >= 0.05:
            budget.record(conn, "apify", diff, None, "correctie volgens je Apify-account", correction=True)
    if abs(diff) >= 0.05:
        run.note(f"Kosten rechtgezet volgens je Apify-account: {'+' if diff > 0 else ''}${diff:.2f} "
                 f"(Apify rekende ${actual:.2f}, de tool telde ${counted:.2f})")


def step_remeasure(run: Run, settings: dict) -> None:
    """Meet de snelste posts van de afgelopen 2 dagen opnieuw.

    Zo zie je of een video echt doorschiet (views per uur sinds de vorige
    meting) in plaats van één momentopname. Kost per post één resultaat.
    """
    per_platform = int(settings.get("herhaalmeting_per_ronde", 0))
    if not per_platform or not apify.available():
        return
    with db.session() as conn:
        if budget.plan(conn, settings)["left_usd"] <= 0:
            run.note("Herhaalmeting overgeslagen: het maandbudget is op", "info")
            return
        acct = db.get_state(conn, "apify_account")
    if acct and acct.get("limit_usd", 0) - acct.get("used_usd", 0) < 0.05:
        return
    since = db.iso(db.now() - timedelta(hours=48))
    recent = db.iso(db.now() - timedelta(hours=settings["interval_uren"] - 0.5))
    with db.session() as conn:
        base = signals.baselines(conn, include_demo=False)
        rows = conn.execute(
            "SELECT * FROM posts WHERE posted_at >= ? AND demo = 0 AND url IS NOT NULL "
            "AND platform IN ('tiktok', 'instagram') AND relevance >= 0.35 AND nl_score >= 0.4 "
            "AND (remeasured_at IS NULL OR remeasured_at < ?) AND fetched_at < ?",
            (since, recent, recent)).fetchall()
    ranked: dict[str, list] = {}
    for p in rows:
        sig = signals.of_post(p, base)
        ranked.setdefault(p["platform"], []).append(
            ((sig["breakout"], sig["views_x"] or 0, sig["shares_x"] or 0), p["url"], p["id"]))
    for platform, items in ranked.items():
        chosen = sorted(items, reverse=True)[:per_platform]
        urls = [u for _, u, _ in chosen]
        cap = len(urls) * settings[f"prijs_{platform}_per_1000"] / 1000 * 1.5
        try:
            found, cost = apify.run_actor(platform, "post", urls, 1, cap,
                                          price_per_1000=settings[f"prijs_{platform}_per_1000"])
        except apify.ApifyRunFailed as exc:
            _remember_failed_run(run, exc, platform, "post", urls)
            continue
        except Exception as exc:  # noqa: BLE001
            run.note(f"Herhaalmeting {platform}: {exc}", "waarschuwing")
            continue
        with db.session() as conn:
            budget.record(conn, "apify", cost, platform, f"herhaalmeting: {len(urls)} posts")
        posts = _normalize_all(run, platform, found)
        with db.session() as conn:
            store_posts(conn, posts, None)
            conn.executemany("UPDATE posts SET remeasured_at = ? WHERE id = ?",
                             [(db.iso(db.now()), pid) for _, _, pid in chosen])
        run.cost += cost
        run.note(f"Herhaalmeting {platform}: {len(posts)} snelle posts opnieuw gemeten, ${cost:.3f}")


def step_ai(run: Run, settings: dict) -> None:
    if not classify.ai_available(settings):
        return
    with db.session() as conn:
        spent = budget.spent_usd(conn, "ai")
        limit_usd = settings["ai_maandbudget_eur"] / (settings["eur_per_usd"] or 0.92)
        rows = [db.row_to_dict(r) for r in conn.execute(
            # Alleen twijfelgevallen en relevante posts; duidelijk niet-Nederlandse
            # posts slaan we over. Scheelt de helft van de AI-kosten.
            "SELECT * FROM posts WHERE ai_done = 0 AND demo = 0 AND relevance >= 0.3 "
            "AND nl_score >= 0.15 AND platform != 'nieuws' "
            "ORDER BY posted_at DESC LIMIT ?", (AI_MAX_PER_RUN,))]
    if not rows:
        return
    done = 0
    for i in range(0, len(rows), AI_BATCH):
        if spent >= limit_usd:
            run.note("AI-maandbudget bereikt; verder alleen indeling op trefwoorden", "waarschuwing")
            break
        batch = rows[i:i + AI_BATCH]
        try:
            results, cost = classify.classify_ai(batch, settings)
        except Exception as exc:  # noqa: BLE001
            run.note(f"AI-indeling mislukt: {exc}", "fout")
            break
        spent += cost
        run.ai_cost += cost
        with db.session() as conn:
            budget.record(conn, "ai", cost, None, f"{len(batch)} posts")
            for p in batch:
                ai = results.get(p["id"])
                if not ai:
                    conn.execute("UPDATE posts SET ai_done = 2 WHERE id = ?", (p["id"],))
                    continue
                rule = classify.classify_rules(p)
                m = classify.merge_ai(rule, ai)
                conn.execute(
                    "UPDATE posts SET relevance=?, nl_score=?, categories=?, brands=?, products=?, "
                    "places=?, city=?, sentiment=?, summary=?, ai_done=1 WHERE id=?",
                    (m["relevance"], m["nl_score"], config.dumps(m["categories"]),
                     config.dumps(m["brands"]), config.dumps(m["products"]),
                     config.dumps(m["places"]), m["city"], m.get("sentiment"),
                     m.get("summary"), p["id"]))
                done += 1
    run.note(f"AI heeft {done} posts ingedeeld (${run.ai_cost:.3f})")


def step_news(run: Run, settings: dict) -> None:
    if not settings.get("nieuws_aan", True):
        return
    items, errors = news.fetch(seeds.NEWS_QUERIES, settings.get("extra_rss") or [])
    for e in errors[:3]:
        run.note(e, "waarschuwing")
    now = db.iso(db.now())
    posts = []
    with db.session() as conn:
        for it in items:
            cur = conn.execute(
                "INSERT OR IGNORE INTO news(id, title, url, outlet, published_at, query, fetched_at) "
                "VALUES (?, ?, ?, ?, ?, ?, ?)",
                (it["id"], it["title"], it["url"], it["outlet"], it["published_at"], it["query"], now))
            if cur.rowcount:
                posts.append({"id": it["id"], "platform": "nieuws", "author": it["outlet"],
                              "text": it["title"], "url": it["url"],
                              "posted_at": it["published_at"]})
        new, _, _ = store_posts(conn, posts, None)
    run.new_posts += new
    run.note(f"Nieuws: {len(items)} berichten bekeken, {new} nieuw")


# Verhoog dit getal als de woordenlijsten of regels in classify.py veranderen:
# bij de volgende start worden alle posts (zonder AI-oordeel) opnieuw beoordeeld.
CLASSIFY_VERSION = 7


def reclassify_if_needed() -> int:
    with db.session() as conn:
        if db.get_state(conn, "classify_version", 1) >= CLASSIFY_VERSION:
            return 0
        rows = [db.row_to_dict(r) for r in conn.execute(
            "SELECT id, platform, text, location, author, author_name, products, hashtags, "
            "mentions, demo FROM posts WHERE ai_done != 1")]
        for p in rows:
            c = classify.classify_rules(p)
            conn.execute(
                "UPDATE posts SET relevance=?, nl_score=?, categories=?, brands=?, places=?, "
                "phrases=?, city=?, hashtags=?, mentions=?, products=?, flags=? WHERE id=?",
                (c["relevance"], c["nl_score"], config.dumps(c["categories"]),
                 config.dumps(c["brands"]), config.dumps(c["places"]), config.dumps(c["phrases"]),
                 c["city"], config.dumps(c["hashtags"]), config.dumps(c["mentions"]),
                 # Producten opnieuw raden (betere regels); alleen demodata heeft vaste producten.
                 config.dumps((p["products"] if p["demo"] else None) or c["products"]),
                 config.dumps(c["flags"]), p["id"]))
        removed = discovery.prune_bad_hashtags(conn)
        if removed:
            log.info("Opgeruimd: %s", ", ".join("#" + r for r in removed))
        db.set_state(conn, "classify_version", CLASSIFY_VERSION)
    return len(rows)


def is_snack_product(name: str) -> bool:
    lower = name.lower()
    if any(word in lower for word in lexicon.NON_FOOD):
        return False
    return classify.classify_rules({"text": name, "platform": "winkel"})["relevance"] >= 0.4


def step_supermarkets(run: Run, settings: dict, force: bool = False) -> None:
    if not settings.get("supermarkt_aan", True):
        return
    with db.session() as conn:
        last = db.get_state(conn, "supermarkt_laatst")
        etag = None if force else db.get_state(conn, "supermarkt_etag")
    every = max(1, settings.get("supermarkt_interval_uren", 12)) - 0.5
    if last and not force and db.now() - db.parse_iso(last) < timedelta(hours=every):
        return
    try:
        stores, etag = supermarket.fetch(etag)
    except Exception as exc:  # noqa: BLE001
        run.note(f"Supermarkten (checkjebon): {exc}", "waarschuwing")
        return
    with db.session() as conn:
        db.set_state(conn, "supermarkt_laatst", db.iso(db.now()))
        db.set_state(conn, "supermarkt_etag", etag)
    if stores is None:
        run.note("Supermarkten: geen nieuwe assortimentsgegevens sinds de vorige keer")
        return

    now = db.iso(db.now())
    via_apify = set(apify_stores(settings))
    summary = []
    with db.session() as conn:
        status = db.get_state(conn, "supermarkt_status", {}) or {}
        for store, products in stores.items():
            if store in via_apify:
                continue  # deze winkel komt via Apify: de (stilstaande) checkjebon-data niet meer gebruiken
            st, line = _store_products(conn, store, products, now, "cjb")
            if st.get("ok") or not st.get("producten"):
                stil = _stale_since(conn, store, products) if products else None
                if stil and st.get("nulmeting_klaar"):
                    # De bron levert voor deze winkel al lang exact hetzelfde assortiment: niet 'werkt'.
                    st.update(ok=False, stil=stil,
                              melding=f"bron staat stil sinds {stil[:10]}: geen nieuwe gegevens van deze winkel")
            status[store] = st
            if line:
                summary.append(line)
        db.set_state(conn, "supermarkt_status", status)
        fixed = unmark_relisted(conn)
    run.note("Supermarkten (nieuw, waarvan snack-relevant): " + ", ".join(summary)
             + (f". {fixed} eerder als nieuw gemelde producten bleken al bekend" if fixed else ""))


def _store_products(conn, store: str, products: list[dict], now: str, source: str,
                    partial: bool = False) -> tuple[dict, str]:
    """Vergelijk het assortiment van één winkel met wat we kennen. Geeft (status, samenvatting).

    De eerste keer per bron en winkel is de nulmeting: dan is niets nieuw. Een product met
    dezelfde naam en verpakking als een bekend product (ander artikelnummer, of uit een
    andere bron) telt ook niet als nieuw.
    """
    if not products:
        return {"ok": False, "melding": "geen assortiment beschikbaar", "t": now}, ""
    baseline_done = db.get_state(conn, f"nulmeting_{source}_{store}", False)
    known, known_names = set(), set()
    for r in conn.execute("SELECT id, name, size FROM products WHERE store = ?", (store,)):
        known.add(r["id"])
        known_names.add(_product_key(r["name"], r["size"]))
    fresh = [p for p in products if p["id"] not in known]
    rows, new_relevant, relisted = [], 0, 0
    for p in fresh:
        # Winkels zetten bestaande producten soms opnieuw online met een ander
        # artikelnummer (Spar). Zelfde naam en verpakking = niet nieuw.
        again = _product_key(p["name"], p["size"]) in known_names
        relisted += again
        # Bij de nulmeting is niets nieuw, dus beoordelen is niet nodig (scheelt een minuut).
        relevant = baseline_done and not again and is_snack_product(p["name"])
        is_new = int(baseline_done and not again)
        new_relevant += is_new and relevant
        rows.append((p["id"], p["store"], p["name"], p["size"], p["price"], p["url"],
                     now, now, is_new, int(relevant)))
    conn.executemany(
        "INSERT OR IGNORE INTO products(id, store, name, size, price, url, first_seen, "
        "last_seen, is_new, relevant) VALUES (?,?,?,?,?,?,?,?,?,?)", rows)
    conn.executemany("UPDATE products SET last_seen = ? WHERE id = ?", [(now, p["id"]) for p in products])
    db.set_state(conn, f"nulmeting_{source}_{store}", True)
    what = "snackproducten bekeken" if partial else "producten"
    if not baseline_done:
        return ({"ok": True, "t": now, "producten": len(products), "bron": source,
                 "melding": f"{len(products)} {what} vastgelegd (nulmeting)"}, f"{store} nulmeting")
    n_new = len(fresh) - relisted
    return ({"ok": True, "t": now, "producten": len(products), "bron": source, "nulmeting_klaar": True,
             "melding": f"{len(products)} {what}, {n_new} nieuw ({new_relevant} snack-relevant)"
                        + (f", {relisted} opnieuw online gezet" if relisted else "")},
            f"{store} {n_new} ({new_relevant})")


def apify_stores(settings: dict) -> dict[str, str]:
    """{winkelnaam: code} voor de winkels die via Apify gaan (alleen met een Apify-sleutel)."""
    if not settings.get("supermarkt_apify_aan", True) or not apify.available():
        return {}
    codes = settings.get("supermarkt_apify_winkels") or {}
    return {supermarket.STORE_NAMES.get(c, c.title()): c for c in codes if c}


def step_supermarkets_apify(run: Run, settings: dict, force: bool = False) -> None:
    """Winkels waarvan de gratis bron stilstaat (AH, Jumbo, Lidl, ...): zelf zoeken via Apify.

    Per winkel één run met snackzoektermen; de eerste keer is de nulmeting. Standaard
    twee keer per week, ongeveer 600 producten per keer (± 3 dollar).
    """
    stores = apify_stores(settings)
    terms = [t.strip() for t in settings.get("supermarkt_zoektermen") or [] if t.strip()]
    if not stores or not terms:
        return
    with db.session() as conn:
        last = db.get_state(conn, "supermarkt_apify_laatst")
        days = max(1.0, float(settings.get("supermarkt_apify_dagen", 3.5) or 3.5))
        if last and not force and db.now() - db.parse_iso(last) < timedelta(days=days) - timedelta(hours=1):
            return
        if budget.plan(conn, settings)["left_usd"] <= 0:
            run.note("Supermarkten via Apify overgeslagen: het maandbudget is op", "info")
            return
    per_store = max(len(terms), int(settings.get("supermarkt_per_winkel", 90) or 90))
    price = settings.get("prijs_supermarkt_per_1000", 5.0)
    now = db.iso(db.now())
    summary, total_cost = [], 0.0
    for store, code in stores.items():
        try:
            items, cost = apify.run_actor("supermarkt", "zoekterm", terms, max(1, per_store // len(terms)),
                                          per_store * price / 1000 * 1.3, price_per_1000=price,
                                          extra_input={"supermarkets": [code], "maxResults": per_store})
        except apify.ApifyRunFailed as exc:
            with db.session() as conn:
                budget.record(conn, "apify", exc.max_usd, None, f"supermarkt {store} (onderbroken)")
            run.note(f"Supermarkt {store} via Apify: {exc}", "waarschuwing")
            continue
        except Exception as exc:  # noqa: BLE001
            with db.session() as conn:
                status = db.get_state(conn, "supermarkt_status", {}) or {}
                status[store] = {"ok": False, "t": now, "bron": "apify", "melding": f"Apify: {str(exc)[:160]}"}
                db.set_state(conn, "supermarkt_status", status)
            run.note(f"Supermarkt {store} via Apify: {exc}", "waarschuwing")
            continue
        total_cost += cost
        products = [p for p in (supermarket.parse_apify(it, store, code) for it in items) if p]
        with db.session() as conn:
            budget.record(conn, "apify", cost, None, f"supermarkt {store}: {len(items)} producten")
            st, line = _store_products(conn, store, products, now, "apify", partial=True)
            status = db.get_state(conn, "supermarkt_status", {}) or {}
            status[store] = st
            db.set_state(conn, "supermarkt_status", status)
        summary.append(line or f"{store} 0")
    with db.session() as conn:
        db.set_state(conn, "supermarkt_apify_laatst", now)
        unmark_relisted(conn)
    run.cost += total_cost
    run.note(f"Supermarkten via Apify (nieuw, waarvan snack-relevant): {', '.join(summary)}, ${total_cost:.2f}")


STALE_DAYS = 4


def _stale_since(conn, store: str, products: list[dict]) -> str | None:
    """Sinds wanneer is het assortiment van deze winkel precies hetzelfde? None als het recent veranderde.

    checkjebon werkt elke dag het bestand bij, maar voor sommige winkels (AH, Jumbo, Lidl, Plus)
    bleef de inhoud maandenlang gelijk. Dan lijkt alles te werken, terwijl er nooit iets nieuws komt.
    """
    sig = hashlib.sha1("\n".join(sorted(f"{p['id']}|{p['price']}" for p in products)).encode()).hexdigest()
    key = f"supermarkt_inhoud_{store}"
    seen = db.get_state(conn, key)
    if not seen or seen.get("sig") != sig:
        db.set_state(conn, key, {"sig": sig, "since": db.iso(db.now())})
        return None
    since = seen["since"]
    return since if db.now() - db.parse_iso(since) >= timedelta(days=STALE_DAYS) else None


def _product_key(name: str, size: str | None) -> tuple[str, str]:
    return (classify.norm(name or ""), classify.norm(size or ""))


def unmark_relisted(conn) -> int:
    """Haal 'nieuw' weg bij producten die de winkel al onder een ander artikelnummer had."""
    older = {}
    for r in conn.execute("SELECT store, name, size, first_seen FROM products WHERE demo = 0 AND is_new = 0"):
        key = (r["store"], *_product_key(r["name"], r["size"]))
        if key not in older or r["first_seen"] < older[key]:
            older[key] = r["first_seen"]
    ids = [r["id"] for r in conn.execute("SELECT id, store, name, size, first_seen FROM products "
                                         "WHERE demo = 0 AND is_new = 1")
           if (first := older.get((r["store"], *_product_key(r["name"], r["size"])))) and first <= r["first_seen"]]
    conn.executemany("UPDATE products SET is_new = 0 WHERE id = ?", [(i,) for i in ids])
    return len(ids)


def step_snackspert(run: Run) -> None:
    with db.session() as conn:
        last = db.get_state(conn, "snackspert_laatst")
    if last and db.now() - db.parse_iso(last) < timedelta(hours=24):
        return
    try:
        reviewed = snackspert.fetch_reviewed()
    except Exception as exc:  # noqa: BLE001
        run.note(f"Snackspert-recensies ophalen mislukt: {exc}", "waarschuwing")
        return
    with db.session() as conn:
        conn.execute("DELETE FROM reviewed")
        conn.executemany("INSERT OR REPLACE INTO reviewed(slug, name, url, norm) VALUES (?,?,?,?)",
                         [(r["slug"], r["name"], r["url"], r["norm"]) for r in reviewed])
        db.set_state(conn, "snackspert_laatst", db.iso(db.now()))
    run.note(f"Snackspert: {len(reviewed)} gereviewde zaken bijgewerkt")


def step_discovery(run: Run, settings: dict, demo: bool = False) -> None:
    with db.session() as conn:
        added = discovery.run(conn, settings, demo=demo)
    if added:
        act = [a for a in added if a["status"] == "actief"]
        names = ", ".join({"hashtag": "#", "account": "@"}.get(a["kind"], "zoekterm ") + a["value"]
                          for a in act[:6])
        run.note(f"Ontdekt: {len(added)} nieuwe bronnen, {len(act)} direct actief"
                 + (f" ({names})" if names else ""))


def step_geocode(run: Run) -> None:
    """Zoek plaatsen van tips op (OpenStreetMap, gratis) voor routes die de tool zelf bedenkt."""
    from . import geo

    res = geo.fill(limit=40)
    if res.get("found") or res.get("failed"):
        run.note(f"Plaatsen opgezocht voor routes: {res['found']} gevonden"
                 + (f", {res['failed']} niet gevonden" if res["failed"] else ""))


def run_once(trigger: str = "schema", force_supermarkets: bool = False) -> dict | None:
    if not _run_lock.acquire(blocking=False):
        return None
    try:
        with db.session() as conn:
            settings = db.get_settings(conn)
            seeds.upgrade(conn, db.iso(db.now()))
            demo_mode = demo_active(conn)
        run = Run(trigger)
        try:
            if demo_mode:
                from . import demo
                with db.session() as conn:
                    n = demo.simulate_round(conn)
                run.results += n
                run.new_posts += n
                run.note(f"Demomodus: {n} voorbeeldposts toegevoegd (geen echte data, geen kosten)")
                step_discovery(run, settings, demo=True)
            else:
                with db.session() as conn:
                    if db.get_state(conn, "demo_seeded"):
                        from . import demo
                        demo.clear(conn)
                        run.note("Echte databron gevonden: demodata gewist")
                done = step_graph(run, settings)
                step_apify(run, settings, done)
                step_remeasure(run, settings)
                step_news(run, settings)
                step_ai(run, settings)
                step_supermarkets(run, settings, force_supermarkets)
                step_supermarkets_apify(run, settings, force_supermarkets)
                step_snackspert(run)
                step_discovery(run, settings)
                step_geocode(run)
                step_own_posts(run, settings)
                step_maps(run, settings)
            step_maintenance(run, settings)
            try:
                with db.session() as conn:
                    trefkans.log_round(conn, include_demo=demo_mode)
            except Exception:  # noqa: BLE001 - bijhouden mag de ronde nooit breken
                log.exception("Trefkans bijhouden mislukt")
        except Exception as exc:  # noqa: BLE001 - ronde altijd netjes afsluiten
            log.exception("Ophaalronde mislukt")
            run.note(f"Ronde afgebroken: {exc}", "fout")
        run.finish()
        return {"id": run.id, "results": run.results, "new": run.new_posts}
    finally:
        _run_lock.release()


def step_own_posts(run: Run, settings: dict) -> None:
    """Eens per week je eigen Instagram-posts ophalen (± 2 cent per week, de eerste keer ± 15 cent)."""
    handle = (settings.get("eigen_instagram") or "").strip().lstrip("@").strip("/")
    if not handle or not apify.available():
        return
    with db.session() as conn:
        last = db.get_state(conn, "eigen_posts_laatst")
        if last and db.now() - db.parse_iso(last["at"]) < timedelta(days=max(1, settings.get("eigen_posts_dagen", 7))):
            return
        if budget.plan(conn, settings)["left_usd"] <= 0:
            return
    # Twee weken terug: dan worden ook de cijfers van je recente posts bijgewerkt.
    since = (db.now() - timedelta(days=14)).strftime("%Y-%m-%d") if last else None
    limit = 30 if last else 60
    price = settings["prijs_instagram_per_1000"]
    try:
        found, cost = apify.run_actor("instagram", "account", [handle], limit, limit * price / 1000 * 1.5,
                                      since=since, price_per_1000=price)
    except apify.ApifyRunFailed as exc:
        _remember_failed_run(run, exc, "instagram", "account", [handle])
        return
    except Exception as exc:  # noqa: BLE001
        run.note(f"Eigen posts ophalen mislukt: {exc}", "waarschuwing")
        return
    with db.session() as conn:
        budget.record(conn, "apify", cost, "instagram", f"eigen posts @{handle}")
    posts = [p for p in _normalize_all(run, "instagram", found) if (p.get("author") or "").lower() == handle.lower()]
    with db.session() as conn:
        res = ownposts.merge_fetched(conn, posts)
        db.set_state(conn, "eigen_posts_laatst", {"at": db.iso(db.now()), **res})
    run.cost += cost
    run.note(f"Eigen posts @{handle}: {res['new']} nieuw, {res['updated']} bijgewerkt, ${cost:.3f}")


def step_maps(run: Run, settings: dict) -> None:
    """Eens per week nieuwe zaken zoeken op Google Maps (± 1 dollar per week)."""
    if not settings.get("maps_aan", True) or not apify.available():
        return
    with db.session() as conn:
        last = db.get_state(conn, "maps_laatst")
        if last and db.now() - db.parse_iso(last["at"]) < timedelta(days=7) - timedelta(hours=1):
            return
        if budget.plan(conn, settings)["left_usd"] <= 0:
            return
        searches = nieuwezaken.next_searches(conn, settings)
    if not searches:
        return
    per = max(5, int(settings.get("maps_per_zoekopdracht", 30)))
    price = settings.get("prijs_maps_per_1000", 4.0)
    values = [s for s, _ in searches]
    try:
        items, cost = apify.run_actor("maps", "zoekterm", values, per, len(values) * per * price / 1000 * 1.3,
                                      price_per_1000=price)
    except apify.ApifyRunFailed as exc:
        with db.session() as conn:
            budget.record(conn, "apify", exc.max_usd, None, "Google Maps (onderbroken)")
        run.note(f"Google Maps: {exc}", "waarschuwing")
        return
    except Exception as exc:  # noqa: BLE001
        run.note(f"Google Maps: {exc}", "waarschuwing")
        return
    with db.session() as conn:
        budget.record(conn, "apify", cost, None, f"Google Maps: {', '.join(sorted({c for _, c in searches}))}")
    # De actor geeft per resultaat de zoekopdracht terug; anders tellen we alles onder de eerste.
    by_search: dict[str, list] = {}
    for it in items:
        by_search.setdefault(it.get("searchString") or values[0], []).append(it)
    with db.session() as conn:
        new = sum(nieuwezaken.store(conn, s, its) for s, its in by_search.items())
        cities = list(dict.fromkeys(c for _, c in searches))
        n_cities = len([c for c in settings.get("maps_steden") or [] if c.strip()]) or 1
        db.set_state(conn, "maps_volgende", (db.get_state(conn, "maps_volgende", 0) + len(cities)) % n_cities)
        db.set_state(conn, "maps_laatst", {"at": db.iso(db.now()), "cities": cities, "found": len(items), "new": new})
    run.cost += cost
    run.note(f"Google Maps ({', '.join(cities)}): {len(items)} zaken bekeken, {new} nieuw, ${cost:.2f}")


def step_maintenance(run: Run, settings: dict) -> None:
    """Eens per week oude posts opruimen en een back-up maken."""
    with db.session() as conn:
        if onderhoud.cleanup_due(conn):
            gone = onderhoud.cleanup(conn, settings)
            if gone.get("posts"):
                run.note(f"Opgeruimd: {gone['posts']} posts ouder dan {settings.get('bewaar_maanden')} maanden")
        due = onderhoud.backup_due(conn, settings)
    if due:
        try:
            info = onderhoud.make_backup(settings)
            run.note(f"Back-up gemaakt ({info['mb']} MB) in {'Google Drive' if info['drive'] else info['path']}")
        except Exception as exc:  # noqa: BLE001 - een volle schijf mag de ronde niet laten mislukken
            run.note(f"Back-up mislukt: {exc}", "waarschuwing")


def demo_active(conn) -> bool:
    """Demomodus zolang er geen enkele echte databron is ingesteld."""
    if config.secret("TRENDRADAR_DEMO") == "1":
        return True
    return not (apify.available() or meta_graph.available())


def last_run(conn) -> dict | None:
    r = conn.execute("SELECT * FROM runs ORDER BY started_at DESC, id DESC LIMIT 1").fetchone()
    return db.row_to_dict(r) if r else None


RETRY_AFTER_FAILED = timedelta(minutes=30)


def due(conn, settings: dict) -> bool:
    r = conn.execute("SELECT started_at, status FROM runs WHERE status != 'bezig' "
                     "ORDER BY started_at DESC, id DESC LIMIT 1").fetchone()
    if not r:
        return True
    waited = db.now() - db.parse_iso(r["started_at"])
    # Een mislukte of afgebroken ronde (geen internet, Ctrl+C) niet 6 uur laten liggen.
    if r["status"] == "fout":
        return waited >= RETRY_AFTER_FAILED
    return waited >= timedelta(hours=settings["interval_uren"])

