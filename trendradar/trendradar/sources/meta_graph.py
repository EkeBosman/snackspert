"""Gratis Instagram-data via de officiële Meta Graph API.

Twee functies, allebei op naam van jouw eigen Instagram-zakelijke account:
- Hashtag-zoeken: posts van de laatste 24 uur onder een hashtag. Meta staat
  maximaal 30 verschillende hashtags per 7 dagen toe; dat houden we bij in de
  tabel graph_hashtags.
- Business Discovery: de laatste posts van een ander zakelijk of creator-account
  (niet van privé-accounts).

Wat de API niet geeft wordt via Apify opgehaald.
"""
from __future__ import annotations

from datetime import timedelta

import requests

from .. import config, db
from ..classify import extract_hashtags, extract_mentions
from .apify import _ts

WEEK_LIMIT = 30
MEDIA_FIELDS = ("id,caption,like_count,comments_count,timestamp,permalink,"
                "media_type,media_url,thumbnail_url")


class GraphError(RuntimeError):
    pass


def available() -> bool:
    return bool(config.secret("META_ACCESS_TOKEN") and config.secret("META_IG_USER_ID"))


def _base() -> str:
    version = config.secret("META_GRAPH_VERSION") or "v25.0"
    return f"https://graph.facebook.com/{version}"


def _get(path: str, params: dict) -> dict:
    params = dict(params, access_token=config.secret("META_ACCESS_TOKEN"))
    try:
        r = requests.get(f"{_base()}/{path}", params=params, timeout=60)
    except requests.RequestException as exc:
        # De sleutel staat in de URL (zo werkt de Graph API); haal hem uit de melding.
        raise GraphError(config.redact(str(exc))) from None
    data = r.json() if r.content else {}
    if r.status_code >= 400 or "error" in data:
        err = data.get("error", {})
        raise GraphError(f"{err.get('code', r.status_code)}: {err.get('message', r.text[:200])}")
    return data


def hashtag_slots(conn) -> tuple[set[str], int]:
    """(hashtags die deze week al een plek hebben, aantal vrije plekken)."""
    cutoff = db.iso(db.now() - timedelta(days=7))
    used = {r["hashtag"] for r in conn.execute(
        "SELECT hashtag FROM graph_hashtags WHERE first_used > ?", (cutoff,))}
    return used, max(0, WEEK_LIMIT - len(used))


def _hashtag_id(conn, tag: str) -> str:
    row = conn.execute("SELECT hashtag_id, first_used FROM graph_hashtags WHERE hashtag = ?",
                       (tag,)).fetchone()
    cutoff = db.iso(db.now() - timedelta(days=7))
    if row and row["hashtag_id"] and row["first_used"] > cutoff:
        return row["hashtag_id"]
    data = _get("ig_hashtag_search", {"user_id": config.secret("META_IG_USER_ID"), "q": tag})
    if not data.get("data"):
        raise GraphError(f"hashtag #{tag} niet gevonden")
    hid = data["data"][0]["id"]
    conn.execute(
        "INSERT INTO graph_hashtags(hashtag, hashtag_id, first_used) VALUES(?, ?, ?) "
        "ON CONFLICT(hashtag) DO UPDATE SET hashtag_id = excluded.hashtag_id, "
        "first_used = excluded.first_used",
        (tag, hid, db.iso(db.now())))
    return hid


def fetch_hashtag(conn, tag: str, limit: int = 50) -> list[dict]:
    hid = _hashtag_id(conn, tag)
    data = _get(f"{hid}/recent_media", {"user_id": config.secret("META_IG_USER_ID"),
                                        "fields": MEDIA_FIELDS, "limit": min(limit, 50)})
    return [p for p in (_normalize(m, author=None) for m in data.get("data", [])) if p]


def fetch_account(username: str, limit: int = 12) -> tuple[list[dict], dict]:
    fields = (f"business_discovery.username({username})"
              f"{{username,name,followers_count,media_count,media.limit({limit}){{{MEDIA_FIELDS}}}}}")
    data = _get(config.secret("META_IG_USER_ID"), {"fields": fields})
    bd = data.get("business_discovery") or {}
    profile = {"username": bd.get("username", username), "name": bd.get("name"),
               "followers": bd.get("followers_count")}
    posts = []
    for m in (bd.get("media") or {}).get("data", []):
        post = _normalize(m, author=profile["username"])
        if post:
            post["author_name"] = profile["name"]
            post["author_followers"] = profile["followers"] or 0
            posts.append(post)
    return posts, profile


def _normalize(m: dict, author: str | None) -> dict | None:
    if not m.get("id") or not m.get("timestamp"):
        return None
    text = m.get("caption") or ""
    return {
        "id": f"instagram:{m['id']}",
        "platform": "instagram",
        "author": (author or "").lower() or None,
        "author_name": None,
        "author_followers": 0,
        "text": text,
        "url": m.get("permalink"),
        "thumbnail": m.get("thumbnail_url") or (m.get("media_url") if m.get("media_type") != "VIDEO" else None),
        "location": None,
        "posted_at": _ts(m["timestamp"].replace("+0000", "+00:00")),
        "likes": int(m.get("like_count") or 0),
        "comments": int(m.get("comments_count") or 0),
        "shares": 0,
        "views": 0,
        "hashtags": extract_hashtags(text),
        "mentions": extract_mentions(text),
    }
