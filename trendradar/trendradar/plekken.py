"""Precieze plekken van tips, voor de kaart van één stad (zoals Amsterdam).

Je tips hebben een plaats maar geen adres. Voor een stad waar je veel tips hebt,
zoekt de tool per zaak de precieze plek op via Google Maps (Apify, ± 0,5 cent per
zaak). Klopt de gevonden naam niet met je tip, dan gebruikt hij hem niet.
"""
from __future__ import annotations

import threading
from datetime import timedelta

from . import budget, db, nieuwezaken, snackspert, spots

RETRY_DAYS = 30
MAX_PER_RUN = 80
_lock = threading.Lock()
_busy = {"running": False, "todo": 0}


def in_city(spot: dict, city: str) -> bool:
    c = city.lower()
    lists = [x.lower() for x in spot.get("lists") or []]
    return (spot.get("place") or "").lower() == c or c in lists


def todo(conn, cities: list[str]) -> list[dict]:
    retry = db.iso(db.now() - timedelta(days=RETRY_DAYS))
    done = {r["spot_id"]: r for r in conn.execute("SELECT spot_id, lat, looked_up FROM spot_geo")}
    out = []
    for r in conn.execute("SELECT * FROM spots"):
        s = db.row_to_dict(r)
        city = next((c for c in cities if in_city(s, c)), None)
        if not city:
            continue
        g = done.get(s["id"])
        if g and (g["lat"] is not None or g["looked_up"] > retry):
            continue
        out.append({**s, "_city": city})
    return out


def _same(a: str, b: str) -> bool:
    ka, kb = snackspert.core_name(a).replace(" ", ""), snackspert.core_name(b).replace(" ", "")
    return bool(ka and kb) and spots._same_place(ka, kb)


def store(conn, wanted: list[dict], items: list[dict]) -> int:
    """Koppel resultaten (per zoekopdracht) aan tips. Geeft het aantal gevonden plekken."""
    by_search = {}
    for it in items:
        by_search.setdefault((it.get("searchString") or "").lower(), []).append(it)
    now = db.iso(db.now())
    found = 0
    for s in wanted:
        hit = None
        # Geeft de actor de zoekopdracht niet terug, dan alle resultaten langs (op naam).
        for it in by_search.get(f"{s['name']} {s['_city']}".lower()) or items:
            p = nieuwezaken.parse(it)
            if p and p["lat"] is not None and _same(s["name"], p["name"]):
                hit = p
                break
        conn.execute("INSERT OR REPLACE INTO spot_geo(spot_id, lat, lon, address, url, looked_up) "
                     "VALUES (?, ?, ?, ?, ?, ?)",
                     (s["id"], hit and hit["lat"], hit and hit["lon"], hit and hit["address"],
                      hit and hit["url"], now))
        found += bool(hit)
    return found


def fill(settings: dict) -> dict:
    """Zoek de plekken die nog ontbreken (hooguit 80 per keer)."""
    from .sources import apify

    cities = [c for c in settings.get("exacte_kaart_steden") or [] if c.strip()]
    if not cities or not apify.available() or not _lock.acquire(blocking=False):
        return {"found": 0, "todo": 0}
    try:
        with db.session() as conn:
            wanted = todo(conn, cities)[:MAX_PER_RUN]
            if not wanted or budget.plan(conn, settings)["left_usd"] <= 0:
                return {"found": 0, "todo": len(wanted)}
        _busy.update(running=True, todo=len(wanted))
        price = settings.get("prijs_maps_per_1000", 4.0)
        values = [f"{s['name']} {s['_city']}" for s in wanted]
        items, cost = apify.run_actor("maps", "zoekterm", values, 1, len(values) * price / 1000 * 2 + 0.1,
                                      price_per_1000=price)
        with db.session() as conn:
            budget.record(conn, "apify", cost, None, f"plekken van {len(values)} tips")
            found = store(conn, wanted, items)
        return {"found": found, "todo": len(wanted), "cost": cost}
    finally:
        _busy["running"] = False
        _lock.release()


def fill_in_background(settings: dict) -> bool:
    if _busy["running"]:
        return False
    threading.Thread(target=fill, args=(settings,), daemon=True).start()
    return True


def progress() -> dict:
    return dict(_busy)
