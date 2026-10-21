"""Hoe bijzonder doet een post het? Vergeleken met wat normaal is.

Een post van 2 uur oud heeft minder views dan een post van 3 dagen oud, ook als
hij het veel beter doet. Daarom vergelijken we elke post met posts van dezelfde
leeftijd (op het moment van meten) op hetzelfde platform. De "gewone" post is de
mediaan van de relevante posts van de afgelopen 7 dagen.

- views ×    views vergeleken met de gewone post van dezelfde leeftijd
- likes ×    likes per view vergeleken met normaal (of likes, als er geen views zijn)
- gedeeld ×  shares per view vergeleken met normaal: wordt hij vaak doorgestuurd?
- bereik ×   views gedeeld door het aantal volgers van de maker

Een **doorbraak** is een post van een kleine maker (minder dan 20.000 volgers)
die veel meer mensen bereikt dan hij volgers heeft, of een post die tien keer
zoveel views haalt als normaal voor zijn leeftijd. Precies het "onbekende maker
gaat viraal"-moment.
"""
from __future__ import annotations

import statistics
from datetime import timedelta

from . import db

SMALL_CREATOR = 20_000
MIN_BREAKOUT_VIEWS = 5_000


def _median(values: list[float]) -> float:
    values = [v for v in values if v > 0]
    return statistics.median(values) if values else 0.0


def _age_hours(p) -> float:
    keys = p.keys()
    taken = p["fetched_at"] if "fetched_at" in keys else None
    end = db.parse_iso(taken) if taken else db.now()
    return max(0.5, (end - db.parse_iso(p["posted_at"])).total_seconds() / 3600)


# Leeftijd bij het meten, in uren: tot 6 uur, tot een dag, tot 3 dagen, ouder.
AGE_BUCKETS = (6, 24, 72, 10**9)
MIN_BUCKET = 15


def _bucket(age_h: float) -> int:
    return next(i for i, limit in enumerate(AGE_BUCKETS) if age_h <= limit)


def baselines(conn, days: int = 7, include_demo: bool = True) -> dict:
    since = db.iso(db.now() - timedelta(days=days))
    q = ("SELECT platform, likes, comments, shares, views, posted_at, fetched_at FROM posts "
         "WHERE posted_at >= ? AND relevance >= 0.35 AND platform != 'nieuws'")
    if not include_demo:
        q += " AND demo = 0"
    raw: dict[str, dict] = {}
    for p in conn.execute(q + " ORDER BY posted_at DESC LIMIT 20000", (since,)):
        d = raw.setdefault(p["platform"], {"likes": [], "like_rate": [], "share_rate": [],
                                           "views_by_age": {i: [] for i in range(len(AGE_BUCKETS))},
                                           "likes_by_age": {i: [] for i in range(len(AGE_BUCKETS))}})
        age = _bucket(_age_hours(p))
        d["likes"].append(p["likes"] or 0)
        d["likes_by_age"][age].append(p["likes"] or 0)
        if p["views"]:
            d["views_by_age"][age].append(p["views"])
            d["like_rate"].append((p["likes"] or 0) / p["views"])
            d["share_rate"].append((p["shares"] or 0) / p["views"])
    out = {}
    for plat, d in raw.items():
        all_views = [v for vals in d["views_by_age"].values() for v in vals]
        all_likes = d["likes"]
        out[plat] = {
            "like_rate": _median(d["like_rate"]),
            "share_rate": _median(d["share_rate"]),
            # Te weinig posts van een leeftijd? Dan vergelijken we met alles.
            "views": {i: _median(v if len(v) >= MIN_BUCKET else all_views)
                      for i, v in d["views_by_age"].items()},
            "likes": {i: _median(v if len(v) >= MIN_BUCKET else all_likes)
                      for i, v in d["likes_by_age"].items()},
            "n": len(all_likes),
        }
    return out


def _ratio(value: float, base: float) -> float | None:
    if not base or value <= 0:
        return None
    return round(value / base, 1)


def of_post(p, base: dict) -> dict:
    """Signalen van één post. `p` is een database-rij of dict."""
    b = base.get(p["platform"]) or {}
    views = p["views"] or 0
    likes = p["likes"] or 0
    shares = p["shares"] or 0
    followers = p["author_followers"] or 0
    age = _bucket(_age_hours(p))
    out = {
        "views_x": _ratio(views, (b.get("views") or {}).get(age, 0)),
        "likes_x": (_ratio(likes / views, b.get("like_rate", 0)) if views
                    else _ratio(likes, (b.get("likes") or {}).get(age, 0))),
        "shares_x": _ratio(shares / views, b.get("share_rate", 0)) if views and shares else None,
        "reach_x": round(views / followers, 1) if views and followers else None,
        "followers": followers or None,
    }
    small = 0 < followers < SMALL_CREATOR
    out["breakout"] = bool(
        views >= MIN_BREAKOUT_VIEWS and (
            (small and (out["reach_x"] or 0) >= 5 and (out["views_x"] or 0) >= 3)
            or (out["views_x"] or 0) >= 10
        )
    )
    out["small_creator"] = small
    return out


def labels(sig: dict) -> list[str]:
    """Korte labels voor in de interface; alleen wat echt opvalt (≥ 2×)."""
    out = []
    if sig.get("breakout"):
        out.append("doorbraak")
    for key, name in (("views_x", "views"), ("likes_x", "likes"), ("shares_x", "gedeeld")):
        v = sig.get(key)
        if v and v >= 2:
            out.append(f"{name} {v:g}×")
    return out


def topic_summary(posts_signals: list[dict]) -> dict:
    """Samenvatting over alle posts van één onderwerp."""
    def med(key):
        vals = [s[key] for s in posts_signals if s.get(key)]
        return round(statistics.median(vals), 1) if vals else None
    return {
        "views": sum((s.get("_views") or 0) for s in posts_signals),
        "views_x": med("views_x"),
        "likes_x": med("likes_x"),
        "shares_x": med("shares_x"),
        "breakouts": sum(1 for s in posts_signals if s.get("breakout")),
    }
