"""Smaakprofiel: wat de tool leert van Mijn lijst.

Alles wat je bewaart, zegt iets over wat jij interessant vindt: een snack
(kipcorn), een woordcombinatie (loaded kipcorn), een soort vondst (een twist,
een combinatie, nieuw op de kaart), een maker of een stad. De tool telt die
kenmerken en geeft nieuwe posts die erop lijken voorrang op Vandaag.
Wat je op 'afgevallen' zet, telt juist tegen.

Het profiel is bewust eenvoudig en zichtbaar: op Vandaag zie je wat de tool
van je lijst heeft geleerd, en bij elke kandidaat waarop hij lijkt.
"""
from __future__ import annotations

import json
from collections import defaultdict

from . import classify

# Hoe zwaar een overeenkomst telt. Een woordcombinatie is specifiek, een stad niet.
WEIGHTS = {"zin": 2.0, "twist": 2.0, "combinatie": 2.0, "zaak": 2.0, "maker": 1.5,
           "snack": 1.0, "label": 0.5, "stad": 0.3}
LABELS = {"nieuw_op_kaart": "nieuw op de kaart", "twist": "twists", "combinatie": "combinaties"}
MAX_BONUS = 3.0
# Bij gelijke punten: het meest zeggende kenmerk eerst.
ORDER = ("twist", "combinatie", "zin", "zaak", "maker", "snack", "label", "stad")


def features(text: str = "", hashtags=(), phrases=(), flags=(), author: str | None = None,
             platform: str | None = None, places=(), city: str | None = None) -> set[str]:
    """Kenmerken van een post, zaak of onderwerp, als 'soort:waarde'."""
    t = " " + (text or "").lower() + " "
    out = {f"snack:{g}" for g in classify.item_groups(t, list(hashtags))}
    out |= {f"zin:{p.lower()}" for p in phrases if " " in p}
    for f in flags:
        kind, _, value = f.partition(":")
        out.add(f"label:{kind}")
        if value:
            out.add(f"{kind}:{value}")
    if author and platform:
        out.add(f"maker:{platform}:{author.lower()}")
    out |= {f"zaak:{_zaak(p)}" for p in places if p}
    if city:
        out.add(f"stad:{city}")
    return out


def _zaak(name: str) -> str:
    """'Snackbar De Hoek, Rotterdam' en '@snackbardehoek' als vergelijkbare sleutel."""
    if ", " in name:
        name = name.rsplit(", ", 1)[0]
    return name.lstrip("@").lower().strip()


def post_features(row) -> set[str]:
    def js(key):
        try:
            return json.loads(row[key] or "[]")
        except (KeyError, IndexError, ValueError):
            return []
    return features(row["text"], js("hashtags"), js("phrases"), js("flags"), row["author"],
                    row["platform"], js("places"), row["city"])


def _item_features(conn, item) -> set[str]:
    kind, ref = item["kind"], item["ref"]
    if kind == "post":
        row = conn.execute("SELECT * FROM posts WHERE id = ?", (ref,)).fetchone()
        if row:
            return post_features(row)
        return features(item["title"], city=item["city"])
    if kind == "onderwerp":
        typ, _, name = ref.partition("|")
        name = name or ref
        out = features(name, phrases=[name])
        if typ == "zaak":
            out.add(f"zaak:{_zaak(name)}")
        elif typ == "woord":
            out.add(f"zin:{name.lower()}")
        # Een nieuw woord als 'loadedkipcorn' of een zin als 'loaded kipcorn': kijk ook naar de twist.
        twist = classify.find_twist(f" {name.lower()} ", [name.lower().replace(" ", "")])
        if twist:
            out |= {"label:twist", f"twist:{twist}"}
        return out
    if kind == "zaak":
        return {f"zaak:{_zaak(ref)}"} | ({f"stad:{item['city']}"} if item["city"] else set())
    # product: de snack in de naam telt, niet de supermarkt
    return features(item["title"])


def profile(conn) -> dict[str, float]:
    """{kenmerk: gewicht}. Bewaard telt +1, afgevallen -1, gereviewd +0,5 (al gedaan)."""
    weights: dict[str, float] = defaultdict(float)
    for item in conn.execute("SELECT kind, ref, title, city, status FROM watchlist"):
        sign = {"afgevallen": -1.0, "gereviewd": 0.5}.get(item["status"], 1.0)
        for f in _item_features(conn, item):
            weights[f] += sign
    return {f: w for f, w in weights.items() if w}


def match(prof: dict[str, float], feats: set[str]) -> tuple[float, list[str]]:
    """(bonus, waarop het lijkt). Hoe specifieker de overeenkomst, hoe meer punten.

    Een algemeen kenmerk (een soort vondst, een stad) telt alleen mee naast een
    specifiek kenmerk; anders lijkt elke combinatie op je lijst.
    """
    if not prof:
        return 0.0, []
    specific, general, hits = 0.0, 0.0, {}
    for f in feats:
        w = prof.get(f)
        if not w:
            continue
        kind = f.split(":", 1)[0]
        points = WEIGHTS.get(kind, 0.5) * max(-2.0, min(2.0, w))
        if kind in ("label", "stad"):
            general += points
            continue
        specific += points
        if w > 0:
            name = label(f)
            rank = (points, -ORDER.index(kind) if kind in ORDER else -len(ORDER))
            hits[name] = max(hits.get(name, rank), rank)
    if not specific:
        return 0.0, []
    score = specific + general
    best = sorted(hits, key=hits.get, reverse=True)[:2]
    return max(-MAX_BONUS, min(MAX_BONUS, score)), best


def label(feature: str) -> str:
    kind, _, value = feature.partition(":")
    if kind == "label":
        return LABELS.get(value, value)
    if kind == "maker":
        return "@" + value.split(":", 1)[-1]
    return value


def summary(prof: dict[str, float], limit: int = 8) -> list[dict]:
    """Wat de tool van je lijst heeft geleerd, voor op Vandaag."""
    def rank(f, w):
        kind = f.split(":", 1)[0]
        return (WEIGHTS.get(kind, 0.5) * w, -ORDER.index(kind) if kind in ORDER else -len(ORDER))
    rows = [(rank(f, w), f, w) for f, w in prof.items() if w > 0 and not f.startswith("stad:")]
    rows.sort(reverse=True)
    out, seen = [], set()
    for _, f, w in rows:
        if label(f) in seen:
            continue
        seen.add(label(f))
        out.append({"kenmerk": label(f), "soort": f.split(":", 1)[0], "keer": w})
        if len(out) >= limit:
            break
    return out
