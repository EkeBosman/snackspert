"""Excel-bestanden inlezen: je postoverzicht en je tips en routes.

De tool herkent zelf wat er in een bestand staat, aan de kolomnamen:

- een tabblad met 'Weergaven' en 'Caption'  -> je eigen posts
- een tabblad met 'Route' en 'Stop 1'       -> routes
- een tabblad met 'Naam' (of 'Naam zaak')   -> tips (spots)

Tabbladen met samenvattingen (Per maand, Samenvatting) slaat hij over: die
rekent de tool zelf uit. Opnieuw importeren kan altijd. Je posts en routes
worden dan vervangen; bij tips blijven jouw status en notities bewaard.
"""
from __future__ import annotations

import io
import json
import re
from datetime import date, datetime

from . import db

POST_COLUMNS = {
    "maand": "month", "datum": "date", "type": "type", "caption (begin)": "caption", "caption": "caption",
    "link": "url", "weergaven": "views", "bereik": "reach", "likes": "likes", "reacties": "comments",
    "gedeeld": "shares", "opgeslagen": "saves", "volgers": "followers", "format": "format",
    "kanaal": "channel", "locatie": "location", "herkenbaarheid": "recognition", "indeling": "classified",
    "volgers telt mee": "followers_count", "notitie": "note",
}
NUMBERS = {"views", "reach", "likes", "comments", "shares", "saves", "followers"}


class ImportError_(ValueError):
    """Het bestand bevat niets wat de tool herkent."""


def _key(v) -> str:
    return re.sub(r"\s+", " ", str(v or "")).strip().lower()


def _text(v) -> str:
    if v is None:
        return ""
    if isinstance(v, (datetime, date)):
        return v.strftime("%Y-%m-%d")
    return str(v).strip()


def _number(v):
    if v is None or v == "":
        return None
    if isinstance(v, (int, float)):
        return int(v)
    digits = re.sub(r"[^\d]", "", str(v))
    return int(digits) if digits else None


def _header(ws, max_scan: int = 6):
    """(rijnummer, [kolomnamen]) van de eerste rij met minstens twee namen."""
    for i, row in enumerate(ws.iter_rows(min_row=1, max_row=max_scan), start=1):
        names = [_key(c.value) for c in row]
        if sum(1 for n in names if n) >= 2:
            return i, names
    return None, []


def _list_name(title: str) -> str:
    t = title.strip()
    low = t.lower()
    if "buiten" in low and ("a'dam" in low or "amsterdam" in low):
        return "Buiten Amsterdam"
    if low.startswith("alle spots"):
        return "Spots"
    return t


def read_workbook(data: bytes) -> dict:
    """Leest een .xlsx en geeft {'posts': [...], 'spots': [...], 'routes': [...]}."""
    import openpyxl

    try:
        wb = openpyxl.load_workbook(io.BytesIO(data), data_only=True)
    except Exception as exc:  # zip- of xml-fout: geen geldig Excel-bestand
        raise ImportError_("Dit is geen Excel-bestand (.xlsx) dat de tool kan lezen.") from exc
    out = {"posts": [], "spots": [], "routes": []}
    for ws in wb.worksheets:
        row_no, names = _header(ws)
        if not row_no:
            continue
        if "weergaven" in names and any(n.startswith("caption") for n in names):
            out["posts"] += _read_posts(ws, row_no, names)
        elif "route" in names and "stop 1" in names:
            out["routes"] += _read_routes(ws, row_no, names)
        elif names and names[0] in ("naam", "naam zaak"):
            out["spots"] += _read_spots(ws, row_no, names)
    # Tabbladen als 'Samenwerkingen' herhalen posts uit 'Posts'. Houd per post de vollediger rij.
    best: dict[str, dict] = {}
    for p in out["posts"]:
        filled = sum(1 for v in p.values() if v not in (None, ""))
        if p["id"] not in best or filled > sum(1 for v in best[p["id"]].values() if v not in (None, "")):
            best[p["id"]] = p
    out["posts"] = list(best.values())
    if not any(out.values()):
        raise ImportError_("Geen posts, tips of routes gevonden. Staan de kolomnamen in de eerste rij?")
    return out


def _read_posts(ws, row_no, names) -> list[dict]:
    cols = {i: POST_COLUMNS[n] for i, n in enumerate(names) if n in POST_COLUMNS}
    rows = []
    for row in ws.iter_rows(min_row=row_no + 1):
        p = {}
        for i, field in cols.items():
            cell = row[i] if i < len(row) else None
            if cell is None:
                continue
            if field == "url":
                p["url"] = cell.hyperlink.target if cell.hyperlink else (
                    _text(cell.value) if _text(cell.value).startswith("http") else "")
            elif field in NUMBERS:
                p[field] = _number(cell.value)
            else:
                p[field] = _text(cell.value)
        if not p.get("caption") and not p.get("views"):
            continue
        p["followers_count"] = 0 if _key(p.get("followers_count")) == "nee" else 1
        if not p.get("month") and p.get("date"):
            p["month"] = p["date"][:7]
        p["id"] = p.get("url") or f"{p.get('month', '')}:{(p.get('caption') or '')[:60]}"
        rows.append(p)
    return rows


def _read_spots(ws, row_no, names) -> list[dict]:
    def col(*options):
        return next((i for i, n in enumerate(names) if n in options), None)
    c_name, c_place = col("naam", "naam zaak"), col("locatie", "plaats", "stad")
    c_spec, c_region = col("specialiteit", "beschrijving", "opmerking"), col("regio", "provincie")
    lst = _list_name(ws.title)
    default_place = "Amsterdam" if c_place is None and "amsterdam" in ws.title.lower() else ""
    out = []
    for row in ws.iter_rows(min_row=row_no + 1, values_only=True):
        name = _text(row[c_name]) if c_name is not None and c_name < len(row) else ""
        if not name:
            continue
        get = lambda c: _text(row[c]) if c is not None and c < len(row) else ""  # noqa: E731
        place = get(c_place) or default_place
        if place.upper() == "ONBEKEND":
            place = ""
        region = get(c_region)
        if region.upper() == "ONBEKEND":
            region = ""
        if not region and place == "Amsterdam":
            region = "Noord-Holland"
        out.append({"name": name, "place": place, "specialty": get(c_spec), "region": region, "list": lst})
    return out


def _read_routes(ws, row_no, names) -> list[dict]:
    stops = [i for i, n in enumerate(names) if n.startswith("stop")]
    def col(prefix):
        return next((i for i, n in enumerate(names) if n.startswith(prefix)), None)
    c_name, c_region, c_km, c_time, c_note = col("route"), col("regio"), col("km"), col("rijtijd"), col("opmerking")
    out = []
    for row in ws.iter_rows(min_row=row_no + 1, values_only=True):
        get = lambda c: _text(row[c]) if c is not None and c < len(row) else ""  # noqa: E731
        name = get(c_name)
        route_stops = [get(i) for i in stops if get(i)]
        if not name or not route_stops:
            continue
        out.append({"name": name, "region": get(c_region), "stops": route_stops, "km": get(c_km),
                    "duration": get(c_time), "note": get(c_note)})
    return out


def parse_stop(stop: str) -> dict:
    """'Snackbar de Poppe (Coevorden) - broodje lammert' -> naam, plaats, specialiteit."""
    m = re.match(r"\s*(.+?)\s*\(([^)]+)\)\s*(?:[-–]\s*(.*))?$", stop)
    if not m:
        return {"name": stop.strip(), "place": "", "specialty": ""}
    return {"name": m.group(1), "place": m.group(2), "specialty": (m.group(3) or "").strip()}


def save(conn, parsed: dict) -> dict:
    """Slaat het resultaat van read_workbook op. Geeft per soort het aantal terug."""
    now = db.iso(db.now())
    result = {"posts": 0, "spots": 0, "spots_new": 0, "routes": 0}
    if parsed["posts"]:
        # Het Excel-overzicht is leidend: alles vervangen voorkomt dubbele posts.
        conn.execute("DELETE FROM own_posts")
        fields = ["id", "date", "month", "type", "caption", "url", "views", "reach", "likes", "comments",
                  "shares", "saves", "followers", "format", "channel", "location", "recognition",
                  "classified", "followers_count", "note"]
        for p in parsed["posts"]:
            conn.execute(
                f"INSERT OR REPLACE INTO own_posts({', '.join(fields)}, imported_at) "
                f"VALUES ({', '.join('?' for _ in fields)}, ?)",
                [p.get(f) if p.get(f) != "" else None for f in fields] + [now])
        result["posts"] = len(parsed["posts"])
    for s in parsed["spots"]:
        existing = conn.execute("SELECT id, lists, specialty, region FROM spots WHERE name = ? AND place = ?",
                                (s["name"], s["place"])).fetchone()
        if existing:
            lists = json.loads(existing["lists"] or "[]")
            if s["list"] not in lists:
                lists.append(s["list"])
            conn.execute("UPDATE spots SET lists = ?, specialty = ?, region = ?, updated_at = ? WHERE id = ?",
                         (json.dumps(lists), s["specialty"] or existing["specialty"],
                          s["region"] or existing["region"], now, existing["id"]))
        else:
            conn.execute("INSERT INTO spots(name, place, specialty, region, lists, added_at, updated_at) "
                         "VALUES (?, ?, ?, ?, ?, ?, ?)",
                         (s["name"], s["place"], s["specialty"], s["region"], json.dumps([s["list"]]), now, now))
            result["spots_new"] += 1
        result["spots"] += 1
    if parsed["routes"]:
        conn.execute("DELETE FROM routes WHERE origin = 'import'")
        for r in parsed["routes"]:
            conn.execute("INSERT INTO routes(name, region, stops, km, duration, note, added_at) "
                         "VALUES (?, ?, ?, ?, ?, ?, ?)",
                         (r["name"], r["region"], json.dumps(r["stops"], ensure_ascii=False), r["km"],
                          r["duration"], r["note"], now))
        result["routes"] = len(parsed["routes"])
    return result
