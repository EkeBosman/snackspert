"""Nieuwe supermarktproducten via checkjebon.

checkjebon (github.com/supermarkt/checkjebon, MIT-licentie) verzamelt elke dag
het online assortiment van een tiental Nederlandse supermarkten en publiceert
dat als één JSON-bestand. De makers geven aan dat de data hergebruikt mag
worden. Dat is betrouwbaarder dan zelf de onofficiële app-API's van elke
winkel aanspreken: die veranderen of blokkeren zonder waarschuwing.

Hoe 'nieuw' wordt bepaald: bij de eerste keer leggen we vast wat elke winkel
verkoopt (de nulmeting). Alles wat daarna voor het eerst opduikt, is nieuw.
Een product dat even uitverkocht was en terugkomt, kennen we al en telt dus
niet opnieuw.
"""
from __future__ import annotations

import re

import requests

DATA_URL = "https://raw.githubusercontent.com/supermarkt/checkjebon/main/data/supermarkets.json"

# checkjebon-code -> naam zoals in de rest van de tool (lexicon.SUPERMARKETS)
STORE_NAMES = {
    "ah": "Albert Heijn", "jumbo": "Jumbo", "lidl": "Lidl", "aldi": "Aldi", "plus": "Plus",
    "dirk": "Dirk", "hoogvliet": "Hoogvliet", "dekamarkt": "DekaMarkt", "spar": "Spar",
    "vomar": "Vomar", "poiesz": "Poiesz", "ekoplaza": "Ekoplaza", "coop": "Coop",
    "janlinders": "Jan Linders", "picnic": "Picnic",
}


def _pick(item: dict, *keys):
    for k in keys:
        v = item.get(k)
        if v not in (None, ""):
            return v
    return None


def _price(value) -> float | None:
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        m = re.search(r"\d+(?:[.,]\d{1,2})?", value.replace("\u20ac", ""))
        return float(m.group(0).replace(",", ".")) if m else None
    if isinstance(value, dict):
        return _price(_pick(value, "now", "amount", "value", "price"))
    return None


# Per winkel de Apify-scrapers in volgorde van voorkeur. 'volledig': het hele assortiment, dan valt
# elk nieuw product op (ook 'Kesbeke gember citroen'). Lukt geen enkele, dan zoekt de tool op
# woorden met de scraper voor alle winkels: die mist alles zonder zo'n woord in de naam.
FULL_SOURCES = {
    # rashadansari: verzamelt eerst alles en levert pas aan het eind (AH ± 20 minuten).
    "ah": [{"actor": "rashadansari~albert-heijn-scraper", "input": {}}],
    "jumbo": [{"actor": "rashadansari~jumbo-scraper", "input": {}}],
    "lidl": [{"actor": "rashadansari~lidl-scraper", "input": {}}],
}
KEYWORD_ACTOR = "harvestedge~dutch-supermarkets-all-11"
MIN_FULL = 500   # een volledig assortiment met minder producten is mislukt


def sources(code: str, settings: dict) -> list[dict]:
    """De volledige scrapers voor deze winkel (eigen instelling gaat voor), dan zoeken op woorden."""
    own = (settings.get("supermarkt_bronnen") or {}).get(code)
    full = [{**s, "volledig": True} for s in (own if isinstance(own, list) else FULL_SOURCES.get(code, []))]
    return full + [{"actor": KEYWORD_ACTOR, "volledig": False}]


def parse_apify(item: dict, store: str, code: str) -> dict | None:
    """Eén product van een Apify-supermarktscraper. Veldnamen verschillen per scraper, dus ruim lezen."""
    if item.get("type") and item.get("type") != "product":
        return None  # categorieën
    name = _pick(item, "name", "title", "productName", "product_name")
    if not name:
        return None
    # Bevat het resultaat een winkel en is het een andere? Dan niet meetellen.
    shop = str(_pick(item, "supermarket", "store", "shop", "chain") or "").lower()
    if shop and shop not in (code.lower(), store.lower()) and code.lower() not in shop and store.lower() not in shop:
        return None
    url = _pick(item, "url", "productUrl", "product_url", "website_url", "websiteUrl", "link")
    size = _pick(item, "unitSize", "unit_size", "salesUnitSize", "size", "quantity", "unit")
    native = _pick(item, "webshopId", "external_id", "externalId", "id", "productId", "product_id", "sku",
                   "ean", "gtin") or url or f"{name}|{size or ''}"
    if not url and code == "ah" and str(native).isdigit():
        url = f"https://www.ah.nl/producten/product/wi{native}"
    if isinstance(url, str) and url.startswith("/"):
        url = {"ah": "https://www.ah.nl", "jumbo": "https://www.jumbo.com", "lidl": "https://www.lidl.nl"}.get(code, "") + url
    return {"id": f"{code}:{native}", "store": store, "name": str(name).strip(),
            "size": str(size) if size is not None and not isinstance(size, (dict, list)) else None,
            "price": _price(_pick(item, "current_price", "currentPrice", "price", "priceBeforeBonus",
                                  "base_price")), "url": url}


class StoreError(RuntimeError):
    pass


def fetch(etag: str | None = None) -> tuple[dict[str, list[dict]] | None, str | None]:
    """Haal het bestand op. Geeft (winkels, etag), of (None, etag) als er niets veranderd is.

    Met de etag van de vorige keer stuurt GitHub '304 Not Modified' als het
    bestand niet veranderd is; dan downloaden we de 10 MB niet opnieuw.
    """
    headers = {"User-Agent": "Snackspert-Trendradar/1.0"}
    if etag:
        headers["If-None-Match"] = etag
    r = requests.get(DATA_URL, headers=headers, timeout=120)
    if r.status_code == 304:
        return None, etag
    if r.status_code >= 400:
        raise StoreError(f"checkjebon gaf {r.status_code}")
    return parse(r.json()), r.headers.get("ETag")


def parse(data: list) -> dict[str, list[dict]]:
    stores: dict[str, list[dict]] = {}
    for store in data:
        code = store.get("n", "")
        name = STORE_NAMES.get(code, code.title())
        base = store.get("u") or ""
        items = []
        for it in store.get("d") or []:
            if not it.get("n") or not it.get("l"):
                continue
            items.append({
                "id": f"{code}:{it['l']}",
                "store": name,
                "name": it["n"].strip(),
                "size": it.get("s"),
                "price": it.get("p"),
                "url": base + it["l"] if base else None,
            })
        stores[name] = items
    return stores
