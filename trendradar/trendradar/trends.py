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

from . import db, lexicon, ownposts, seeds, signals, taste, trefkans
from .classify import norm

WINDOWS = {
    "nu": {"hours": 6, "baseline": 4, "bucket_h": 1, "label": "Nu (6 uur)"},
    "24u": {"hours": 24, "baseline": 6, "bucket_h": 6, "label": "24 uur"},
    "3d": {"hours": 72, "baseline": 2, "bucket_h": 12, "label": "3 dagen"},
    "7d": {"hours": 168, "baseline": 1, "bucket_h": 24, "label": "7 dagen"},
}

TOPIC_TYPES = {
    "categorie": "Gerecht", "merk": "Merk/winkel",
    "product": "Product", "zaak": "Zaak", "stad": "Stad", "zin": "Woordcombinatie",
    "woord": "Nieuw woord",
}

MIN_AUTHORS = {"zin": 3, "woord": 2, "product": 1, "merk": 2, "zaak": 1,
               "categorie": 1, "stad": 2}


def engagement(p) -> float:
    return (p["likes"] or 0) + 2 * (p["comments"] or 0) + 3 * (p["shares"] or 0) + (p["views"] or 0) / 50


def _filters(platform: str | None, min_rel: float, min_nl: float, include_demo: bool,
             city: str | None = None):
    where = ["relevance >= ?", "nl_score >= ?"]
    args: list = [min_rel, min_nl]
    if city:
        where.append("city = ?")
        args.append(city)
    if platform:
        where.append("platform = ?")
        args.append(platform)
    if not include_demo:
        where.append("demo = 0")
    return where, args


def load_posts(conn, start, end, platform=None, min_rel=0.35, min_nl=0.4, include_demo=True,
               city=None):
    where, args = _filters(platform, min_rel, min_nl, include_demo, city)
    where += ["posted_at >= ?", "posted_at < ?"]
    args += [db.iso(start), db.iso(end)]
    return conn.execute(f"SELECT * FROM posts WHERE {' AND '.join(where)}", args).fetchall()


PHASES = {
    "vroeg": "🌱 Vroeg",
    "groeit": "📈 Groeit",
    "piek": "🔥 Piek",
    "over": "📉 Over hoogtepunt",
}


def phase(t: dict) -> str:
    """In welke fase zit de hype? Zo zie je of je er nog als eerste bij bent.

    vroeg   een paar makers, nog geen nieuws: hier kun jij het verschil maken
    groeit  steeds meer makers, hooguit één nieuwsbericht
    piek    meerdere nieuwsberichten of heel veel makers: iedereen heeft het erover
    over    minder posts dan in de periodes ervoor
    """
    if t["growth_pct"] is not None and t["growth_pct"] <= -20:
        return "over"
    if t["news"] >= 2 or t["authors"] >= 15:
        return "piek"
    if t["authors"] <= 3 and t["news"] == 0:
        return "vroeg"
    return "groeit"


def candidates(conn, hours: int = 72, city: str | None = None, include_demo: bool = True,
               limit: int = 12) -> list[dict]:
    """Posts die het waard zijn om naar te kijken: de 'kleine viral' die jij kunt uitvergroten.

    Telt mee: een nieuwe creatie van een zaak (nieuw op de kaart), een
    combinatie die je nog niet kent, en signalen dat een post het ver boven
    normaal doet. Hoe meer van die dingen samen, hoe hoger.
    """
    since = db.now() - timedelta(hours=hours)
    base = signals.baselines(conn, include_demo=include_demo)
    # Wat je al bewaard hebt, hoef je niet nog eens te zien; wat erop lijkt wel.
    prof = taste.profile(conn)
    seen = {r["ref"] for r in conn.execute("SELECT ref FROM watchlist WHERE kind = 'post'")} | taste.rated(conn)
    # Je eigen posts: welke snacks doen het goed bij jouw publiek, en wie heb je al gepost?
    lifts = ownposts.lifts(conn)
    learned = trefkans.learned_lifts(conn)
    posted = {taste.zaak_key(h): v for h, v in ownposts.posted_handles(conn).items()}
    captions = ownposts.caption_index(conn)
    scored = []
    for p in load_posts(conn, since, db.now() + timedelta(minutes=1), None, 0.5, 0.4,
                        include_demo, city):
        if p["platform"] == "nieuws" or p["id"] in seen:
            continue
        flags = json.loads(p["flags"] or "[]") if "flags" in p.keys() else []
        sig = signals.of_post(p, base)
        reasons, score = [], 0.0
        if "nieuw_op_kaart" in flags:
            score += 3
            reasons.append("Nieuw op de kaart")
        combo = next((f.split(":", 1)[1] for f in flags if f.startswith("combinatie:")), None)
        if combo:
            score += 3
            reasons.append(f"Combinatie: {combo}")
        twist = next((f.split(":", 1)[1] for f in flags if f.startswith("twist:")), None)
        if twist:
            score += 2
            reasons.append(f"Twist: {twist}")
        if sig["breakout"]:
            score += 3
            reasons.append("Doorbraak")
        if (sig["views_x"] or 0) >= 2:
            score += min(3.0, math.log2(sig["views_x"]))
            reasons.append(f"{sig['views_x']:g}× views")
        if (sig["shares_x"] or 0) >= 2:
            score += 1
            reasons.append(f"{sig['shares_x']:g}× gedeeld")
        if sig["small_creator"] and score:
            score += 0.5
            reasons.append(f"kleine maker ({sig['followers']} volgers)")
        feats = taste.post_features(p, prof)
        bonus, alike, strong = taste.match(prof, feats)
        # Alleen 'past bij jou' is genoeg als het specifiek is (een zin, twist, zaak of maker).
        if bonus > 0 and (score or strong >= 1.5):
            score += bonus
            reasons.append("Past bij jou: " + ", ".join(alike))
        elif bonus < 0:
            score += bonus
        if score <= 0:
            continue
        # Trefkans: signalen die bij jouw eerdere posts goed (of slecht) uitpakten.
        for sig in {s for r in reasons if (s := trefkans.signal_of(r))}:
            lift = learned.get(sig)
            if lift and abs(lift - 1) >= 0.1:
                score += max(-1.0, min(1.0, (lift - 1) * 1.5))
                if lift > 1:
                    reasons.append(f"Werkte bij jou: {sig} {str(lift).replace('.', ',')}×")
        best = max((lifts[f[6:]] | {"snack": f[6:]} for f in feats if f.startswith("snack:") and f[6:] in lifts),
                   key=lambda x: x["lift"], default=None)
        if best and best["lift"] >= 1.15:
            score += min(1.5, (best["lift"] - 1) * 3)
            reasons.append(f"Jouw publiek: {best['snack']} {str(best['lift']).replace('.', ',')}× je mediaan")
        zaken = [taste.zaak_key(p["author"] or "")] + [f[5:] for f in feats if f.startswith("zaak:")]
        done = next((posted[k] for k in zaken if k and k in posted), None) or next(
            (hit for k in zaken if len(k) >= 10 for hit in [ownposts.find_posted(k, captions)] if hit), None)
        if done:
            score -= 1
            reasons.append(f"Al gepost op {done['date']}")
        age_h = (db.now() - db.parse_iso(p["posted_at"])).total_seconds() / 3600
        score += 1 if age_h < 24 else 0
        phrases = json.loads(p["phrases"] or "[]")
        subject = combo or twist or (phrases[0] if phrases else p["id"])
        scored.append((score, p, reasons, sig, subject))
    scored.sort(key=lambda x: x[0], reverse=True)
    # Spreiding: maximaal 2 posts per maker en per onderwerp, anders vult één
    # hype de hele lijst.
    out, per_author, per_subject = [], defaultdict(int), defaultdict(int)
    for score, p, reasons, sig, subject in scored:
        who = (p["platform"], p["author"] or p["id"])
        if per_author[who] >= 2 or per_subject[subject] >= 2:
            continue
        per_author[who] += 1
        per_subject[subject] += 1
        out.append({"id": p["id"], "score": round(score, 2), "reasons": reasons, "signals": sig})
        if len(out) >= limit:
            break
    return out


def _words(name: str) -> list[str]:
    return norm(name.lstrip("@").replace("_", " ")).split()


def _broad_hashtags() -> set[str]:
    """Brede hashtags (#snackbar, #frikandel): een zoeknet, nooit een nieuwe bron.

    Hashtags zijn in de trendradar geen onderwerp. Deze lijst gebruikt
    discovery.py om te bepalen welke ontdekte hashtags het volgen waard zijn.
    """
    words = {w for kws in lexicon.CATEGORIES.values() for w in kws if " " not in w}
    foods = {f.replace(" ", "") for f in lexicon.DUTCH_FOODS}
    starts = set(seeds.INSTAGRAM_HASHTAGS) | set(seeds.TIKTOK_HASHTAGS) | set(seeds.AMSTERDAM_HASHTAGS)
    return lexicon.GENERIC_HASHTAGS | words | foods | starts


BROAD_HASHTAGS = _broad_hashtags()


def topics_of(p) -> list[tuple[str, str]]:
    # Hashtags zijn geen onderwerp: ze dienen om posts en accounts te vinden.
    # Wat in de post staat (product, zaak, woordcombinatie) is het onderwerp.
    out = []
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
        out.append(("zin" if " " in z else "woord", z))
    return list(dict.fromkeys(out))


def compute(conn, window: str = "24u", platform: str | None = None, limit: int = 40,
            min_rel: float = 0.35, min_nl: float = 0.4, include_demo: bool = True,
            city: str | None = None) -> dict:
    w = WINDOWS[window]
    now = db.now()
    span = timedelta(hours=w["hours"])
    cur_start = now - span
    base_start = cur_start - span * w["baseline"]
    posts = load_posts(conn, base_start, now, platform, min_rel, min_nl, include_demo, city)

    n_buckets = int(w["hours"] * (w["baseline"] + 1) / w["bucket_h"])
    bucket_span = timedelta(hours=w["bucket_h"])

    stats = defaultdict(lambda: {"cur": 0, "base": 0, "eng": 0.0, "authors": set(),
                                 "base_authors": set(), "platforms": set(),
                                 "series": [0] * n_buckets, "posts": [], "sigs": [],
                                 "news": 0})
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
                s["news"] += p["platform"] == "nieuws"
            else:
                s["base"] += 1
                s["base_authors"].add(author)

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
        rows.append({
            "type": kind,
            "type_label": TOPIC_TYPES[kind],
            "name": name,
            "posts": s["cur"],
            "baseline": round(base_avg, 2),
            "growth_pct": None if base_avg == 0 else round((s["cur"] / base_avg - 1) * 100),
            "new": s["base"] == 0,
            "authors": n_auth,
            "authors_baseline": round(base_auth, 1),
            "engagement": round(s["eng"]),
            "signals": summary,
            "platforms": sorted(s["platforms"]),
            "series": s["series"],
            "score": round(score, 3),
            "top_posts": [pid for _, pid in sorted(s["posts"], reverse=True)[:3]],
            "news": s["news"],
        })
        rows[-1]["phase"] = phase(rows[-1])
    # Woordcombinaties die al in een product-, zaak- of merknaam zitten ("kapsalon
    # chips" bij "Smaakmakers Kapsalon Chips"), of uit precies dezelfde posts komen
    # ("birria taco", "taco gespot"): houd er één.
    named = [set(_words(r["name"])) for r in rows if r["type"] in ("product", "zaak", "merk")]
    seen_sets = set()
    kept = []
    # Bij gelijke score wint de leesbare woordcombinatie ('pistache kroket' boven 'pistachekroket').
    for r in sorted(rows, key=lambda r: (r["score"], r["type"] == "zin"), reverse=True):
        if r["type"] in ("zin", "woord"):
            if any(set(_words(r["name"])) <= n for n in named):
                continue
            # 'kapsalonchips' hoort bij het product 'Smaakmakers Kapsalon Chips'.
            if r["type"] == "woord" and any(r["name"] in "".join(_words(p["name"])) for p in rows
                                            if p["type"] in ("product", "zaak", "merk")):
                continue
            # 'birria tacos', 'birria taco' en 'birriataco' zijn hetzelfde.
            stem = "".join(w[:-1] if len(w) > 4 and w.endswith("s") else w for w in _words(r["name"]))
            stem = stem[:-1] if stem.endswith("s") else stem
            fingerprint = (r["posts"], r["authors"], r["engagement"])
            if fingerprint in seen_sets or stem in seen_sets:
                continue
            seen_sets.update({fingerprint, stem})
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
        "phases": PHASES,
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


def volume(conn, window: str, platform: str | None = None, min_rel=0.35, min_nl=0.4,
           include_demo=True, city: str | None = None) -> dict:
    """Aantal relevante posts per platform per tijdsblok (voor de lijngrafiek)."""
    w = WINDOWS[window]
    now = db.now()
    span = timedelta(hours=w["hours"])
    start = now - span * (w["baseline"] + 1)
    n = int(w["hours"] * (w["baseline"] + 1) / w["bucket_h"])
    bucket = timedelta(hours=w["bucket_h"])
    series = defaultdict(lambda: [0] * n)
    for p in load_posts(conn, start, now, platform, min_rel, min_nl, include_demo, city):
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
