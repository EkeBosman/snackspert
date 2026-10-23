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


# `since` (JJJJ-MM-DD) vraagt de actor alleen posts vanaf die datum terug te geven.
# Apify rekent per resultaat, dus posts die we al hebben willen we niet nog eens
# betalen. Negeert een actor het veld, dan zie je dat terug als een hoog
# percentage 'dubbel' bij de bron.

def _ig_hashtag_input(values, limit, since=None):
    out = {"hashtags": values, "resultsLimit": limit, "resultsType": "posts"}
    if since:
        out["onlyPostsNewerThan"] = since
    return out


def _ig_profile_input(values, limit, since=None):
    out = {"directUrls": [f"https://www.instagram.com/{v}/" for v in values],
           "resultsType": "posts", "resultsLimit": limit, "addParentData": False}
    if since:
        out["onlyPostsNewerThan"] = since
    return out


def _ig_post_input(urls, limit, since=None):
    # Herhaalmeting: de actuele cijfers van losse posts.
    return {"directUrls": urls, "resultsType": "posts", "resultsLimit": 1, "addParentData": False}


def _tt_input(kind):
    def build(values, limit, since=None):
        base = {"resultsPerPage": limit, "shouldDownloadVideos": False,
                "shouldDownloadCovers": False, "shouldDownloadSubtitles": False,
                "shouldDownloadSlideshowImages": False}
        if kind == "hashtag":
            base["hashtags"] = values
        elif kind == "account":
            base["profiles"] = values
            # Nieuwste eerst, zonder vastgezette video's: dan werkt het datumfilter
            # en betaal je alleen voor wat er sinds de vorige keer bij kwam.
            base["profileSorting"] = "latest"
            base["excludePinnedPosts"] = True
        elif kind == "post":
            base["postURLs"] = values
            base["resultsPerPage"] = 1
        else:
            base["searchQueries"] = values
            base["searchSection"] = "/video"
        if kind != "post":
            base["proxyCountryCode"] = "NL"   # Nederlandse resultaten
        if since and kind != "post":
            base["oldestPostDateUnified"] = since
        return base
    return build


def _fb_input(values, limit, since=None):
    out = {"startUrls": [{"url": v if v.startswith("http") else f"https://www.facebook.com/{v}"}
                         for v in values],
           "resultsLimit": limit}
    if since:
        out["onlyPostsNewerThan"] = since
    return out


# (platform, soort) -> (actor-id, invoerbouwer)
ACTORS = {
    ("instagram", "hashtag"): ("apify~instagram-hashtag-scraper", _ig_hashtag_input),
    ("instagram", "account"): ("apify~instagram-scraper", _ig_profile_input),
    ("instagram", "post"): ("apify~instagram-scraper", _ig_post_input),
    ("tiktok", "hashtag"): ("clockworks~tiktok-scraper", _tt_input("hashtag")),
    ("tiktok", "account"): ("clockworks~tiktok-scraper", _tt_input("account")),
    ("tiktok", "zoekterm"): ("clockworks~tiktok-scraper", _tt_input("zoekterm")),
    ("tiktok", "post"): ("clockworks~tiktok-scraper", _tt_input("post")),
    ("facebook", "account"): ("apify~facebook-posts-scraper", _fb_input),
}


class ApifyError(RuntimeError):
    pass


class ApifyLimitError(ApifyError):
    """Het tegoed of de limiet van je Apify-account is op: verder proberen heeft geen zin."""


class ApifyRunFailed(ApifyError):
    """Een run is gestart (en kost dus geld), maar daarna ging er iets mis.

    De tool telt dan voorlopig het maximum en haalt de echte kosten en de al
    betaalde resultaten de volgende ronde op (zie collector.step_reconcile_apify).
    """

    def __init__(self, message: str, run_id: str, max_usd: float, dataset_id: str | None = None):
        super().__init__(message)
        self.run_id, self.max_usd, self.dataset_id = run_id, max_usd, dataset_id


def _is_limit_error(status: int, text: str) -> bool:
    low = text.lower()
    return status == 402 or ("usage" in low and any(w in low for w in ("limit", "exceed", "upgrade", "plan")))


def account_usage() -> dict | None:
    """Wat je Apify-account deze maand gebruikt heeft en wat de limiet is (in dollars).

    Dat is iets anders dan het budget in de tool: het gratis Apify-plan heeft
    $5 per maand, ook als je in de tool €60 instelt. None als Apify het niet geeft.
    """
    try:
        # Kort en zonder tweede poging: lukt het niet, dan gaat de ronde gewoon door.
        r = requests.get(f"{API}/users/me/limits", headers=_auth(), timeout=15)
    except requests.RequestException:
        return None
    if not r.ok:
        return None
    d = (r.json() or {}).get("data") or {}
    used = (d.get("current") or {}).get("monthlyUsageUsd")
    limit = (d.get("limits") or {}).get("maxMonthlyUsageUsd")
    if used is None or limit is None:
        return None
    cycle = d.get("monthlyUsageCycle") or {}
    return {"used_usd": round(float(used), 2), "limit_usd": round(float(limit), 2),
            "cycle_start": cycle.get("startAt"), "cycle_end": cycle.get("endAt")}


def available() -> bool:
    return bool(config.secret("APIFY_TOKEN"))


def supports(platform: str, kind: str) -> bool:
    return (platform, kind) in ACTORS


def _auth() -> dict:
    # In een header en niet in de URL, zodat de sleutel nooit in een foutmelding staat.
    return {"Authorization": f"Bearer {config.secret('APIFY_TOKEN')}"}


# Sommige actors (zoals de TikTok-scraper) weigeren een run met een
# maximumbedrag onder $0,50. Het echte plafond is dan `maxItems`: Apify rekent
# per resultaat, dus minder resultaten betekent minder kosten.
MIN_CHARGE_USD = 0.50

# Velden die het resultaat verbeteren maar niet nodig zijn om te werken.
OPTIONAL_KEYS = {"searchSection", "proxyCountryCode", "profileSorting", "excludePinnedPosts",
                 "oldestPostDateUnified", "onlyPostsNewerThan"}


RETRY_WAIT_S = 20


def _get(url: str, **kw):
    """GET met één nieuwe poging bij een netwerkfout: opvragen kost niets extra."""
    try:
        return requests.get(url, **kw)
    except (requests.ConnectionError, requests.Timeout):
        time.sleep(RETRY_WAIT_S)
        return requests.get(url, **kw)


def _never_sent(exc: Exception) -> bool:
    """Kwam de verbinding met Apify niet eens tot stand (DNS, geen internet)?

    Alleen dan is zeker dat Apify het verzoek niet ontving. Een verbinding die
    wegvalt terwijl Apify al bezig is, geeft óók een ConnectionError; opnieuw
    starten zou dan een tweede, betaalde run zijn.
    """
    from urllib3.exceptions import NewConnectionError  # ook DNS-fouten (NameResolutionError)

    if isinstance(exc, requests.ConnectTimeout):
        return True
    reason = getattr(exc.args[0], "reason", None) if exc.args else None
    return isinstance(reason, NewConnectionError) or isinstance(exc.args[0] if exc.args else None,
                                                                 NewConnectionError)


def _start(url: str, **kw):
    """Run starten, met één nieuwe poging als de verbinding niet eens tot stand kwam."""
    try:
        return requests.post(url, **kw)
    except requests.ConnectionError as exc:
        if not _never_sent(exc):
            raise
        time.sleep(RETRY_WAIT_S)
        return requests.post(url, **kw)


def run_actor(platform: str, kind: str, values: list[str], per_value: int,
              max_usd: float, since: str | None = None, price_per_1000: float = 0.0,
              timeout_s: int = 900) -> tuple[list[dict], float]:
    """Start een actor-run, wacht tot hij klaar is en geef (items, kosten_usd)."""
    actor, build = ACTORS[(platform, kind)]
    headers = _auth()
    max_items = per_value * len(values)
    params = {
        "maxItems": max_items,
        "maxTotalChargeUsd": f"{max(MIN_CHARGE_USD, max_usd):.2f}",
        "waitForFinish": 60,
    }
    body = build(values, per_value, since)
    resp = _start(f"{API}/acts/{actor}/runs", params=params, headers=headers, json=body, timeout=90)
    if resp.status_code == 400 and OPTIONAL_KEYS & body.keys():
        # Kent de actor een van de extra velden niet (meer)? Probeer het zonder,
        # zodat één verkeerde veldnaam niet de hele ronde kost.
        log.warning("%s weigerde de invoer, opnieuw zonder extra velden: %s", actor, resp.text[:200])
        body = {k: v for k, v in body.items() if k not in OPTIONAL_KEYS}
        resp = _start(f"{API}/acts/{actor}/runs", params=params, headers=headers, json=body, timeout=90)
    if resp.status_code >= 400:
        if _is_limit_error(resp.status_code, resp.text):
            raise ApifyLimitError(f"{actor}: {resp.status_code} {resp.text[:300]}")
        raise ApifyError(f"{actor}: {resp.status_code} {resp.text[:300]}")
    run = resp.json()["data"]
    cap = max(MIN_CHARGE_USD, max_usd)
    try:
        return _finish_run(actor, run, headers, max_items, price_per_1000, timeout_s)
    except Exception as exc:  # noqa: BLE001 - de run loopt en kost geld: nooit stil laten verdwijnen
        try:
            requests.post(f"{API}/actor-runs/{run['id']}/abort", headers=headers, timeout=15)
        except requests.RequestException:
            pass
        raise ApifyRunFailed(f"{actor}: run {run['id']} onderbroken ({exc})", run["id"], cap,
                             run.get("defaultDatasetId")) from exc


def _finish_run(actor, run, headers, max_items, price_per_1000, timeout_s) -> tuple[list[dict], float]:
    deadline = time.time() + timeout_s
    while run.get("status") in ("READY", "RUNNING") and time.time() < deadline:
        time.sleep(10)
        r = _get(f"{API}/actor-runs/{run['id']}", headers=headers, params={"waitForFinish": 60}, timeout=90)
        r.raise_for_status()
        run = r.json()["data"]

    if run.get("status") in ("READY", "RUNNING"):
        try:
            requests.post(f"{API}/actor-runs/{run['id']}/abort", headers=headers, timeout=30)
        except requests.RequestException:
            pass
        log.warning("%s duurde te lang en is afgebroken", actor)

    items: list[dict] = []
    dataset = run.get("defaultDatasetId")
    if dataset:
        r = _get(f"{API}/datasets/{dataset}/items", headers=headers,
                 params={"clean": "true", "format": "json", "limit": max_items}, timeout=120)
        r.raise_for_status()
        items = r.json()
    if run.get("status") not in ("SUCCEEDED", "ABORTED", "TIMED-OUT") and not items:
        raise ApifyError(f"{actor}: run eindigde met status {run.get('status')}")
    # De kosten staan soms pas even na afloop in de run; vraag ze nog één keer op.
    try:
        r = requests.get(f"{API}/actor-runs/{run['id']}", headers=headers, timeout=30)
        if r.ok:
            run = r.json()["data"]
    except requests.RequestException:
        pass
    reported = float(run.get("usageTotalUsd") or 0.0)
    # Meldt Apify (nog) niets, tel dan de prijs per resultaat: liever te hoog
    # dan te laag ingeschat, anders loopt het budget ongemerkt uit.
    estimated = len(items) * price_per_1000 / 1000
    return items, max(reported, estimated)


FINAL = ("SUCCEEDED", "FAILED", "ABORTED", "TIMED-OUT")


def run_info(run_id: str) -> dict | None:
    """Status, kosten en dataset van een eerdere run (voor het rechtzetten na een onderbreking)."""
    try:
        r = requests.get(f"{API}/actor-runs/{run_id}", headers=_auth(), timeout=30)
    except requests.RequestException:
        return None
    if not r.ok:
        return None
    d = r.json().get("data") or {}
    return {"status": d.get("status"), "usage_usd": float(d.get("usageTotalUsd") or 0.0),
            "dataset": d.get("defaultDatasetId")}


def dataset_items(dataset_id: str, limit: int = 1000) -> list[dict]:
    r = _get(f"{API}/datasets/{dataset_id}/items", headers=_auth(),
             params={"clean": "true", "format": "json", "limit": limit}, timeout=120)
    r.raise_for_status()
    return r.json()


def abort(run_id: str) -> None:
    try:
        requests.post(f"{API}/actor-runs/{run_id}/abort", headers=_auth(), timeout=15)
    except requests.RequestException:
        pass



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
