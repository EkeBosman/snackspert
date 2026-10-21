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

import requests

DATA_URL = "https://raw.githubusercontent.com/supermarkt/checkjebon/main/data/supermarkets.json"

# checkjebon-code -> naam zoals in de rest van de tool (lexicon.SUPERMARKETS)
STORE_NAMES = {
    "ah": "Albert Heijn", "jumbo": "Jumbo", "lidl": "Lidl", "aldi": "Aldi", "plus": "Plus",
    "dirk": "Dirk", "hoogvliet": "Hoogvliet", "dekamarkt": "DekaMarkt", "spar": "Spar",
    "vomar": "Vomar", "poiesz": "Poiesz", "ekoplaza": "Ekoplaza", "coop": "Coop",
    "janlinders": "Jan Linders", "picnic": "Picnic",
}


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
