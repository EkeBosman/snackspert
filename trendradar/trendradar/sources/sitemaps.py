"""Nieuwe supermarktproducten via de openbare productlijsten (sitemaps) van de winkels.

Winkels publiceren voor zoekmachines een lijst met al hun productpagina's. De naam
van het product staat in de link ('/kesbeke-vers-gesneden-gember-citroen'). Door die
lijst te vergelijken met de vorige keer valt elk nieuw product op, ook als het geen
snackwoord in de naam heeft. Gratis, compleet en precies waarvoor zo'n lijst bedoeld is.

Niet elke winkel heeft er een met eten: Lidl's lijst is alleen de webshop (kleding,
gereedschap), Jumbo en Vomar publiceren geen productlijst. Die blijven via Apify gaan.
"""
from __future__ import annotations

import gzip
import re

import requests

USER_AGENT = "SnackspertTrendradar/1.0 (leest openbare productsitemaps)"

# Per winkel: waar de productlijst staat en hoe een productlink eruitziet.
SITEMAPS = {
    "ah": {"url": "https://www.ah.nl/sitemaps/entities/products/detail.xml",
           "pattern": r"/producten/product/(?P<id>wi\d+)/(?P<slug>[^/?#<]+)"},
    "plus": {"url": "https://www.plus.nl/ECP_Sitemap_Engine/rest/Sitemap/product",
             "pattern": r"/product/(?P<slug>[^/?#<]+?)-(?P<id>\d+)$"},
    "dirk": {"url": "https://www.dirk.nl/products-sitemap.xml",
             "pattern": r"/boodschappen/(?P<dept>[^/]+)/[^/]+/(?P<slug>[^/?#<]+)/(?P<id>\d+)$",
             # Afdelingen zonder eten of drinken.
             "skip": {"huishoud-huisdieren", "kind-drogisterij", "non-food", "non-food-inout", "bloemen-planten"}},
    "aldi": {"url": "https://www.aldi.nl/sitemaps/.aldi-nord-sitemap-products.xml",
             "pattern": r"/product/(?P<slug>[^/?#<]+?)-(?P<id>\d+)\.html$"},
}
LOC_RE = re.compile(r"<loc>\s*([^<\s]+)\s*</loc>")
MAX_FILES = 40       # een sitemap-index met meer deelbestanden is waarschijnlijk iets anders
MIN_PRODUCTS = 300   # minder producten: de lijst is (tijdelijk) kapot of geblokkeerd


class SitemapError(RuntimeError):
    pass


def _download(url: str) -> str:
    r = requests.get(url, headers={"User-Agent": USER_AGENT, "Accept-Encoding": "gzip"}, timeout=120)
    if r.status_code >= 400:
        raise SitemapError(f"{url}: {r.status_code}"
                           + (" (de winkel blokkeert dit adres)" if r.status_code in (401, 403) else ""))
    data = r.content
    if data[:2] == b"\x1f\x8b":  # .xml.gz
        data = gzip.decompress(data)
    return data.decode("utf-8", errors="replace")


def _urls(url: str) -> list[str]:
    """Alle links uit een sitemap; een sitemap-index wordt gevolgd (één niveau diep)."""
    text = _download(url)
    locs = LOC_RE.findall(text)
    if "<sitemapindex" in text[:2000]:
        out = []
        for child in locs[:MAX_FILES]:
            out += LOC_RE.findall(_download(child))
        return out
    return locs


def _name(slug: str) -> str:
    """'kesbeke-vers-gesneden-gember-citroen' -> 'Kesbeke vers gesneden gember citroen'."""
    words = re.sub(r"%[0-9a-fA-F]{2}", " ", slug).replace("-", " ").split()
    text = " ".join(words)
    return text[:1].upper() + text[1:]


def parse(code: str, urls: list[str], store: str) -> list[dict]:
    conf = SITEMAPS[code]
    pattern = re.compile(conf["pattern"])
    skip = conf.get("skip", set())
    out, seen = [], set()
    for u in urls:
        m = pattern.search(u)
        if not m or m.groupdict().get("dept") in skip:
            continue
        native = m.group("id")
        if native in seen:
            continue
        seen.add(native)
        out.append({"id": f"{code}:{native}", "store": store, "name": _name(m.group("slug")), "size": None,
                    "price": None, "url": u})
    return out


def fetch(code: str, store: str) -> list[dict]:
    """De producten van één winkel volgens zijn openbare productlijst."""
    if code not in SITEMAPS:
        raise SitemapError(f"geen productlijst bekend voor {store}")
    try:
        products = parse(code, _urls(SITEMAPS[code]["url"]), store)
    except requests.RequestException as exc:
        raise SitemapError(f"{store}: {exc}") from exc
    if len(products) < MIN_PRODUCTS:
        raise SitemapError(f"{store}: maar {len(products)} producten in de productlijst")
    return products
