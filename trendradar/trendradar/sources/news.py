"""Nieuws over nieuwe producten en zaken, via Google News-RSS (gratis).

Supermarkten en vakmedia melden nieuwe producten vaak eerder dan dat er
social posts over komen. Eigen RSS-feeds kun je toevoegen in Instellingen.
"""
from __future__ import annotations

import hashlib
import xml.etree.ElementTree as ET
from email.utils import parsedate_to_datetime
from urllib.parse import quote_plus

import requests

from .. import db

GOOGLE_NEWS = "https://news.google.com/rss/search?q={q}+when:7d&hl=nl&gl=NL&ceid=NL:nl"
HEADERS = {"User-Agent": "Mozilla/5.0 (X11; CrOS x86_64) Snackspert-Trendradar/1.0"}


def parse_feed(xml_text: str, query: str) -> list[dict]:
    root = ET.fromstring(xml_text)
    items = []
    for item in root.iter("item"):
        title = (item.findtext("title") or "").strip()
        link = (item.findtext("link") or "").strip()
        if not title:
            continue
        pub = item.findtext("pubDate")
        try:
            published = db.iso(parsedate_to_datetime(pub)) if pub else db.iso(db.now())
        except (TypeError, ValueError):
            published = db.iso(db.now())
        source = item.find("source")
        outlet = source.text.strip() if source is not None and source.text else ""
        if not outlet and " - " in title:
            outlet = title.rsplit(" - ", 1)[1]
        items.append({
            "id": "nieuws:" + hashlib.sha1((link or title).encode()).hexdigest()[:16],
            "title": title,
            "url": link,
            "outlet": outlet,
            "published_at": published,
            "query": query,
        })
    return items


def fetch(queries: list[str], extra_feeds: list[str]) -> tuple[list[dict], list[str]]:
    items: list[dict] = []
    errors: list[str] = []
    targets = [(q, GOOGLE_NEWS.format(q=quote_plus(f'"{q}"' if " " in q else q))) for q in queries]
    targets += [(url, url) for url in extra_feeds]
    for label, url in targets:
        try:
            r = requests.get(url, headers=HEADERS, timeout=30)
            r.raise_for_status()
            items.extend(parse_feed(r.text, label))
        except (requests.RequestException, ET.ParseError) as exc:
            errors.append(f"nieuws '{label}': {exc}")
    return items, errors
