"""Koppeling met snackspert.nl: welke zaken zijn al gereviewd?

Gebruikt dezelfde WordPress REST API als de app (snackspert-app/services/api.ts).
"""
from __future__ import annotations

import difflib
import re

import requests

from .classify import norm

API = "https://snackspert.nl/wp-json/wp/v2/restaurant"
HEADERS = {"User-Agent": "Mozilla/5.0 (X11; CrOS x86_64) Snackspert-Trendradar/1.0"}

# Woorden die in bijna elke zaaknaam zitten en dus niets onderscheiden.
NOISE = {"snackbar", "cafetaria", "de", "het", "t", "friet", "frites", "grillroom",
         "shoarma", "pizzeria", "eethuis", "taqueria", "foodtruck", "grill", "restaurant",
         "bv", "v o f", "vof", "en"}


def fetch_reviewed() -> list[dict]:
    out = []
    page, pages = 1, 1
    while page <= pages:
        r = requests.get(API, params={"per_page": 100, "page": page,
                                      "_fields": "id,slug,title,link"},
                         headers=HEADERS, timeout=30)
        r.raise_for_status()
        pages = int(r.headers.get("X-WP-TotalPages", "1"))
        for item in r.json():
            name = re.sub(r"<[^>]+>", "", item["title"]["rendered"])
            name = name.replace("&amp;", "&").replace("&#8217;", "'").replace("&#038;", "&")
            out.append({"slug": item["slug"], "name": name, "url": item.get("link"),
                        "norm": core_name(name)})
        page += 1
    return out


def core_name(name: str) -> str:
    words = [w for w in norm(name.lstrip("@").replace("_", " ").replace(".", " ")).split()
             if w not in NOISE]
    return " ".join(words) or norm(name)


def match(place: str, reviewed: list[dict], threshold: float = 0.86) -> dict | None:
    key = core_name(place)
    if len(key) < 3:
        return None
    best, best_score = None, 0.0
    squashed = key.replace(" ", "")
    for r in reviewed:
        cand = r["norm"]
        if not cand:
            continue
        score = difflib.SequenceMatcher(None, squashed, cand.replace(" ", "")).ratio()
        if score > best_score:
            best, best_score = r, score
    return best if best_score >= threshold else None
