"""Eén ophaalronde: bronnen ophalen, posts indelen, opslaan, nieuwe bronnen zoeken."""
from __future__ import annotations

import logging
import threading
from datetime import timedelta

from . import budget, classify, config, db, discovery, lexicon, seeds, signals, snackspert
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
        status = "klaar" if not self.errors else ("deels" if self.results or self.new_posts else "fout")
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
    """Wijs posts uit één Apify-run toe aan de bron waar ze vandaan kwamen."""
    out: dict[str, list[dict]] = {v: [] for v in values}
    for p in posts:
        target = None
        if kind == "hashtag":
            target = next((v for v in values if v.lower() in (p.get("hashtags") or [])), None)
        elif kind == "account":
            author = (p.get("author") or "").lower()
            target = next((v for v in values if v.lower() == author or v.lower() in author), None)
        if target is None and len(values) == 1:
            target = values[0]
        if target is None and kind == "zoekterm":
            text = (p.get("text") or "").lower()
            target = next((v for v in values if all(w in text for w in v.split())), values[0])
        if target is not None:
            out[target].append(p)
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
            with db.session() as conn:
                posts = meta_graph.fetch_hashtag(conn, s["value"])
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
    with db.session() as conn:
        p = budget.plan(conn, settings)
        sources = [dict(r) for r in conn.execute("SELECT * FROM sources WHERE status='actief'")]
    run.note(f"Budget deze ronde: ${p['per_run_usd']:.2f} "
             f"(nog ${p['left_usd']:.2f} voor {p['runs_left']} rondes deze maand)")
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
                    # Vanaf de oudste laatste ophaalbeurt in deze groep, min een dag marge.
                    fetched = [db.parse_iso(s["last_fetched"]) for s in batch if s["last_fetched"]]
                    start = (min(fetched) if len(fetched) == len(batch) else db.now()
                             - timedelta(days=2)) - timedelta(days=1)
                    since = start.strftime("%Y-%m-%d")
                try:
                    items, cost = apify.run_actor(platform, kind, values, per_value, cap, since,
                                                  price_per_1000=price)
                except Exception as exc:  # noqa: BLE001
                    run.note(f"Apify {platform}/{kind}: {exc}", "fout")
                    with db.session() as conn:
                        conn.executemany("UPDATE sources SET last_error = ? WHERE id = ?",
                                         [(config.redact(str(exc))[:300], s["id"]) for s in batch])
                    continue
                usd_left -= cost
                run.cost += cost
                posts = [x for x in (apify.normalize(platform, it) for it in items) if x]
                by_value = _attribute(posts, kind, values)
                batch_new = 0
                with db.session() as conn:
                    budget.record(conn, "apify", cost, platform, f"{kind}: {', '.join(values)}")
                    for s in batch:
                        mine = by_value.get(s["value"], [])
                        share = cost * (len(mine) / len(posts) if posts else 1 / len(batch))
                        new, rel, useful = store_posts(conn, mine, s["id"])
                        run.new_posts += new
                        batch_new += new
                        discovery.update_source_stats(conn, s["id"], len(mine), rel, new, useful,
                                                      share, settings["interval_uren"])
                run.results += len(posts)
                dup = 1 - batch_new / len(posts) if posts else 0
                run.note(f"Apify {platform}/{kind}: {len(posts)} posts uit {len(values)} bronnen, "
                         f"{batch_new} nieuw ({dup:.0%} al bekend), ${cost:.3f}")


def step_remeasure(run: Run, settings: dict) -> None:
    """Meet de snelste posts van de afgelopen 2 dagen opnieuw.

    Zo zie je of een video echt doorschiet (views per uur sinds de vorige
    meting) in plaats van één momentopname. Kost per post één resultaat.
    """
    per_platform = int(settings.get("herhaalmeting_per_ronde", 0))
    if not per_platform or not apify.available():
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
        except Exception as exc:  # noqa: BLE001
            run.note(f"Herhaalmeting {platform}: {exc}", "waarschuwing")
            continue
        posts = [x for x in (apify.normalize(platform, it) for it in found) if x]
        with db.session() as conn:
            budget.record(conn, "apify", cost, platform, f"herhaalmeting: {len(urls)} posts")
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
CLASSIFY_VERSION = 5


def reclassify_if_needed() -> int:
    with db.session() as conn:
        if db.get_state(conn, "classify_version", 1) >= CLASSIFY_VERSION:
            return 0
        rows = [db.row_to_dict(r) for r in conn.execute(
            "SELECT id, platform, text, location, author, author_name, products, hashtags, "
            "mentions FROM posts WHERE ai_done != 1")]
        for p in rows:
            c = classify.classify_rules(p)
            conn.execute(
                "UPDATE posts SET relevance=?, nl_score=?, categories=?, brands=?, places=?, "
                "phrases=?, city=?, hashtags=?, mentions=?, products=?, flags=? WHERE id=?",
                (c["relevance"], c["nl_score"], config.dumps(c["categories"]),
                 config.dumps(c["brands"]), config.dumps(c["places"]), config.dumps(c["phrases"]),
                 c["city"], config.dumps(c["hashtags"]), config.dumps(c["mentions"]),
                 config.dumps(p["products"] or c["products"]), config.dumps(c["flags"]), p["id"]))
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
    status = {}
    summary = []
    with db.session() as conn:
        for store, products in stores.items():
            if not products:
                status[store] = {"ok": False, "melding": "geen assortiment beschikbaar", "t": now}
                continue
            baseline_done = db.get_state(conn, f"nulmeting_cjb_{store}", False)
            known = {r["id"] for r in conn.execute("SELECT id FROM products WHERE store = ?", (store,))}
            fresh = [p for p in products if p["id"] not in known]
            rows = []
            new_relevant = 0
            for p in fresh:
                # Bij de nulmeting is niets nieuw, dus beoordelen is niet nodig (scheelt een minuut).
                relevant = baseline_done and is_snack_product(p["name"])
                is_new = int(baseline_done)
                new_relevant += is_new and relevant
                rows.append((p["id"], p["store"], p["name"], p["size"], p["price"], p["url"],
                             now, now, is_new, int(relevant)))
            conn.executemany(
                "INSERT OR IGNORE INTO products(id, store, name, size, price, url, first_seen, "
                "last_seen, is_new, relevant) VALUES (?,?,?,?,?,?,?,?,?,?)", rows)
            conn.execute("UPDATE products SET last_seen = ? WHERE store = ? AND demo = 0", (now, store))
            db.set_state(conn, f"nulmeting_cjb_{store}", True)
            if baseline_done:
                status[store] = {"ok": True, "t": now, "producten": len(products),
                                 "melding": f"{len(products)} producten, {len(fresh)} nieuw "
                                            f"({new_relevant} snack-relevant)"}
                summary.append(f"{store} {len(fresh)} ({new_relevant})")
            else:
                status[store] = {"ok": True, "t": now, "producten": len(products),
                                 "melding": f"{len(products)} producten vastgelegd (nulmeting)"}
                summary.append(f"{store} nulmeting")
        db.set_state(conn, "supermarkt_status", status)
    run.note("Supermarkten (nieuw, waarvan snack-relevant): " + ", ".join(summary))


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
        names = ", ".join(("#" if a["kind"] == "hashtag" else "@") + a["value"] for a in act[:6])
        run.note(f"Ontdekt: {len(added)} nieuwe bronnen, {len(act)} direct actief"
                 + (f" ({names})" if names else ""))


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
                step_snackspert(run)
                step_discovery(run, settings)
        except Exception as exc:  # noqa: BLE001 - ronde altijd netjes afsluiten
            log.exception("Ophaalronde mislukt")
            run.note(f"Ronde afgebroken: {exc}", "fout")
        run.finish()
        return {"id": run.id, "results": run.results, "new": run.new_posts}
    finally:
        _run_lock.release()


def demo_active(conn) -> bool:
    """Demomodus zolang er geen enkele echte databron is ingesteld."""
    if config.secret("TRENDRADAR_DEMO") == "1":
        return True
    return not (apify.available() or meta_graph.available())


def last_run(conn) -> dict | None:
    r = conn.execute("SELECT * FROM runs ORDER BY started_at DESC, id DESC LIMIT 1").fetchone()
    return db.row_to_dict(r) if r else None


def due(conn, settings: dict) -> bool:
    r = conn.execute("SELECT started_at FROM runs WHERE status != 'bezig' ORDER BY started_at DESC, id DESC LIMIT 1").fetchone()
    if not r:
        return True
    return db.now() - db.parse_iso(r["started_at"]) >= timedelta(hours=settings["interval_uren"])

