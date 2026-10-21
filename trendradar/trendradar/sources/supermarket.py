"""Nieuwe supermarktproducten (experimenteel).

Supermarkten hebben geen officiële open API. Deze module gebruikt de
onofficiële app-API's van Albert Heijn en Jumbo, die ook door hun eigen apps
worden gebruikt. Die kunnen zonder waarschuwing veranderen of geblokkeerd
worden; dan staat de status in de interface op rood en draait de rest gewoon
door.

Hoe 'nieuw' wordt bepaald: bij de eerste keer ophalen leggen we vast wat er in
de snack-categorieën ligt (de nulmeting). Alles wat daarna voor het eerst
opduikt, telt als nieuw. Producten met een 'nieuw'-label van de winkel zelf
tellen meteen als nieuw.
"""
from __future__ import annotations

import json
import logging

import requests

log = logging.getLogger(__name__)

# Breed genoeg om nieuwkomers te zien, smal genoeg om het snel te houden.
# Elke zoekterm is één verzoek; de supermarkt-API's zijn gratis.
QUERIES = [
    "nieuw", "nieuwe smaak", "limited edition",
    "chips", "tortilla chips", "snacks", "borrelhapjes", "borrelnoten", "nootjes", "popcorn",
    "zoutjes", "crackers", "frituursnacks", "diepvriessnacks", "kroket", "bitterballen",
    "frikandel", "loempia", "kipnuggets", "friet", "airfryer", "pizza", "snackpizza",
    "kant en klaar", "maaltijdsalade", "wraps", "dip", "saus", "mayonaise", "ketchup",
    "ijs", "softijs", "chocolade", "chocoladereep", "koekjes", "snoep", "drop", "mueslireep",
    "frisdrank", "energiedrank", "ijsthee", "sportdrank", "milkshake", "proteine",
]

UA = "Appie/8.22.3 Model/phone Android/13"


class StoreError(RuntimeError):
    pass


def _has_new_label(product: dict, keys: tuple[str, ...]) -> bool:
    for key in keys:
        if key in product and "nieuw" in json.dumps(product[key], ensure_ascii=False).lower():
            return True
    return False


def fetch_ah(queries: list[str] = QUERIES) -> list[dict]:
    session = requests.Session()
    session.headers.update({"User-Agent": UA, "x-application": "AHWEBSHOP",
                            "Content-Type": "application/json"})
    r = session.post("https://api.ah.nl/mobile-auth/v1/auth/token/anonymous",
                     json={"clientId": "appie"}, timeout=30)
    if r.status_code >= 400:
        raise StoreError(f"AH-token geweigerd ({r.status_code})")
    session.headers["Authorization"] = f"Bearer {r.json()['access_token']}"

    products: dict[str, dict] = {}
    for q in queries:
        r = session.get("https://api.ah.nl/mobile-services/product/search/v2",
                        params={"query": q, "sortOn": "RELEVANCE", "page": 0, "size": 60},
                        timeout=30)
        if r.status_code >= 400:
            raise StoreError(f"AH-zoeken '{q}' gaf {r.status_code}")
        for p in r.json().get("products", []):
            pid = p.get("webshopId") or p.get("hqId")
            if not pid or not p.get("title"):
                continue
            images = sorted(p.get("images") or [], key=lambda i: i.get("width", 0))
            products[f"ah:{pid}"] = {
                "id": f"ah:{pid}",
                "store": "Albert Heijn",
                "name": p["title"],
                "brand": p.get("brand"),
                "category": p.get("subCategory") or p.get("mainCategory"),
                "price": p.get("currentPrice") or p.get("priceBeforeBonus"),
                "url": f"https://www.ah.nl/producten/product/wi{pid}",
                "image": images[len(images) // 2]["url"] if images else None,
                "labelled_new": _has_new_label(p, ("propertyIcons", "shield", "stickers",
                                                   "highlights", "descriptionHighlights")),
            }
    return list(products.values())


def fetch_jumbo(queries: list[str] = QUERIES) -> list[dict]:
    products: dict[str, dict] = {}
    headers = {"User-Agent": "Jumbo/10.0 (Android)"}
    for q in queries:
        r = requests.get("https://mobileapi.jumbo.com/v17/search",
                         params={"q": q, "limit": 30, "offset": 0}, headers=headers, timeout=30)
        if r.status_code >= 400:
            raise StoreError(f"Jumbo-zoeken '{q}' gaf {r.status_code}")
        for p in (r.json().get("products") or {}).get("data", []):
            pid = p.get("id")
            if not pid or not p.get("title"):
                continue
            price = ((p.get("prices") or {}).get("price") or {}).get("amount")
            views = ((p.get("imageInfo") or {}).get("primaryView") or [])
            products[f"jumbo:{pid}"] = {
                "id": f"jumbo:{pid}",
                "store": "Jumbo",
                "name": p["title"],
                "brand": p.get("brand"),
                "category": p.get("topLevelCategory"),
                "price": price / 100 if isinstance(price, (int, float)) else None,
                "url": f"https://www.jumbo.com/producten/{pid}",
                "image": views[0].get("url") if views else None,
                "labelled_new": _has_new_label(p, ("badgeDescription", "badges", "stickers", "labels")),
            }
    return list(products.values())


STORES = {"Albert Heijn": fetch_ah, "Jumbo": fetch_jumbo}
