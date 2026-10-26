"""Waar liggen je tips? Coördinaten van plaatsen, voor routes die de tool zelf bedenkt.

Eerst kijkt de tool in zijn eigen lijst met steden. Een plaats die daar niet
in staat, zoekt hij één keer op bij OpenStreetMap (Nominatim, gratis) en
bewaart het antwoord. Volgens de regels van OpenStreetMap: hooguit één
vraag per seconde, en elke plaats maar één keer.
"""
from __future__ import annotations

import math
import re
import threading
import time
from datetime import timedelta

import requests

from . import db, imports, lexicon

NOMINATIM = "https://nominatim.openstreetmap.org/search"
USER_AGENT = "SnackspertTrendradar/1.0 (lokale tool, zoekt plaatsen van snackzaken op)"
PAUSE_S = 1.1
RETRY_FAILED_DAYS = 30
ROAD_FACTOR = 1.3      # hemelsbreed naar over de weg
SPEED_KMH = 75         # gemiddelde snelheid, inclusief binnen de bebouwde kom

_lock = threading.Lock()
_busy = {"running": False, "done": 0, "todo": 0}
_CITIES = {k.lower(): v for k, v in lexicon.CITIES.items()}


def clean_place(place: str) -> str:
    """'Colmschate (Deventer)' -> 'Colmschate, Deventer'; 'ONBEKEND' -> ''."""
    p = re.sub(r"\s*\(([^)]+)\)", r", \1", (place or "").strip())
    return "" if p.upper() == "ONBEKEND" else p


def coords(conn, place: str) -> tuple[float, float] | None:
    p = clean_place(place)
    if not p:
        return None
    # Alleen een exacte naam uit de eigen lijst. 'Valkenburg, ZH' is niet het Valkenburg in
    # Limburg: een plaats met een toevoeging zoekt de tool altijd op.
    if p.lower() in _CITIES:
        return _CITIES[p.lower()]
    row = conn.execute("SELECT lat, lon FROM geo WHERE place = ?", (p,)).fetchone()
    return (row["lat"], row["lon"]) if row and row["lat"] is not None else None


def all_places(conn) -> set[str]:
    places = {clean_place(r["place"]) for r in conn.execute("SELECT place FROM spots")}
    for r in conn.execute("SELECT stops FROM routes"):
        places |= {clean_place(imports.parse_stop(s)["place"]) for s in db.row_to_dict(r)["stops"]}
    home = db.get_settings(conn).get("thuisbasis") or "Amsterdam"
    places.add(clean_place(home))
    return {p for p in places if p}


def missing(conn) -> list[str]:
    retry = db.iso(db.now() - timedelta(days=RETRY_FAILED_DAYS))
    out = []
    for p in sorted(all_places(conn)):
        if coords(conn, p):
            continue
        row = conn.execute("SELECT looked_up FROM geo WHERE place = ?", (p,)).fetchone()
        if row and row["looked_up"] > retry:
            continue  # recent niet gevonden: niet steeds opnieuw vragen
        out.append(p)
    return out


def lookup(place: str) -> tuple[float, float] | None:
    r = requests.get(NOMINATIM, params={"q": place, "format": "json", "limit": 1, "countrycodes": "nl,be"},
                     headers={"User-Agent": USER_AGENT, "Accept-Language": "nl"}, timeout=20)
    r.raise_for_status()
    data = r.json()
    if not data:
        return None
    return float(data[0]["lat"]), float(data[0]["lon"])


def fill(limit: int = 60) -> dict:
    """Zoek ontbrekende plaatsen op (hooguit `limit`). Veilig om vaker aan te roepen."""
    if not _lock.acquire(blocking=False):
        return {"found": 0, "failed": 0, "busy": True}
    found = failed = 0
    try:
        with db.session() as conn:
            todo = missing(conn)[:limit]
        _busy.update(running=True, done=0, todo=len(todo))
        for i, place in enumerate(todo):
            if i:
                time.sleep(PAUSE_S)
            try:
                hit = lookup(place)
            except requests.RequestException:
                break  # geen internet of OpenStreetMap druk: later verder
            with db.session() as conn:
                conn.execute("INSERT OR REPLACE INTO geo(place, lat, lon, looked_up) VALUES (?, ?, ?, ?)",
                             (place, hit[0] if hit else None, hit[1] if hit else None, db.iso(db.now())))
            found += bool(hit)
            failed += not hit
            _busy["done"] = i + 1
        return {"found": found, "failed": failed, "busy": False}
    finally:
        _busy["running"] = False
        _lock.release()


def fill_in_background() -> bool:
    if _busy["running"]:
        return False
    threading.Thread(target=fill, kwargs={"limit": 500}, daemon=True).start()
    return True


def progress() -> dict:
    return dict(_busy)


def km(a: tuple[float, float], b: tuple[float, float]) -> float:
    """Hemelsbrede afstand in km."""
    lat1, lon1, lat2, lon2 = map(math.radians, (*a, *b))
    h = math.sin((lat2 - lat1) / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin((lon2 - lon1) / 2) ** 2
    return 6371 * 2 * math.asin(math.sqrt(h))


def road_km(points: list[tuple[float, float]]) -> float:
    """Geschatte afstand over de weg langs alle punten."""
    return ROAD_FACTOR * sum(km(points[i], points[i + 1]) for i in range(len(points) - 1))


def drive_time(road: float) -> str:
    minutes = round(road / SPEED_KMH * 60)
    return f"{minutes // 60}u {minutes % 60:02d}min" if minutes >= 60 else f"{minutes} min"
