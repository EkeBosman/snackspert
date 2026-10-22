"""Trendberekening.

Een onderwerp (hashtag, gerecht, merk, product, zaak, stad of woordcombinatie)
is trending als het in de gekozen periode vaker voorkomt dan in de periodes
ervoor. Per periode:

    nu (6 uur)  vergeleken met het gemiddelde van de 4 blokken van 6 uur ervoor
    24 uur      vergeleken met het gemiddelde van de 6 dagen ervoor
    3 dagen     vergeleken met de 2 blokken van 3 dagen ervoor
    7 dagen     vergeleken met de week ervoor

Trendscore = log2(groei) x wortel(aantal verschillende makers)
           + een beetje gewicht voor interactie (likes, reacties, views).
Zo telt één account dat tien keer hetzelfde post niet als trend.
"""
from __future__ import annotations

import json
import math
from collections import defaultdict
from datetime import timedelta

from . import db, lexicon, seeds, signals

WINDOWS = {
    "nu": {"hours": 6, "baseline": 4, "bucket_h": 1, "label": "Nu (6 uur)"},
    "24u": {"hours": 24, "baseline": 6, "bucket_h": 6, "label": "24 uur"},
    "3d": {"hours": 72, "baseline": 2, "bucket_h": 12, "label": "3 dagen"},
    "7d": {"hours": 168, "baseline": 1, "bucket_h": 24, "label": "7 dagen"},
}

TOPIC_TYPES = {
    "hashtag": "Hashtag", "categorie": "Gerecht", "merk": "Merk/winkel",
    "product": "Product", "zaak": "Zaak", "stad": "Stad", "zin": "Woordcombinatie",
}

MIN_AUTHORS = {"hashtag": 2, "zin": 3, "product": 1, "merk": 2, "zaak": 1,
               "categorie": 1, "stad": 2}


def engagement(p) -> float:
    return (p["likes"] or 0) + 2 * (p["comments"] or 0) + 3 * (p["shares"] or 0) + (p["views"] or 0) / 50


def _filters(platform: str | None, min_rel: float, min_nl: float, include_demo: bool):
    where = ["relevance >= ?", "nl_score >= ?"]
    args: list = [min_rel, min_nl]
    if platform:
        where.append("platform = ?")
        args.append(platform)
    if not include_demo:
        where.append("demo = 0")
    return where, args


def load_posts(conn, start, end, platform=None, min_rel=0.35, min_nl=0.4, include_demo=True):
    where, args = _filters(platform, min_rel, min_nl, include_demo)
    where += ["posted_at >= ?", "posted_at < ?"]
    args += [db.iso(start), db.iso(end)]
    return conn.execute(f"SELECT * FROM posts WHERE {' AND '.join(where)}", args).fetchall()


def _broad_hashtags() -> set[str]:
    """Hashtags die een zoeknet zijn, geen trend.

    #snackbar of #frikandel is altijd populair; dat zegt niets. Ze dienen om
    posts te vinden, en wát er in die posts staat (een product, een zaak, een
    specifieke hashtag als #frikandelijs) kan wél een trend zijn.
    """
    words = {w for kws in lexicon.CATEGORIES.values() for w in kws if " " not in w}
    foods = {f.replace(" ", "") for f in lexicon.DUTCH_FOODS}
    starts = set(seeds.INSTAGRAM_HASHTAGS) | set(seeds.TIKTOK_HASHTAGS)
    return lexicon.GENERIC_HASHTAGS | words | foods | starts


BROAD_HASHTAGS = _broad_hashtags()


def topics_of(p) -> list[tuple[str, str]]:
    out = []
    for t in json.loads(p["hashtags"] or "[]"):
        if t not in BROAD_HASHTAGS and len(t) >= 3:
            out.append(("hashtag", "#" + t))
    for c in json.loads(p["categories"] or "[]"):
        out.append(("categorie", c))
    for b in json.loads(p["brands"] or "[]"):
        out.append(("merk", b))
    for prod in json.loads(p["products"] or "[]"):
        name = prod.get("naam") if isinstance(prod, dict) else str(prod)
        if name:
            out.append(("product", name.strip()))
    for place in json.loads(p["places"] or "[]"):
        out.append(("zaak", place))
    if p["city"]:
        out.append(("stad", p["city"]))
    for z in json.loads(p["phrases"] or "[]"):
        out.append(("zin", z))
    return list(dict.fromkeys(out))


def compute(conn, window: str = "24u", platform: str | None = None, limit: int = 40,
            min_rel: float = 0.35, min_nl: float = 0.4, include_demo: bool = True) -> dict:
    w = WINDOWS[window]
    now = db.now()
    span = timedelta(hours=w["hours"])
    cur_start = now - span
    base_start = cur_start - span * w["baseline"]
    posts = load_posts(conn, base_start, now, platform, min_rel, min_nl, include_demo)

    n_buckets = int(w["hours"] * (w["baseline"] + 1) / w["bucket_h"])
    bucket_span = timedelta(hours=w["bucket_h"])

    stats = defaultdict(lambda: {"cur": 0, "base": 0, "eng": 0.0, "authors": set(),
                                 "base_authors": set(), "platforms": set(),
                                 "series": [0] * n_buckets, "posts": [], "sigs": []})
    base_sig = signals.baselines(conn, include_demo=include_demo)
    cur_posts = 0
    cur_eng = 0.0
    cur_authors = set()
    breakout_posts = []
    for p in posts:
        t = db.parse_iso(p["posted_at"])
        idx = min(n_buckets - 1, max(0, int((t - base_start) / bucket_span)))
        is_cur = t >= cur_start
        eng = engagement(p)
        sig = None
        if is_cur:
            cur_posts += 1
            cur_eng += eng
            cur_authors.add((p["platform"], p["author"]))
            sig = signals.of_post(p, base_sig)
            sig["_views"] = p["views"] or 0
            if sig["breakout"]:
                breakout_posts.append((sig["reach_x"] or 0, sig["views_x"] or 0, p["id"], sig))
        for key in topics_of(p):
            s = stats[key]
            s["series"][idx] += 1
            author = (p["platform"], p["author"] or p["id"])
            if is_cur:
                s["cur"] += 1
                s["eng"] += eng
                s["authors"].add(author)
                s["platforms"].add(p["platform"])
                s["posts"].append((eng, p["id"]))
                s["sigs"].append(sig)
            else:
                s["base"] += 1
                s["base_authors"].add(author)

    first_seen = _first_seen(conn, include_demo)
    rows = []
    for (kind, name), s in stats.items():
        n_auth = len(s["authors"])
        if s["cur"] == 0:
            continue
        summary = signals.topic_summary(s["sigs"])
        # Eén onbekende maker die viraal gaat telt wél: dat is precies wat we
        # vroeg willen zien. Anders moeten meerdere makers het noemen.
        if n_auth < MIN_AUTHORS.get(kind, 1) and not summary["breakouts"]:
            continue
        base_avg = s["base"] / w["baseline"]
        base_auth = len(s["base_authors"]) / w["baseline"]
        growth = (s["cur"] + 1) / (base_avg + 1)
        score = (math.log2(growth) * math.sqrt(n_auth) + math.log10(1 + s["eng"]) * 0.4
                 + 0.6 * math.log2(max(1.0, summary["views_x"] or 1))
                 + 0.4 * math.log2(max(1.0, summary["shares_x"] or 1))
                 + min(3, summary["breakouts"]))
        fs = first_seen.get((kind, name))
        rows.append({
            "type": kind,
            "type_label": TOPIC_TYPES[kind],
            "name": name,
            "posts": s["cur"],
            "baseline": round(base_avg, 2),
            "growth_pct": None if base_avg == 0 else round((s["cur"] / base_avg - 1) * 100),
            "new": s["base"] == 0 and (fs is None or fs >= db.iso(cur_start)),
            "authors": n_auth,
            "authors_baseline": round(base_auth, 1),
            "engagement": round(s["eng"]),
            "signals": summary,
            "platforms": sorted(s["platforms"]),
            "series": s["series"],
            "score": round(score, 3),
            "top_posts": [pid for _, pid in sorted(s["posts"], reverse=True)[:3]],
        })
    # "pistache kroket" en "#pistachekroket" zijn hetzelfde onderwerp: toon het één keer.
    tag_names = {r["name"] for r in rows if r["type"] == "hashtag"}
    rows = [r for r in rows if not (r["type"] == "zin" and "#" + r["name"].replace(" ", "") in tag_names)]
    # Woordcombinaties uit precies dezelfde posts ("birria taco", "taco gespot"): houd er één.
    seen_sets = set()
    kept = []
    for r in sorted(rows, key=lambda r: r["score"], reverse=True):
        if r["type"] == "zin":
            fingerprint = (r["posts"], r["authors"], r["engagement"])
            if fingerprint in seen_sets:
                continue
            seen_sets.add(fingerprint)
        kept.append(r)
    rows = kept

    # Historie: hoe ver terug hebben we data? Te kort = baseline onbetrouwbaar.
    oldest = conn.execute("SELECT MIN(started_at) AS m FROM runs WHERE status != 'fout'").fetchone()["m"]
    history_h = (now - db.parse_iso(oldest)).total_seconds() / 3600 if oldest else 0
    needed_h = w["hours"] * (w["baseline"] + 1)

    return {
        "window": window,
        "label": w["label"],
        "start": db.iso(cur_start),
        "baseline_start": db.iso(base_start),
        "bucket_hours": w["bucket_h"],
        "n_buckets": n_buckets,
        "baseline_buckets": n_buckets - int(w["hours"] / w["bucket_h"]),
        "history_ok": history_h >= needed_h,
        "history_hours": round(history_h, 1),
        "needed_hours": needed_h,
        "totals": {"posts": cur_posts, "engagement": round(cur_eng), "makers": len(cur_authors),
                   "breakouts": len(breakout_posts)},
        "breakouts": _one_per_maker(conn, breakout_posts),
        "topics": rows[:limit],
        "new_topics": [r for r in rows if r["new"] and r["type"] != "categorie"][:15],
        "categories": sorted([r for r in rows if r["type"] == "categorie"],
                             key=lambda r: r["posts"], reverse=True),
        "cities": sorted([dict(r, coords=lexicon.CITIES.get(r["name"])) for r in rows
                          if r["type"] == "stad"], key=lambda r: r["posts"], reverse=True),
    }


def _one_per_maker(conn, breakout_posts: list, limit: int = 12) -> list[dict]:
    """De sterkste doorbraak per maker, met hoeveel virale posts die maker had."""
    best: dict = {}
    counts: dict = {}
    ranked = sorted(breakout_posts, key=lambda b: (b[0], b[1]), reverse=True)
    ids = [pid for _, _, pid, _ in ranked]
    authors = {}
    for i in range(0, len(ids), 500):
        chunk = ids[i:i + 500]
        authors.update({r["id"]: (r["platform"], r["author"] or r["id"]) for r in conn.execute(
            f"SELECT id, platform, author FROM posts WHERE id IN ({','.join('?' * len(chunk))})", chunk)})
    for _, _, pid, sig in ranked:
        who = authors.get(pid, pid)
        counts[who] = counts.get(who, 0) + 1
        best.setdefault(who, {"id": pid, "signals": sig})
    out = []
    for who, item in best.items():
        item["count"] = counts[who]
        out.append(item)
    return out[:limit]


def _first_seen(conn, include_demo: bool) -> dict:
    """Wanneer een hashtag voor het eerst in de database opdook (goedkope benadering)."""
    cache = {}
    q = "SELECT hashtags, MIN(posted_at) AS f FROM posts"
    if not include_demo:
        q += " WHERE demo = 0"
    q += " GROUP BY hashtags"
    for r in conn.execute(q):
        for t in json.loads(r["hashtags"] or "[]"):
            key = ("hashtag", "#" + t)
            if key not in cache or r["f"] < cache[key]:
                cache[key] = r["f"]
    return cache


def volume(conn, window: str, platform: str | None = None, min_rel=0.35, min_nl=0.4,
           include_demo=True) -> dict:
    """Aantal relevante posts per platform per tijdsblok (voor de lijngrafiek)."""
    w = WINDOWS[window]
    now = db.now()
    span = timedelta(hours=w["hours"])
    start = now - span * (w["baseline"] + 1)
    n = int(w["hours"] * (w["baseline"] + 1) / w["bucket_h"])
    bucket = timedelta(hours=w["bucket_h"])
    series = defaultdict(lambda: [0] * n)
    for p in load_posts(conn, start, now, platform, min_rel, min_nl, include_demo):
        idx = min(n - 1, max(0, int((db.parse_iso(p["posted_at"]) - start) / bucket)))
        series[p["platform"]][idx] += 1
    labels = [db.iso(start + bucket * i) for i in range(n)]
    return {"labels": labels, "series": dict(series), "current_from": n - int(w["hours"] / w["bucket_h"])}


def rising_posts(conn, hours: int = 24, limit: int = 10, include_demo=True) -> list[dict]:
    """Posts waarvan de interactie tussen twee ophaalrondes het hardst groeide."""
    since = db.iso(db.now() - timedelta(hours=hours))
    q = """
    SELECT p.*, s1.taken_at AS t1, s2.taken_at AS t2,
           (s2.likes + 2*s2.comments + 3*s2.shares + s2.views/50.0)
         - (s1.likes + 2*s1.comments + 3*s1.shares + s1.views/50.0) AS gained
    FROM posts p
    JOIN metric_snapshots s2 ON s2.post_id = p.id
    JOIN metric_snapshots s1 ON s1.post_id = p.id AND s1.taken_at < s2.taken_at
    WHERE s2.taken_at >= ? AND p.relevance >= 0.35 AND p.nl_score >= 0.4
      AND s2.taken_at = (SELECT MAX(taken_at) FROM metric_snapshots WHERE post_id = p.id)
      AND s1.taken_at = (SELECT MAX(taken_at) FROM metric_snapshots
                         WHERE post_id = p.id AND taken_at < s2.taken_at)
    """
    if not include_demo:
        q += " AND p.demo = 0"
    q += " ORDER BY gained DESC LIMIT ?"
    out = []
    for r in conn.execute(q, (since, limit)):
        d = db.row_to_dict(r)
        hrs = max(0.5, (db.parse_iso(r["t2"]) - db.parse_iso(r["t1"])).total_seconds() / 3600)
        d["gain_per_hour"] = round(r["gained"] / hrs, 1)
        out.append(d)
    return out
