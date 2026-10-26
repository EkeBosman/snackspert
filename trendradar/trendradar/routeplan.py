"""Routes die de tool zelf bedenkt.

De tool zoekt groepjes kansrijke tips (zie potential.py) die dicht bij elkaar
liggen en maakt daar een route van, vanaf je thuisbasis en weer terug. Wat
hij leert:

- van je eigen routes: hoe ver je gewoonlijk rijdt en met hoeveel stops;
- van je statussen: bezochte, gereviewde en afgewezen tips doen niet mee;
- van je ♥, 👎 en bewaarde items: die tellen mee in de potentie van een tip;
- van routes die je afwijst: die stelt hij niet opnieuw voor.

Afstand en rijtijd zijn een schatting (hemelsbreed × 1,3, gemiddeld 75 km/u).
De knop naar Google Maps geeft de echte route.
"""
from __future__ import annotations

import itertools
import json
import re
from statistics import median

from . import db, geo, imports, potential, spots

CLUSTER_KM = 35          # stops liggen hooguit zo ver van de eerste stop
DEFAULT_MAX_KM = 450
MAX_PROPOSALS = 6


def _stop_key(name: str, place: str) -> str:
    zaak, place_key = imports.spot_key(name, place)
    return f"{zaak}@{place_key}"


def route_key(stops: list[dict]) -> str:
    return "|".join(sorted(_stop_key(s["name"], s["place"]) for s in stops))


def habits(conn) -> dict:
    """Hoe ver en met hoeveel stops je routes gewoonlijk gaan (uit je eigen routes)."""
    kms, n_stops = [], []
    for r in conn.execute("SELECT km, stops FROM routes"):
        if m := re.search(r"(\d+)", r["km"] or ""):
            kms.append(int(m.group(1)))
        n_stops.append(len(db.row_to_dict(r)["stops"]))
    if not kms:
        return {"max_km": DEFAULT_MAX_KM, "median_km": None, "stops": [3, 4], "routes": 0}
    kms.sort()
    p90 = kms[min(len(kms) - 1, int(0.9 * len(kms)))]
    common = sorted({n for n in n_stops if n_stops.count(n) >= max(1, len(n_stops) // 10)}) or [3]
    return {"max_km": max(100, p90), "median_km": round(median(kms)), "stops": [n for n in common if 2 <= n <= 5] or [3],
            "routes": len(kms)}


def _best_order(home, group):
    best = None
    for perm in itertools.permutations(group):
        road = geo.road_km([home, *[s["xy"] for s in perm], home])
        if best is None or road < best[0]:
            best = (road, list(perm))
    return best


def proposals(conn, include_demo: bool = True, limit: int = MAX_PROPOSALS) -> dict:
    settings = db.get_settings(conn)
    home_name = settings.get("thuisbasis") or "Amsterdam"
    home = geo.coords(conn, home_name)
    h = habits(conn)
    info = {"home": home_name, "habits": h, "missing": len(geo.missing(conn)), "progress": geo.progress()}
    if not home:
        return {**info, "routes": [], "melding": f"De tool weet nog niet waar {home_name} ligt."}
    ranked = potential.ranking(conn, limit=10000, include_demo=include_demo)["top"]
    cands, seen = [], set()
    for t in ranked:
        key = _stop_key(t["name"], t["place"])
        # Bezochte tips hoeven niet nog eens in een route; elke zaak maar één keer.
        if t["status"] in spots.DONE or key in seen:
            continue
        xy = geo.coords(conn, t["place"])
        if xy and t["score"] > 0:
            seen.add(key)
            cands.append({**t, "xy": xy})
    rejected = {r["stops_key"] for r in conn.execute("SELECT stops_key FROM route_feedback WHERE value < 0")}
    existing = set()
    for r in conn.execute("SELECT stops FROM routes"):
        existing.add(route_key([imports.parse_stop(s) for s in db.row_to_dict(r)["stops"]]))

    found: dict[str, dict] = {}
    for anchor in sorted(cands, key=lambda c: c["score"], reverse=True)[:40]:
        near = [c for c in cands if c is not anchor and geo.km(anchor["xy"], c["xy"]) <= CLUSTER_KM]
        near.sort(key=lambda c: c["score"] - 0.03 * geo.km(anchor["xy"], c["xy"]), reverse=True)
        for n in h["stops"]:
            group = [anchor] + near[:n - 1]
            if len(group) < n:
                continue
            key = route_key(group)
            if key in rejected or key in existing or key in found:
                continue
            road, order = _best_order(home, group)
            if road > h["max_km"]:
                continue
            spread = max(geo.km(a["xy"], b["xy"]) for a, b in itertools.combinations(group, 2))
            found[key] = {
                "key": key,
                "name": " → ".join(dict.fromkeys(geo.clean_place(s["place"]).split(",")[0] for s in order)),
                "value": round(sum(s["score"] for s in group) - 0.006 * road, 2),
                "potential": round(sum(s["potential"] for s in group) / len(group)),
                "km": int(round(road / 5) * 5),
                "duration": geo.drive_time(road),
                "spread_km": round(spread),
                "maps": spots.maps_url([f"{s['name']} ({s['place']})" for s in order]),
                "stops": [{"id": s["id"], "name": s["name"], "place": s["place"], "specialty": s["specialty"],
                           "potential": s["potential"], "maps": s["maps"],
                           "reasons": [r["text"] for r in sorted(s["reasons"], key=lambda r: -r["points"])[:2]]}
                          for s in order],
            }
    # Spreiding: een voorstel deelt hooguit één stop met een eerder voorstel, anders
    # zie je zes keer bijna dezelfde route rond één topper.
    chosen = []
    for p in sorted(found.values(), key=lambda p: p["value"], reverse=True):
        keys = set(p["key"].split("|"))
        if any(len(keys & set(c["key"].split("|"))) > 1 for c in chosen):
            continue
        chosen.append(p)
        if len(chosen) >= limit:
            break
    return {**info, "routes": chosen, "candidates": len(cands)}


def save(conn, proposal: dict) -> int | None:
    """Bewaar een voorgestelde route. Bestaat dezelfde route al (dubbelklik), dan niet nog eens."""
    stops = [f"{s['name']} ({geo.clean_place(s['place'])})" + (f" - {s['specialty']}" if s.get("specialty") else "")
             for s in proposal["stops"]]
    key = route_key([imports.parse_stop(x) for x in stops])
    for r in conn.execute("SELECT id, stops FROM routes"):
        if route_key([imports.parse_stop(x) for x in db.row_to_dict(r)["stops"]]) == key:
            return r["id"]
    cur = conn.execute("INSERT INTO routes(name, region, stops, km, duration, note, status, origin, added_at) "
                       "VALUES (?, ?, ?, ?, ?, ?, 'nieuw', 'bedacht', ?)",
                       (proposal["name"], proposal.get("region", ""), json.dumps(stops, ensure_ascii=False),
                        f"~{proposal['km']} km", proposal["duration"], "Bedacht door de tool",
                        db.iso(db.now())))
    return cur.lastrowid


def reject(conn, key: str) -> None:
    conn.execute("INSERT OR REPLACE INTO route_feedback(stops_key, value, at) VALUES (?, -1, ?)",
                 (key, db.iso(db.now())))
