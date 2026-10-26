"""Trefkans: welke tips van de tool heb je gepost, en hoe deden die het?

Bij elke ophaalronde schrijft de tool op wat hij je aanraadt (kandidaten op
Vandaag, de top van de Viral-potentie, de testlijst uit de supermarkt), met de
redenen erbij. Importeer je later je eigen posts, dan zoekt hij welke van die
tips je echt hebt gepost en hoe die posts liepen. Zo leert hij welke soort
signalen bij jóu werken (een combinatie, een doorbraak, een eigen creatie) en
telt hij die op Vandaag iets zwaarder of lichter mee.
"""
from __future__ import annotations

import json
import re
from collections import defaultdict
from statistics import median

from . import classify, db, taste

MIN_HITS = 3  # pas vanaf drie geposte tips met hetzelfde signaal zegt het iets

# Reden (zoals de tool hem toont) -> soort signaal
SIGNALS = [("Nieuw op de kaart", "nieuw op de kaart"), ("Combinatie", "combinatie"), ("Twist", "twist"),
           ("Doorbraak", "doorbraak"), ("Past bij jou", "past bij jou"), ("Jouw publiek", "jouw publiek"),
           ("Eigen creatie", "eigen creatie"), ("Variant", "variant"), ("Opvallend", "spektakel"),
           ("Vaker getipt", "getipt"), ("Nu al posts", "radar"), ("Herkenbare snack", "herkenbare snack")]


def signal_of(reason: str) -> str | None:
    if re.search(r"\d+(?:[.,]\d+)?× views", reason):
        return "veel views"
    if "× gedeeld" in reason:
        return "veel gedeeld"
    return next((s for prefix, s in SIGNALS if reason.startswith(prefix)), None)


def _terms_zaak(name: str) -> list[str]:
    key = taste.zaak_key(name)
    return [key] if len(key) >= 8 else []


def _terms_words(text: str) -> list[str]:
    return [w for w in classify.norm(text).split() if len(w) >= 4][:4]


def log(conn, kind: str, key: str, label: str, terms: list[str], reasons: list[str]) -> None:
    """Onthoud een tip (één keer; de eerste datum telt)."""
    if not key or not terms:
        return
    signals = sorted({s for r in reasons if (s := signal_of(r))})
    conn.execute("INSERT INTO suggestions(key, kind, label, terms, signals, first_at) VALUES (?, ?, ?, ?, ?, ?) "
                 "ON CONFLICT(key) DO NOTHING",
                 (key, kind, label[:200], json.dumps(terms), json.dumps(signals), db.iso(db.now())))


def log_round(conn, include_demo: bool = False) -> int:
    """Leg vast wat de tool deze ronde aanraadt."""
    from . import potential, products, trends

    before = conn.execute("SELECT COUNT(*) FROM suggestions").fetchone()[0]
    for c in trends.candidates(conn, 72, None, include_demo, 12):
        p = conn.execute("SELECT text, author, places, flags FROM posts WHERE id = ?", (c["id"],)).fetchone()
        if not p:
            continue
        flags = json.loads(p["flags"] or "[]")
        subject = next((f.split(":", 1)[1] for f in flags if f.startswith(("combinatie:", "twist:"))), None)
        places = json.loads(p["places"] or "[]")
        if subject:
            log(conn, "kandidaat", f"zin:{subject.lower()}", subject, _terms_words(subject), c["reasons"])
        for place in places[:1]:
            log(conn, "kandidaat", f"zaak:{taste.zaak_key(place)}", place.lstrip("@"), _terms_zaak(place), c["reasons"])
    for t in potential.ranking(conn, 25, include_demo)["top"]:
        log(conn, "potentie", f"zaak:{taste.zaak_key(t['name'])}", t["name"], _terms_zaak(t["name"]),
            [r["text"] for r in t["reasons"]])
    for i in products.test_ideas(conn, include_demo, 10):
        log(conn, "testlijst", f"product:{classify.norm(i['name'])}", i["name"], _terms_words(i["name"]),
            i["reasons"] + ["Testlijst"])
    return conn.execute("SELECT COUNT(*) FROM suggestions").fetchone()[0] - before


def _posted(sug: dict, posts: list[dict]) -> dict | None:
    """De eerste eigen post na de tip waarin alle zoektermen voorkomen."""
    after = sug["first_at"][:10]
    for p in posts:
        when = p["date"] or (p["month"] + "-31" if p["month"] else "")
        if when < after:
            continue
        if sug["key"].startswith("zaak:"):
            if all(t in p["_blob"] for t in sug["terms"]):
                return p
        elif all(t in p["_text"] for t in sug["terms"]):
            return p
    return None


def report(conn) -> dict:
    sugs = [dict(r) for r in conn.execute("SELECT * FROM suggestions ORDER BY first_at")]
    for s in sugs:
        s["terms"] = json.loads(s["terms"])
        s["signals"] = json.loads(s["signals"])
    posts = sorted((dict(r) for r in conn.execute("SELECT * FROM own_posts")),
                   key=lambda p: p["date"] or p["month"] or "")
    for p in posts:
        text = classify.norm(p["caption"] or "")
        p["_text"] = text
        p["_blob"] = text.replace(" ", "") + " " + " ".join(m.lower() for m in classify.extract_mentions(p["caption"] or ""))
    overall = median([p["views"] or 0 for p in posts]) if posts else 0
    hits = []
    for s in sugs:
        p = _posted(s, posts)
        if p:
            hits.append({"label": s["label"], "kind": s["kind"], "signals": s["signals"], "since": s["first_at"],
                         "views": p["views"] or 0, "date": p["date"] or p["month"], "url": p["url"],
                         "followers": p["followers"] if p["followers_count"] else None})
    per = defaultdict(list)
    for h in hits:
        for sig in h["signals"]:
            per[sig].append(h["views"])
    signals = sorted(({"signal": k, "hits": len(v), "lift": round(median(v) / overall, 2) if overall else None}
                      for k, v in per.items()), key=lambda x: (-x["hits"], x["signal"]))
    return {"suggested": len(sugs), "posted": len(hits), "median_views": round(overall),
            "hit_median": round(median([h["views"] for h in hits])) if hits else None,
            "signals": signals, "hits": sorted(hits, key=lambda h: h["date"] or "", reverse=True)[:15],
            "since": sugs[0]["first_at"] if sugs else None}


def learned_lifts(conn) -> dict[str, float]:
    """{signaal: lift} voor signalen met genoeg geposte tips; gebruikt door Vandaag."""
    return {s["signal"]: s["lift"] for s in report(conn)["signals"] if s["hits"] >= MIN_HITS and s["lift"]}
