"""Vult de bronnenlijst automatisch aan en ruimt hem op.

Toevoegen: hashtags en accounts die de afgelopen 7 dagen in meerdere relevante
Nederlandse posts opduiken, van verschillende makers. Hashtags en makers uit
posts die viraal gaan (zie signals.py) gaan altijd voor, ook bij één maker.
Gewone kandidaten scoren maximaal 15, virale minimaal 20.
Opruimen: bronnen die structureel weinig relevants opleveren gaan op pauze;
accounts die twee keer niets teruggeven worden 'ongeldig'.
Handmatig toegevoegde bronnen worden nooit automatisch gepauzeerd.
"""
from __future__ import annotations

import json
from collections import defaultdict
from datetime import timedelta

from . import db, lexicon, signals, trends
from .classify import _is_food_word, norm
from .classify import looks_like_business

MIN_REL = 0.5
MIN_NL = 0.5


def _known(conn) -> set[tuple[str, str, str]]:
    return {(r["platform"], r["kind"], r["value"]) for r in conn.execute(
        "SELECT platform, kind, value FROM sources")}


_PLACES = ({norm(c).replace(" ", "") for c in lexicon.CITIES}
           | {norm(t).replace(" ", "") for t in lexicon.NL_TOWNS})
_STORES = {norm(h).replace(" ", "") for hints in lexicon.SUPERMARKETS.values() for h in hints
           if len(h.strip("# ")) > 3} | {norm(s).replace(" ", "") for s in lexicon.SUPERMARKETS}


# Geen eten, maar voor Snackspert wel precies goed (#foodtruckfestival, #streetfoodrotterdam).
STREETFOOD_STEMS = ("foodtruck", "streetfood", "foodhall", "foodmarkt", "foodmarket",
                    "foodfestival", "eetfestival", "foodspot", "snackbar", "frituur", "cafetaria")


def acceptable_hashtag(tag: str, viral: bool = False) -> bool:
    """Mag deze hashtag een bron worden?

    Niet: algemene tags (#herfst, #deals), brede zoektags die we al gebruiken
    (#snackbar), plaatsnamen (#groningen) en winkelnamen (#albertheijn). Daarnaast
    moet een gewone kandidaat over eten gaan (#birriatacos wel, #kapper niet).
    Uit een virale post mag ook een onbekend woord komen: juist een nieuwe snack
    staat nog niet in de woordenlijst.
    """
    if len(tag) < 4 or tag.isdigit() or tag in trends.BROAD_HASHTAGS:
        return False
    if tag in _PLACES or tag in _STORES or tag in lexicon.HAIR_WORDS:
        return False
    if any(place in tag for place in _PLACES if len(place) >= 6) and not _is_food_word(tag):
        return False
    return viral or _is_food_word(tag) or any(stem in tag for stem in STREETFOOD_STEMS)


def prune_bad_hashtags(conn) -> list[str]:
    """Ruim eerder ontdekte hashtags op die niet (meer) door de keuring komen."""
    removed = []
    for s in conn.execute("SELECT id, value, reason FROM sources WHERE origin = 'ontdekt' "
                          "AND kind = 'hashtag' AND status IN ('actief', 'kandidaat')").fetchall():
        reason = s["reason"] or ""
        viral = "virale" in reason or "viraal" in reason
        if not acceptable_hashtag(s["value"], viral):
            conn.execute("UPDATE sources SET status = 'afgewezen', reason = ? WHERE id = ?",
                         ("te algemeen of niet over eten (automatisch opgeruimd)", s["id"]))
            removed.append(s["value"])
    return removed


def candidates(conn, days: int = 7) -> list[dict]:
    since = db.iso(db.now() - timedelta(days=days))
    rows = conn.execute(
        "SELECT platform, author, hashtags, mentions, relevance FROM posts "
        "WHERE posted_at >= ? AND relevance >= ? AND nl_score >= ? AND platform != 'nieuws'",
        (since, MIN_REL, MIN_NL)).fetchall()
    known = _known(conn)

    tags = defaultdict(lambda: {"authors": set(), "posts": 0, "rel": 0.0})
    authors = defaultdict(lambda: {"posts": 0, "rel": 0.0})
    mentions = defaultdict(lambda: {"authors": set(), "posts": 0})
    for r in rows:
        p = r["platform"]
        author = r["author"] or ""
        for t in json.loads(r["hashtags"] or "[]"):
            if not acceptable_hashtag(t):
                continue
            d = tags[(p, t)]
            d["authors"].add(author)
            d["posts"] += 1
            d["rel"] += r["relevance"]
        if author and p in ("instagram", "tiktok", "facebook"):
            authors[(p, author)]["posts"] += 1
            authors[(p, author)]["rel"] += r["relevance"]
        for m in json.loads(r["mentions"] or "[]"):
            if m != author:
                mentions[(p, m)]["authors"].add(author)
                mentions[(p, m)]["posts"] += 1

    out = []
    for (p, t), d in tags.items():
        if (p, "hashtag", t) in known or p == "facebook":
            continue
        n_auth = len(d["authors"])
        if n_auth >= 3 or (n_auth >= 2 and d["posts"] >= 4):
            avg = d["rel"] / d["posts"]
            out.append({"platform": p, "kind": "hashtag", "value": t,
                        "score": round(min(15, n_auth * avg), 2),
                        "reason": f"in {d['posts']} relevante posts van {n_auth} makers"})
    for (p, a), d in authors.items():
        if (p, "account", a) in known or d["posts"] < 2:
            continue
        avg = d["rel"] / d["posts"]
        out.append({"platform": p, "kind": "account", "value": a,
                    "score": round(min(15, d["posts"] * avg * 1.2), 2),
                    "reason": f"plaatste {d['posts']} relevante posts"})
    for (p, m), d in mentions.items():
        if (p, "account", m) in known or p == "facebook":
            continue
        n_auth = len(d["authors"])
        if n_auth >= 2 and d["posts"] >= 3:
            bonus = 1.5 if looks_like_business(m) else 1.0
            out.append({"platform": p, "kind": "account", "value": m,
                        "score": round(min(15, n_auth * bonus), 2),
                        "reason": f"genoemd in {d['posts']} posts door {n_auth} makers"})
    out += breakout_candidates(conn, known)
    out += topic_searches(conn, known)
    # Eén ontdekking per (platform, soort, waarde), hoogste score wint.
    best: dict = {}
    for c in out:
        key = (c["platform"], c["kind"], c["value"])
        if key not in best or c["score"] > best[key]["score"]:
            best[key] = c
    return sorted(best.values(), key=lambda c: c["score"], reverse=True)


def breakout_candidates(conn, known: set, days: int = 3) -> list[dict]:
    """Hashtags en makers uit posts die viraal gaan, ook als het maar één maker is.

    Juist de onbekende maker die met één video over een snack ontploft, wil je
    als eerste zien. Deze kandidaten krijgen daarom een hoge score en gaan voor.
    """
    base = signals.baselines(conn)
    since = db.iso(db.now() - timedelta(days=days))
    out = []
    rows = conn.execute(
        "SELECT * FROM posts WHERE posted_at >= ? AND relevance >= ? AND nl_score >= ? "
        "AND platform IN ('instagram', 'tiktok') AND views > 0", (since, MIN_REL, MIN_NL))
    for p in rows:
        sig = signals.of_post(p, base)
        if not sig["breakout"]:
            continue
        who = f"@{p['author']}" if p["author"] else "een maker"
        why = f"{sig['views_x']:g}× views" if sig["views_x"] else "veel views"
        if sig["small_creator"] and (sig["reach_x"] or 0) >= 3:
            why += f", bereik {sig['reach_x']:g}× het aantal volgers"
        score = 20 + min(30, sig["views_x"] or 0)
        for t in json.loads(p["hashtags"] or "[]"):
            if not acceptable_hashtag(t, viral=True):
                continue
            if (p["platform"], "hashtag", t) not in known:
                out.append({"platform": p["platform"], "kind": "hashtag", "value": t, "score": score,
                            "reason": f"uit virale post van {who} ({why})"})
        if p["author"] and sig["small_creator"] and (p["platform"], "account", p["author"]) not in known:
            out.append({"platform": p["platform"], "kind": "account", "value": p["author"],
                        "score": score - 5, "reason": f"kleine maker ging viraal ({why})"})
    return out


def topic_searches(conn, known: set, limit: int = 3) -> list[dict]:
    """Stijgende onderwerpen worden een TikTok-zoekopdracht.

    Duikt 'frikandelijs' op bij een paar makers, dan zoekt de tool de volgende
    ronde op TikTok naar 'frikandelijs'. Zo vind je de andere vroege video's
    erover, voordat het onderwerp groot is. Levert de zoekopdracht niets op,
    dan gaat hij vanzelf op pauze.
    """
    out = []
    for t in trends.compute(conn, "24u", limit=40)["topics"]:
        if t["type"] not in ("woord", "zin", "product") or t["phase"] not in ("vroeg", "groeit"):
            continue
        if t["authors"] < 2:
            continue
        query = t["name"].lower().strip()
        if ("tiktok", "zoekterm", query) in known:
            continue
        out.append({"platform": "tiktok", "kind": "zoekterm", "value": query,
                    "score": 18 + min(5, t["authors"]),
                    "reason": f"stijgend onderwerp ({t['authors']} makers): zoek meer video's"})
        if len(out) >= limit:
            break
    return out


def run(conn, settings: dict, demo: bool = False) -> list[dict]:
    """Voegt ontdekte bronnen toe. Geeft de toegevoegde terug."""
    found = candidates(conn)
    auto = settings.get("auto_toevoegen", True)
    cap = settings.get("max_nieuwe_bronnen_per_run", 6)
    max_active = settings.get("max_actieve_bronnen_per_platform", 60)
    active = {r["platform"]: r["n"] for r in conn.execute(
        "SELECT platform, COUNT(*) AS n FROM sources WHERE status = 'actief' GROUP BY platform")}
    added = []
    now = db.iso(db.now())
    for c in found:
        activate = auto and len([a for a in added if a["status"] == "actief"]) < cap \
            and active.get(c["platform"], 0) < max_active
        status = "actief" if activate else "kandidaat"
        conn.execute(
            "INSERT OR IGNORE INTO sources(platform, kind, value, status, origin, reason, "
            "priority, added_at, demo) VALUES (?, ?, ?, ?, 'ontdekt', ?, ?, ?, ?)",
            (c["platform"], c["kind"], c["value"], status, c["reason"],
             1.0 + min(c["score"], 10) / 10, now, int(demo)))
        if activate:
            active[c["platform"]] = active.get(c["platform"], 0) + 1
        added.append(dict(c, status=status))
        if len(added) >= cap * 3:
            break
    return added


def update_source_stats(conn, source_id: int, results: int, relevant: int,
                        new: int | None = None, new_relevant: int | None = None,
                        cost_usd: float = 0.0, interval_h: float = 6) -> None:
    """Werk de cijfers van een bron bij na een ophaalronde.

    Opbrengst = aandeel *nieuwe* relevante posts per betaald resultaat: een bron
    die steeds dezelfde posts teruggeeft, kost geld maar levert niets op.
    Daarnaast bepalen we wanneer ophalen weer zin heeft: een bron die weinig
    nieuws oplevert, komt pas na 2 of 4 rondes weer aan de beurt.
    """
    s = conn.execute("SELECT * FROM sources WHERE id = ?", (source_id,)).fetchone()
    if not s:
        return
    useful = relevant if new_relevant is None else new_relevant
    ratio = useful / results if results else 0.0
    yield_ = ratio if s["yield_score"] is None else round(0.6 * s["yield_score"] + 0.4 * ratio, 3)
    streak = 0 if results else (s["empty_streak"] or 0) + 1
    status, reason = s["status"], s["reason"]
    if s["origin"] != "handmatig":
        if s["kind"] == "account" and streak >= 2:
            status, reason = "ongeldig", "twee rondes zonder resultaat (bestaat niet of is privé?)"
        elif (s["fetch_count"] or 0) + 1 >= 3 and yield_ < 0.15 and results:
            status, reason = "gepauzeerd", f"levert weinig nieuws en relevants op ({yield_:.0%})"
    new_ratio = (new / results) if (new is not None and results) else (1.0 if results else 0.0)
    rounds = 1 if new_ratio >= 0.3 else 2 if new_ratio >= 0.1 else 4
    next_due = db.iso(db.now() + timedelta(hours=interval_h * rounds - 0.5))
    conn.execute(
        "UPDATE sources SET last_fetched = ?, fetch_count = fetch_count + 1, last_results = ?, "
        "last_relevant = ?, yield_score = ?, empty_streak = ?, status = ?, reason = ?, "
        "last_error = NULL, next_due = ?, last_new = ?, cost_usd = cost_usd + ?, "
        "useful_total = useful_total + ? WHERE id = ?",
        (db.iso(db.now()), results, relevant, yield_, streak, status, reason, next_due,
         new if new is not None else results, cost_usd, useful, source_id))
