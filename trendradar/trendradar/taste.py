"""Smaakprofiel: wat de tool leert van jou.

Vier bronnen zeggen iets over wat jij interessant vindt:

- Mijn lijst: wat je met ☆ bewaart (+1), afgevallen (-1), gereviewd (+0,5)
- ♥ en 👎 bij posts: waarderen zonder te bewaren (+0,7 en -0,7)
- je tips (Tips & routes): zaken en hun specialiteit (+0,5)
- je eigen posts: welke snacks het bij jouw publiek goed doen (zie ownposts.py)

De eerste drie leveren kenmerken op: een snack (kipcorn), een woordcombinatie
(loaded kipcorn), een twist, een combinatie, een zaak, een maker of een stad.
De tool telt die kenmerken en geeft nieuwe posts die erop lijken voorrang op
Vandaag.

Het profiel is bewust eenvoudig en zichtbaar: op Vandaag zie je wat de tool
heeft geleerd, en bij elke kandidaat waarop hij lijkt.
"""
from __future__ import annotations

import functools
import json
import re
from collections import defaultdict

from . import classify, lexicon

# Hoe zwaar een overeenkomst telt. Een woordcombinatie is specifiek, een stad niet.
WEIGHTS = {"zin": 2.0, "twist": 2.0, "combinatie": 2.0, "zaak": 2.0, "maker": 1.5,
           "snack": 1.0, "label": 0.5, "stad": 0.3}
# Een snack telt hooguit één keer mee: 99 burgertips maken niet elke burger-post een kandidaat.
CAPS = {"snack": 1.0}
LABELS = {"nieuw_op_kaart": "nieuw op de kaart", "twist": "twists", "combinatie": "combinaties"}
MAX_BONUS = 3.0
# Bij gelijke punten: het meest zeggende kenmerk eerst.
ORDER = ("twist", "combinatie", "zin", "zaak", "maker", "snack", "label", "stad")
STRONG = ("twist", "combinatie", "zin", "zaak", "maker")

FEEDBACK_WEIGHT = 0.7
SPOT_WEIGHT = 0.5
_TOWNS = {re.sub(r"[^a-z0-9]", "", classify.norm(t)) for t in (*lexicon.CITIES, *lexicon.NL_TOWNS)}


class Profile(dict):
    """{kenmerk: gewicht}, plus leesbare namen en de bronnen waaruit het komt."""

    def __init__(self):
        super().__init__()
        self.names: dict[str, str] = {}
        self.sources: dict[str, int] = {}
        self.user: dict[str, float] = {}   # gewichten uit je lijst en ♥/👎, zonder je tips

    def scan_names(self) -> dict[str, str]:
        """Zaaknamen die specifiek genoeg zijn om in de tekst van een post te zoeken."""
        if getattr(self, "_scan", None) is not None:
            return self._scan
        out = {}
        for f, w in self.items():
            if w <= 0 or not f.startswith("zaak:"):
                continue
            key = f[5:]
            display = self.names.get(f, key)
            if key in _TOWNS:
                continue
            if len(key) >= 10 or (len(key) >= 8 and " " in display.strip()):
                out[key] = f
        self._scan = out
        return out


@functools.lru_cache(maxsize=16384)
def zaak_key(name: str) -> str:
    """'Snackbar De Poppe, Coevorden', 'Snackbar de Poppe' en '@snackbardepoppe': dezelfde sleutel."""
    if ", " in name:
        name = name.rsplit(", ", 1)[0]
    return re.sub(r"[^a-z0-9]", "", classify.norm(name.lstrip("@")))


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
    out |= {f"zaak:{zaak_key(p)}" for p in places if p and zaak_key(p)}
    if city:
        out.add(f"stad:{city}")
    return out


def post_features(row, prof: Profile | None = None) -> set[str]:
    def js(key):
        try:
            return json.loads(row[key] or "[]")
        except (KeyError, IndexError, ValueError):
            return []
    out = features(row["text"], js("hashtags"), js("phrases"), js("flags"), row["author"],
                   row["platform"], js("places"), row["city"])
    if prof is not None:
        names = prof.scan_names()
        if names:
            blob = re.sub(r"[^a-z0-9]", "", classify.norm(row["text"] or ""))
            if row["author"]:
                blob += " " + zaak_key(row["author"])  # een zaak die zelf post
            out |= {f for key, f in names.items() if key in blob}
    return out


def _specialty_features(text: str) -> set[str]:
    """'broodje lammert (hamburger met kaassoufflé)': snacks, combinatie en twist."""
    t = " " + (text or "").lower() + " "
    flags = classify.find_flags(t, [], 1.0)
    return features(text, flags=[f for f in flags if f != "nieuw_op_kaart"])


def _item_features(conn, item, names: dict) -> set[str]:
    kind, ref = item["kind"], item["ref"]
    if kind == "post":
        row = conn.execute("SELECT * FROM posts WHERE id = ?", (ref,)).fetchone()
        if row:
            for place in json.loads(row["places"] or "[]"):
                names.setdefault(f"zaak:{zaak_key(place)}", place.lstrip("@"))
            return post_features(row)
        return features(item["title"], city=item["city"])
    if kind == "onderwerp":
        typ, _, name = ref.partition("|")
        name = name or ref
        out = features(name, phrases=[name])
        if typ == "zaak":
            out.add(f"zaak:{zaak_key(name)}")
            names[f"zaak:{zaak_key(name)}"] = name.lstrip("@")
        elif typ == "woord":
            out.add(f"zin:{name.lower()}")
        # Een nieuw woord als 'loadedkipcorn' of een zin als 'loaded kipcorn': kijk ook naar de twist.
        twist = classify.find_twist(f" {name.lower()} ", [name.lower().replace(" ", "")])
        if twist:
            out |= {"label:twist", f"twist:{twist}"}
        return out
    if kind == "zaak":
        names[f"zaak:{zaak_key(ref)}"] = item["title"] or ref
        return {f"zaak:{zaak_key(ref)}"} | ({f"stad:{item['city']}"} if item["city"] else set())
    # product: de snack in de naam telt, niet de supermarkt
    return features(item["title"])


def profile(conn) -> Profile:
    """Het smaakprofiel uit Mijn lijst, ♥/👎 en je tips."""
    prof = Profile()
    weights: dict[str, float] = defaultdict(float)
    n_list = 0
    for item in conn.execute("SELECT kind, ref, title, city, status FROM watchlist"):
        sign = {"afgevallen": -1.0, "gereviewd": 0.5}.get(item["status"], 1.0)
        for f in _item_features(conn, item, prof.names):
            weights[f] += sign
        n_list += 1
    likes = dislikes = 0
    for fb in conn.execute("SELECT f.value, p.* FROM feedback f JOIN posts p ON p.id = f.post_id"):
        for f in post_features(fb):
            weights[f] += FEEDBACK_WEIGHT * fb["value"]
        for place in json.loads(fb["places"] or "[]"):
            prof.names.setdefault(f"zaak:{zaak_key(place)}", place.lstrip("@"))
        likes += fb["value"] > 0
        dislikes += fb["value"] < 0
    prof.user = {f: w for f, w in weights.items() if w}
    n_spots = 0
    for s in conn.execute("SELECT name, place, specialty, status FROM spots"):
        sign = -SPOT_WEIGHT if s["status"] == "afgevallen" else SPOT_WEIGHT
        key = f"zaak:{zaak_key(s['name'])}"
        weights[key] += sign
        prof.names.setdefault(key, s["name"])
        for f in _specialty_features(s["specialty"]):
            weights[f] += sign
        n_spots += 1
    prof.update({f: w for f, w in weights.items() if abs(w) > 1e-9})
    prof.sources = {"lijst": n_list, "likes": likes, "dislikes": dislikes, "tips": n_spots}
    return prof


def _points(kind: str, w: float) -> float:
    cap = CAPS.get(kind, 2.0)
    return WEIGHTS.get(kind, 0.5) * max(-cap, min(cap, w))


def match(prof: dict[str, float], feats: set[str]) -> tuple[float, list[str], float]:
    """(bonus, waarop het lijkt, sterkte). Hoe specifieker de overeenkomst, hoe meer punten.

    Een algemeen kenmerk (een soort vondst, een stad) telt alleen mee naast een
    specifiek kenmerk; anders lijkt elke combinatie op je lijst. 'Sterkte' telt
    alleen de echt specifieke kenmerken (zin, twist, combinatie, zaak, maker):
    alleen daarmee mag een post zonder andere signalen een kandidaat worden.
    """
    if not prof:
        return 0.0, [], 0.0
    specific, general, strong, hits = 0.0, 0.0, 0.0, {}
    for f in feats:
        w = prof.get(f)
        if not w:
            continue
        kind = f.split(":", 1)[0]
        # Een losse snack telt alleen op basis van wat je zelf bewaarde, ♥ of 👎 gaf, niet uit je
        # tips: anders past elke kaassoufflé-post 'bij jou'.
        if kind == "snack" and hasattr(prof, "user"):
            w = prof.user.get(f, 0)
            if not w:
                continue
        points = _points(kind, w)
        if kind in ("label", "stad"):
            general += points
            continue
        specific += points
        if kind in STRONG:
            strong += points
        if w > 0:
            name = label(f, prof)
            rank = (points, -ORDER.index(kind) if kind in ORDER else -len(ORDER))
            hits[name] = max(hits.get(name, rank), rank)
    if not specific:
        return 0.0, [], 0.0
    score = specific + general
    best = sorted(hits, key=hits.get, reverse=True)[:2]
    return max(-MAX_BONUS, min(MAX_BONUS, score)), best, strong


def label(feature: str, prof: dict | None = None) -> str:
    names = getattr(prof, "names", {}) or {}
    if feature in names:
        return names[feature]
    kind, _, value = feature.partition(":")
    if kind == "label":
        return LABELS.get(value, value)
    if kind == "maker":
        return "@" + value.split(":", 1)[-1]
    return value


def summary(prof: dict[str, float], limit: int = 10) -> list[dict]:
    """Wat de tool heeft geleerd, voor op Vandaag. Losse tips (zaaknamen) laat hij weg."""
    def rank(f, w):
        kind = f.split(":", 1)[0]
        return (_points(kind, w), -ORDER.index(kind) if kind in ORDER else -len(ORDER))
    rows = [(rank(f, w), f, w) for f, w in prof.items()
            if w > 0 and not f.startswith("stad:")
            and not (f.split(":", 1)[0] in ("zaak", "snack") and getattr(prof, "user", {f: w}).get(f, 0) <= 0)]
    rows.sort(reverse=True)
    out, seen = [], set()
    for _, f, w in rows:
        name = label(f, prof)
        if name in seen:
            continue
        seen.add(name)
        out.append({"kenmerk": name, "soort": f.split(":", 1)[0], "keer": round(w, 1)})
        if len(out) >= limit:
            break
    return out


def rated(conn) -> set[str]:
    """Posts waar je al ♥ of 👎 bij gaf: die hoef je niet nog eens als kandidaat te zien."""
    return {r["post_id"] for r in conn.execute("SELECT post_id FROM feedback")}
