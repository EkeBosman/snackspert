"""Vult de bronnenlijst automatisch aan en ruimt hem op.

Toevoegen: hashtags en accounts die de afgelopen 7 dagen in meerdere relevante
Nederlandse posts opduiken, van verschillende makers.
Opruimen: bronnen die structureel weinig relevants opleveren gaan op pauze;
accounts die twee keer niets teruggeven worden 'ongeldig'.
Handmatig toegevoegde bronnen worden nooit automatisch gepauzeerd.
"""
from __future__ import annotations

import json
from collections import defaultdict
from datetime import timedelta

from . import db, lexicon
from .classify import looks_like_business

MIN_REL = 0.5
MIN_NL = 0.5


def _known(conn) -> set[tuple[str, str, str]]:
    return {(r["platform"], r["kind"], r["value"]) for r in conn.execute(
        "SELECT platform, kind, value FROM sources")}


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
            if len(t) < 4 or t.isdigit() or t in lexicon.GENERIC_HASHTAGS:
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
                        "score": round(n_auth * avg, 2),
                        "reason": f"in {d['posts']} relevante posts van {n_auth} makers"})
    for (p, a), d in authors.items():
        if (p, "account", a) in known or d["posts"] < 2:
            continue
        avg = d["rel"] / d["posts"]
        out.append({"platform": p, "kind": "account", "value": a,
                    "score": round(d["posts"] * avg * 1.2, 2),
                    "reason": f"plaatste {d['posts']} relevante posts"})
    for (p, m), d in mentions.items():
        if (p, "account", m) in known or p == "facebook":
            continue
        n_auth = len(d["authors"])
        if n_auth >= 2 and d["posts"] >= 3:
            bonus = 1.5 if looks_like_business(m) else 1.0
            out.append({"platform": p, "kind": "account", "value": m,
                        "score": round(n_auth * bonus, 2),
                        "reason": f"genoemd in {d['posts']} posts door {n_auth} makers"})
    # Eén ontdekking per (platform, soort, waarde), hoogste score wint.
    best: dict = {}
    for c in out:
        key = (c["platform"], c["kind"], c["value"])
        if key not in best or c["score"] > best[key]["score"]:
            best[key] = c
    return sorted(best.values(), key=lambda c: c["score"], reverse=True)


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


def update_source_stats(conn, source_id: int, results: int, relevant: int) -> None:
    s = conn.execute("SELECT * FROM sources WHERE id = ?", (source_id,)).fetchone()
    if not s:
        return
    ratio = relevant / results if results else 0.0
    yield_ = ratio if s["yield_score"] is None else round(0.6 * s["yield_score"] + 0.4 * ratio, 3)
    streak = 0 if results else (s["empty_streak"] or 0) + 1
    status, reason = s["status"], s["reason"]
    if s["origin"] != "handmatig":
        if s["kind"] == "account" and streak >= 2:
            status, reason = "ongeldig", "twee rondes zonder resultaat (bestaat niet of is privé?)"
        elif (s["fetch_count"] or 0) + 1 >= 3 and yield_ < 0.15 and results:
            status, reason = "gepauzeerd", f"levert weinig relevants op ({yield_:.0%})"
    conn.execute(
        "UPDATE sources SET last_fetched = ?, fetch_count = fetch_count + 1, last_results = ?, "
        "last_relevant = ?, yield_score = ?, empty_streak = ?, status = ?, reason = ?, "
        "last_error = NULL WHERE id = ?",
        (db.iso(db.now()), results, relevant, yield_, streak, status, reason, source_id))
