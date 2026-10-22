"""Je tips en routes, gekoppeld aan de trendradar.

Een tip is een zaak die je wilt proberen, met de specialiteit erbij. De tool
kijkt of een tip opduikt in de posts die hij ophaalt ('in de radar'): dan zie
je dat een zaak van je lijst nu besproken wordt. Een route is een rijtje
stops; met één klik open je hem in Google Maps.
"""
from __future__ import annotations

import json
import re
from datetime import timedelta
from urllib.parse import quote

from . import classify, db, imports, ownposts, taste


def _distinctive(name: str) -> str | None:
    """Sleutel om op te zoeken in posts, of None als de naam te algemeen is ('Raam', 'Istanbul')."""
    key = taste.zaak_key(name)
    if key in taste._TOWNS:
        return None
    if len(key) >= 10 or (len(key) >= 8 and " " in name.strip()):
        return key
    return None


def radar_hits(conn, days: int = 30, include_demo: bool = True) -> dict[int, dict]:
    """{spot_id: {posts, last, post_ids}}: tips die in recente posts genoemd worden."""
    spots = [(r["id"], _distinctive(r["name"])) for r in conn.execute("SELECT id, name FROM spots")]
    spots = [(i, k) for i, k in spots if k]
    if not spots:
        return {}
    since = db.iso(db.now() - timedelta(days=days))
    demo = "" if include_demo else " AND demo = 0"
    hits: dict[int, dict] = {}
    for p in conn.execute("SELECT id, text, author, places, posted_at FROM posts "
                          f"WHERE posted_at >= ? AND relevance >= 0.35 AND platform != 'nieuws'{demo} "
                          "ORDER BY posted_at DESC", (since,)):
        blob = re.sub(r"[^a-z0-9]", "", classify.norm(p["text"] or ""))
        keys = {taste.zaak_key(x) for x in json.loads(p["places"] or "[]")} | {taste.zaak_key(p["author"] or "")}
        for spot_id, key in spots:
            if key in blob or key in keys:
                h = hits.setdefault(spot_id, {"posts": 0, "last": p["posted_at"], "post_ids": []})
                h["posts"] += 1
                if len(h["post_ids"]) < 5:
                    h["post_ids"].append(p["id"])
    return hits


def maps_url(stops: list[str]) -> str:
    """Google Maps-route langs de stops, vanaf je huidige locatie."""
    places = []
    for s in stops:
        p = imports.parse_stop(s)
        places.append(f"{p['name']} {p['place']}".strip())
    if not places:
        return ""
    url = "https://www.google.com/maps/dir/?api=1&travelmode=driving&destination=" + quote(places[-1])
    if len(places) > 1:
        url += "&waypoints=" + quote("|".join(places[:-1]))
    return url


def maps_search(name: str, place: str) -> str:
    return "https://www.google.com/maps/search/?api=1&query=" + quote(f"{name} {place}".strip())


def listing(conn, include_demo: bool = True) -> dict:
    hits = radar_hits(conn, include_demo=include_demo)
    handles = {taste.zaak_key(h): v for h, v in ownposts.posted_handles(conn).items()}
    captions = ownposts.caption_index(conn)
    rows = []
    for r in conn.execute("SELECT * FROM spots ORDER BY name COLLATE NOCASE"):
        s = db.row_to_dict(r)
        s["radar"] = hits.get(s["id"])
        s["maps"] = maps_search(s["name"], s["place"])
        key = _distinctive(s["name"])
        s["posted"] = handles.get(taste.zaak_key(s["name"])) or (ownposts.find_posted(key, captions) if key else None)
        rows.append(s)
    lists = sorted({x for s in rows for x in s["lists"]})
    regions = sorted({s["region"] for s in rows if s["region"]})
    return {"spots": rows, "lists": lists, "regions": regions}


def routes(conn) -> list[dict]:
    statuses = {(r["name"].lower(), r["place"].lower()): r["status"]
                for r in conn.execute("SELECT name, place, status FROM spots")}
    out = []
    for r in conn.execute("SELECT * FROM routes ORDER BY id"):
        d = db.row_to_dict(r)
        d["maps"] = maps_url(d["stops"])
        d["stops"] = [{**imports.parse_stop(s), "text": s} for s in d["stops"]]
        for s in d["stops"]:
            s["status"] = statuses.get((s["name"].lower(), s["place"].lower()))
        out.append(d)
    return out

