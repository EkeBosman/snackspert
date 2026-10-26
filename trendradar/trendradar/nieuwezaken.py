"""Nieuwe zaken vinden via Google Maps, nog voordat ze op Instagram rondgaan.

Elke week zoekt de tool in een paar steden (op rij af) naar snackbars,
foodtrucks, streetfood en frituren. De eerste keer per zoekopdracht legt hij
vast wat er al is (de nulmeting). Een zaak die daarna voor het eerst opduikt,
met nog weinig reviews, is waarschijnlijk net open: die zie je bij Tips & routes.
Kosten: ongeveer 4 dollar per 1000 zaken, dus met 2 steden × 4 zoektermen × 30
zaken zo'n 1 dollar per week.
"""
from __future__ import annotations

from datetime import timedelta

from . import db, snackspert, taste

MAX_REVIEWS_NEW = 60   # met meer reviews is een zaak niet 'net open', maar was hij er al


def _first(item: dict, *keys):
    for k in keys:
        cur = item
        for part in k.split("."):
            cur = cur.get(part) if isinstance(cur, dict) else None
        if cur not in (None, ""):
            return cur
    return None


def parse(item: dict) -> dict | None:
    pid = _first(item, "placeId", "cid", "url")
    name = _first(item, "title", "name")
    if not pid or not name:
        return None
    if item.get("permanentlyClosed") or item.get("temporarilyClosed"):
        return None
    loc = item.get("location") or {}
    return {"place_id": str(pid), "name": str(name).strip(), "category": _first(item, "categoryName"),
            "address": _first(item, "address", "street"), "city": _first(item, "city"),
            "lat": loc.get("lat"), "lon": loc.get("lng"), "rating": _first(item, "totalScore"),
            "reviews": int(_first(item, "reviewsCount") or 0), "url": _first(item, "url")}


def next_searches(conn, settings: dict) -> list[tuple[str, str]]:
    """De volgende steden op rij, met alle zoektermen: [(zoekopdracht, stad)]."""
    cities = [c for c in settings.get("maps_steden") or [] if c.strip()]
    terms = [t for t in settings.get("maps_zoektermen") or [] if t.strip()]
    if not cities or not terms:
        return []
    start = db.get_state(conn, "maps_volgende", 0) % len(cities)
    n = max(1, int(settings.get("maps_steden_per_week", 2)))
    chosen = [cities[(start + i) % len(cities)] for i in range(min(n, len(cities)))]
    return [(f"{t} {c}", c) for c in chosen for t in terms]


def store(conn, search: str, items: list[dict]) -> int:
    """Sla resultaten op. Geeft het aantal nieuwe zaken (na de nulmeting van deze zoekopdracht)."""
    baseline_done = db.get_state(conn, f"maps_nulmeting_{search.lower()}", False)
    now = db.iso(db.now())
    new = 0
    for it in items:
        p = parse(it)
        if not p:
            continue
        known = conn.execute("SELECT 1 FROM places WHERE place_id = ?", (p["place_id"],)).fetchone()
        if known:
            conn.execute("UPDATE places SET last_seen = ?, rating = ?, reviews = ? WHERE place_id = ?",
                         (now, p["rating"], p["reviews"], p["place_id"]))
            continue
        is_new = int(baseline_done and p["reviews"] <= MAX_REVIEWS_NEW)
        conn.execute("INSERT INTO places(place_id, name, category, address, city, lat, lon, rating, reviews, url, "
                     "search, first_seen, last_seen, is_new) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                     (p["place_id"], p["name"], p["category"], p["address"], p["city"], p["lat"], p["lon"],
                      p["rating"], p["reviews"], p["url"], search, now, now, is_new))
        new += is_new
    db.set_state(conn, f"maps_nulmeting_{search.lower()}", True)
    return new


def new_places(conn, days: int = 60, limit: int = 30) -> list[dict]:
    """Net opgedoken zaken die nog niet in je tips staan en die je nog niet gereviewd hebt."""
    since = db.iso(db.now() - timedelta(days=days))
    tips = {taste.zaak_key(r["name"]) for r in conn.execute("SELECT name FROM spots")}
    reviewed = [dict(r) for r in conn.execute("SELECT * FROM reviewed")]
    out = []
    for r in conn.execute("SELECT * FROM places WHERE is_new = 1 AND first_seen >= ? "
                          "ORDER BY first_seen DESC, reviews ASC", (since,)):
        d = dict(r)
        if taste.zaak_key(d["name"]) in tips or (reviewed and snackspert.match(d["name"], reviewed)):
            continue
        # Weinig reviews maar al hoog gewaardeerd: dat is het interessantst.
        d["hot"] = bool(d["rating"] and d["rating"] >= 4.5 and d["reviews"] >= 5)
        d["category"] = d["category"] or ""
        out.append(d)
        if len(out) >= limit:
            break
    out.sort(key=lambda d: (not d["hot"], -(d["rating"] or 0)))
    return out


def summary(conn) -> dict:
    return {"places": conn.execute("SELECT COUNT(*) FROM places").fetchone()[0],
            "last": db.get_state(conn, "maps_laatst")}
