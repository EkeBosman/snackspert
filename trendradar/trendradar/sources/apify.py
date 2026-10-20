"""Instagram, TikTok en Facebook via Apify (betaalde scrapers, per resultaat).

Elke run krijgt twee harde plafonds mee: `maxItems` (aantal resultaten) en
`maxTotalChargeUsd` (maximaal bedrag). Apify stopt de run zelf zodra een van
beide bereikt is, dus de tool kan nooit meer uitgeven dan gepland.

Actor-namen en invoervelden staan bovenaan in ACTORS. Verandert een actor zijn
invoer, of wil je een goedkopere, dan pas je het alleen hier aan.
"""
from __future__ import annotations

import logging
import time
from datetime import datetime, timezone

import requests

from .. import config
from ..classify import extract_hashtags, extract_mentions

log = logging.getLogger(__name__)

API = "https://api.apify.com/v2"


def _ig_hashtag_input(values, limit):
    return {"hashtags": values, "resultsLimit": limit, "resultsType": "posts"}


def _ig_profile_input(values, limit):
    return {"directUrls": [f"https://www.instagram.com/{v}/" for v in values],
            "resultsType": "posts", "resultsLimit": limit, "addParentData": False}


def _tt_input(kind):
    def build(values, limit):
        base = {"resultsPerPage": limit, "shouldDownloadVideos": False,
                "shouldDownloadCovers": False, "shouldDownloadSubtitles": False,
                "shouldDownloadSlideshowImages": False}
        if kind == "hashtag":
            base["hashtags"] = values
        elif kind == "account":
            base["profiles"] = values
        else:
            base["searchQueries"] = values
        return base
    return build


def _fb_input(values, limit):
    return {"startUrls": [{"url": v if v.startswith("http") else f"https://www.facebook.com/{v}"}
                          for v in values],
            "resultsLimit": limit}


# (platform, soort) -> (actor-id, invoerbouwer)
ACTORS = {
    ("instagram", "hashtag"): ("apify~instagram-hashtag-scraper", _ig_hashtag_input),
    ("instagram", "account"): ("apify~instagram-scraper", _ig_profile_input),
    ("tiktok", "hashtag"): ("clockworks~tiktok-scraper", _tt_input("hashtag")),
    ("tiktok", "account"): ("clockworks~tiktok-scraper", _tt_input("account")),
    ("tiktok", "zoekterm"): ("clockworks~tiktok-scraper", _tt_input("zoekterm")),
    ("facebook", "account"): ("apify~facebook-posts-scraper", _fb_input),
}


class ApifyError(RuntimeError):
    pass


def available() -> bool:
    return bool(config.secret("APIFY_TOKEN"))


def supports(platform: str, kind: str) -> bool:
    return (platform, kind) in ACTORS


def _auth() -> dict:
    # In een header en niet in de URL, zodat de sleutel nooit in een foutmelding staat.
    return {"Authorization": f"Bearer {config.secret('APIFY_TOKEN')}"}


def run_actor(platform: str, kind: str, values: list[str], per_value: int,
              max_usd: float, timeout_s: int = 900) -> tuple[list[dict], float]:
    """Start een actor-run, wacht tot hij klaar is en geef (items, kosten_usd)."""
    actor, build = ACTORS[(platform, kind)]
    headers = _auth()
    max_items = per_value * len(values)
    params = {
        "maxItems": max_items,
        "maxTotalChargeUsd": f"{max_usd:.2f}",
        "waitForFinish": 60,
    }
    resp = requests.post(f"{API}/acts/{actor}/runs", params=params, headers=headers,
                         json=build(values, per_value), timeout=90)
    if resp.status_code >= 400:
        raise ApifyError(f"{actor}: {resp.status_code} {resp.text[:300]}")
    run = resp.json()["data"]

    deadline = time.time() + timeout_s
    while run.get("status") in ("READY", "RUNNING") and time.time() < deadline:
        time.sleep(10)
        r = requests.get(f"{API}/actor-runs/{run['id']}", headers=headers,
                         params={"waitForFinish": 60}, timeout=90)
        r.raise_for_status()
        run = r.json()["data"]

    if run.get("status") in ("READY", "RUNNING"):
        requests.post(f"{API}/actor-runs/{run['id']}/abort", headers=headers, timeout=30)
        log.warning("%s duurde te lang en is afgebroken", actor)

    items: list[dict] = []
    dataset = run.get("defaultDatasetId")
    if dataset:
        r = requests.get(f"{API}/datasets/{dataset}/items", headers=headers,
                         params={"clean": "true", "format": "json", "limit": max_items},
                         timeout=120)
        r.raise_for_status()
        items = r.json()
    cost = float(run.get("usageTotalUsd") or 0.0)
    if run.get("status") not in ("SUCCEEDED", "ABORTED", "TIMED-OUT") and not items:
        raise ApifyError(f"{actor}: run eindigde met status {run.get('status')}")
    return items, cost


def account_usage() -> dict | None:
    """Wat Apify zelf zegt over het verbruik deze maand (ter controle)."""
    try:
        r = requests.get(f"{API}/users/me/usage/monthly", headers=_auth(), timeout=30)
        r.raise_for_status()
        return r.json().get("data")
    except requests.RequestException:
        return None


# --- omzetten naar één postformaat -----------------------------------------

def _first(item: dict, *keys, default=None):
    for key in keys:
        cur = item
        for part in key.split("."):
            if isinstance(cur, dict) and part in cur:
                cur = cur[part]
            else:
                cur = None
                break
        if cur not in (None, ""):
            return cur
    return default


def _ts(value) -> str | None:
    if value in (None, ""):
        return None
    if isinstance(value, (int, float)):
        if value > 1e12:
            value /= 1000
        dt = datetime.fromtimestamp(value, tz=timezone.utc)
    else:
        text = str(value).replace("Z", "+00:00")
        try:
            dt = datetime.fromisoformat(text)
        except ValueError:
            return None
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _int(value) -> int:
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0


def normalize(platform: str, item: dict) -> dict | None:
    if platform == "instagram":
        native = _first(item, "id", "shortCode")
        text = _first(item, "caption", default="") or ""
        post = {
            "id": f"instagram:{native}",
            "author": _first(item, "ownerUsername", "owner.username"),
            "author_name": _first(item, "ownerFullName", "owner.full_name"),
            "author_followers": _int(_first(item, "owner.followersCount", "followersCount")),
            "text": text,
            "url": _first(item, "url", default=f"https://www.instagram.com/p/{_first(item, 'shortCode')}/"),
            "thumbnail": _first(item, "displayUrl", "thumbnailUrl"),
            "location": _first(item, "locationName"),
            "posted_at": _ts(_first(item, "timestamp", "takenAtTimestamp")),
            "likes": max(0, _int(_first(item, "likesCount"))),
            "comments": _int(_first(item, "commentsCount")),
            "shares": 0,
            "views": _int(_first(item, "videoPlayCount", "videoViewCount")),
            "hashtags": [h.lower() for h in (item.get("hashtags") or [])] or extract_hashtags(text),
            "mentions": [m.lower() for m in (item.get("mentions") or [])] or extract_mentions(text),
        }
    elif platform == "tiktok":
        native = _first(item, "id")
        text = _first(item, "text", "desc", default="") or ""
        tags = [(h.get("name") if isinstance(h, dict) else h) for h in (item.get("hashtags") or [])]
        post = {
            "id": f"tiktok:{native}",
            "author": _first(item, "authorMeta.name", "author.uniqueId"),
            "author_name": _first(item, "authorMeta.nickName", "author.nickname"),
            "author_followers": _int(_first(item, "authorMeta.fans", "authorStats.followerCount")),
            "text": text,
            "url": _first(item, "webVideoUrl", "url"),
            "thumbnail": _first(item, "videoMeta.coverUrl", "covers.default"),
            "location": _first(item, "locationMeta.address", "locationMeta.locationName", "poi.name"),
            "posted_at": _ts(_first(item, "createTimeISO", "createTime")),
            "likes": _int(_first(item, "diggCount", "stats.diggCount")),
            "comments": _int(_first(item, "commentCount", "stats.commentCount")),
            "shares": _int(_first(item, "shareCount", "stats.shareCount")),
            "views": _int(_first(item, "playCount", "stats.playCount")),
            "hashtags": [t.lower() for t in tags if t] or extract_hashtags(text),
            "mentions": [m.lower().lstrip("@") for m in (item.get("mentions") or [])] or extract_mentions(text),
        }
    elif platform == "facebook":
        native = _first(item, "postId", "id", "url")
        text = _first(item, "text", "message", default="") or ""
        media = item.get("media") or []
        thumb = None
        if media and isinstance(media[0], dict):
            thumb = _first(media[0], "thumbnail", "photo_image.uri", "image.uri")
        post = {
            "id": f"facebook:{native}",
            "author": _first(item, "pageName", "user.name", "facebookUrl"),
            "author_name": _first(item, "user.name", "pageName"),
            "author_followers": _int(_first(item, "pageFollowers", "followers")),
            "text": text,
            "url": _first(item, "url", "topLevelUrl"),
            "thumbnail": thumb,
            "location": None,
            "posted_at": _ts(_first(item, "time", "timestamp")),
            "likes": _int(_first(item, "likes", "topReactionsCount", "reactionsCount")),
            "comments": _int(_first(item, "comments", "commentsCount")),
            "shares": _int(_first(item, "shares", "sharesCount")),
            "views": _int(_first(item, "viewsCount", "videoViewCount")),
            "hashtags": extract_hashtags(text),
            "mentions": extract_mentions(text),
        }
    else:
        return None
    if not native or not post["posted_at"]:
        return None
    post["platform"] = platform
    if post["author"]:
        post["author"] = str(post["author"]).lstrip("@").lower()
    return post
