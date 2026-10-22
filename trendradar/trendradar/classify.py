"""Herkent of een post over Snackspert-terrein gaat, en waarover precies.

Twee lagen:
1. Regels (altijd, gratis): woordenlijsten uit lexicon.py.
2. Claude (optioneel, met ANTHROPIC_API_KEY): leest de posts die de regels
   twijfelachtig of relevant vinden en haalt er producten, zaken en steden uit.
"""
from __future__ import annotations

import json
import logging
import re
import unicodedata

from . import config, lexicon

log = logging.getLogger(__name__)

URL_RE = re.compile(r"https?://\S+")
HASHTAG_RE = re.compile(r"#([\wÀ-ɏ]+)", re.UNICODE)
MENTION_RE = re.compile(r"@([\w.]+)")
TOKEN_RE = re.compile(r"[a-zÀ-ɏ][a-zÀ-ɏ'’-]+")

_BRANDS = sorted({b for b in lexicon.BRANDS}, key=len, reverse=True)


def _brand_pattern(brand: str) -> re.Pattern:
    # "Lay's", "Lays" en "Lay’s" moeten allemaal matchen.
    parts = [re.escape(p) for p in re.split(r"['’]", brand.lower())]
    return re.compile(r"(?<![\w])" + "['’]?".join(parts) + r"(?![\w])")


_BRAND_PATTERNS = [(b, _brand_pattern(b)) for b in _BRANDS]


def strip_accents(text: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFKD", text) if not unicodedata.combining(c))


def norm(text: str) -> str:
    """Voor vergelijken van namen: kleine letters, geen accenten of leestekens."""
    text = strip_accents(text.lower())
    text = re.sub(r"[^a-z0-9 ]+", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def extract_hashtags(text: str) -> list[str]:
    return list(dict.fromkeys(h.lower() for h in HASHTAG_RE.findall(text or "")))


def extract_mentions(text: str) -> list[str]:
    return list(dict.fromkeys(m.lower().rstrip(".") for m in MENTION_RE.findall(text or "")))


def _keyword_hit(keyword: str, text: str, tokens: set[str], tag_blob: str) -> bool:
    if " " in keyword or len(keyword) >= 6:
        # Samenstellingen ("kipburger", "frietkot") vangen we zo ook.
        return keyword in text or keyword.replace(" ", "") in tag_blob
    return keyword in tokens or (len(keyword) >= 5 and keyword in tag_blob)


def _dutch_food(food: str, text: str, tokens: set[str], hashtags: list[str]) -> bool:
    # Hele woorden, geen stukjes: 'patat' mag niet matchen op het Spaanse 'patatas'.
    if " " in food:
        return f" {food} " in text or food.replace(" ", "") in hashtags
    if food in tokens or food in hashtags:
        return True
    return len(food) >= 6 and any(food in tag for tag in hashtags)


def find_city(text: str, hashtags: list[str], location: str | None) -> str | None:
    hay = " " + (location or "").lower() + " " + text + " "
    for city in sorted(lexicon.CITIES, key=len, reverse=True):
        c = city.lower()
        if re.search(r"(?<![\w])" + re.escape(c) + r"(?![\w])", hay):
            return "Den Bosch" if city == "'s-Hertogenbosch" else city
    tags = set(hashtags)
    if any(area in hay for area in lexicon.AMSTERDAM_AREAS) or tags & set(lexicon.AMSTERDAM_TAGS):
        return "Amsterdam"
    for town in lexicon.NL_TOWNS:
        t = town.lower()
        if re.search(r"(?<![\w])" + re.escape(t) + r"(?![\w])", hay) or t.replace("-", "") in hashtags:
            return town
    for tag in hashtags:
        for alias, city in lexicon.CITY_ALIASES.items():
            if tag.endswith(alias) or tag.startswith(alias):
                return city
        for city in lexicon.CITIES:
            c = city.lower().replace(" ", "")
            if len(c) >= 5 and c in tag:
                return city
    return None


# Woorden die duidelijk over eten gaan; een woordcombinatie moet er minstens
# één bevatten, anders komen zinnetjes als "iedereen praat" in de trends.
# 'Review', 'foodtruck' of 'supermarkt' zijn context, geen eten: die tellen hier niet mee.
_CONTEXT_CATEGORIES = {"Streetfood & events", "Supermarkt & nieuwe producten"}
_FOOD_WORDS = {w for cat, words in lexicon.CATEGORIES.items() if cat not in _CONTEXT_CATEGORIES
               for w, weight in words.items() if weight >= 0.5 and " " not in w}
_FOOD_WORDS |= {norm(b) for b in lexicon.BRANDS if " " not in norm(b)}
_FOOD_STEMS = {w for w in _FOOD_WORDS if len(w) >= 5}


def _is_food_word(word: str) -> bool:
    return word in _FOOD_WORDS or any(stem in word for stem in _FOOD_STEMS)


_KNOWN_WORDS = ({w for words in lexicon.CATEGORIES.values() for w in words}
                | lexicon.DUTCH_FOODS | lexicon.GENERIC_HASHTAGS)
_PLACE_WORDS = ("snackbar", "cafetaria", "frituur", "friettent", "foodtruck", "streetfood",
                "foodspot", "food")


def new_compounds(words: list[str]) -> list[str]:
    """Nieuwe samengestelde snackwoorden, zoals 'frikandelijs' of 'pistachekroket'.

    Een woord dat een bekende snack bevat maar zelf niet in de woordenlijst
    staat, is vaak precies de nieuwe trend. Ze komen ook uit hashtags, omdat
    makers zo'n nieuwe naam vaak alleen als hashtag schrijven; het onderwerp is
    dan het woord, niet de hashtag.
    """
    out = []
    for w in words:
        if len(w) < 8 or not w.isalpha() or w in _KNOWN_WORDS or w in out:
            continue
        if any(p in w for p in _PLACE_WORDS):
            continue
        if any(stem in w and stem != w for stem in _FOOD_STEMS):
            out.append(w)
    return out


def key_phrases(text: str, limit: int = 8, hashtags: list[str] | None = None) -> list[str]:
    """Tweewoordcombinaties zonder stopwoorden: zo duiken nieuwe dingen als
    'dubai chocolade' op zonder dat iemand ze vooraf hoeft te kennen. Plus
    nieuwe samengestelde snackwoorden (zie new_compounds)."""
    clean = URL_RE.sub(" ", text)
    clean = HASHTAG_RE.sub(" ", clean)
    clean = MENTION_RE.sub(" ", clean).lower()
    phrases: list[str] = new_compounds(TOKEN_RE.findall(clean) + list(hashtags or []))[:3]
    for sentence in re.split(r"[.!?\n,;:()\"|]+", clean):
        words = [w.strip("'’-") for w in TOKEN_RE.findall(sentence)]
        for a, b in zip(words, words[1:]):
            if a in lexicon.STOPWORDS or b in lexicon.STOPWORDS:
                continue
            if len(a) < 3 or len(b) < 3 or not (_is_food_word(a) or _is_food_word(b)):
                continue
            phrase = f"{a} {b}"
            if phrase not in phrases:
                phrases.append(phrase)
            if len(phrases) >= limit:
                return phrases
    return phrases


def item_groups(text: str, hashtags: list[str]) -> list[str]:
    """Welke herkenbare snacks en dragers (brioche, pita, suikerbrood) staan erin?"""
    found = []
    words = set(TOKEN_RE.findall(text))
    blobs = list(hashtags) + new_compounds(list(words))
    for group, keywords in lexicon.ITEM_GROUPS.items():
        hit = False
        for kw in keywords:
            k = kw.strip()
            if " " in kw or kw.endswith(" "):
                hit = f" {kw.strip()} " in text
            else:
                hit = k in words or (len(k) >= 4 and any(k in b for b in blobs))
            if hit:
                break
        # 'frikandelijs', 'bitterbalijs': ijs als laatste deel van een samenstelling.
        if not hit and group == "softijs":
            hit = any(b.endswith("ijs") and len(b) > 6 for b in blobs)
        if hit:
            found.append(group)
    return found


def find_twist(text: str, hashtags: list[str]) -> str | None:
    """'loaded kipcorn', 'gevulde kroket': een twistwoord vlak voor een bekende snack.

    Werkt ook voor hashtags als #loadedkipcorn. Geeft 'loaded kipcorn' terug,
    met de snack als groepsnaam (dus 'gevulde kroket', ook bij 'gevulde kroketten').
    """
    words = TOKEN_RE.findall(text)
    for i, w in enumerate(words[:-1]):
        if w in lexicon.TWIST_WORDS:
            for group in item_groups(f" {words[i + 1]} ", []):
                twist = f"{w} {group}"
                if twist not in lexicon.COMMON_TWISTS:
                    return twist
    for tag in hashtags:
        for tw in lexicon.TWIST_WORDS:
            if tag.startswith(tw) and len(tag) > len(tw) + 3:
                for group in item_groups(f" {tag[len(tw):]} ", []):
                    twist = f"{tw} {group}"
                    if twist not in lexicon.COMMON_TWISTS:
                        return twist
    return None


def find_flags(text: str, hashtags: list[str], relevance: float) -> list[str]:
    """Labels voor kandidaten: 'nieuw_op_kaart', 'combinatie:a + b' en 'twist:loaded kipcorn'."""
    flags = []
    if relevance >= 0.5 and any(p in text for p in lexicon.NEW_MENU_PHRASES):
        flags.append("nieuw_op_kaart")
    if relevance >= 0.5:
        twist = find_twist(text, hashtags)
        if twist:
            flags.append(f"twist:{twist}")
    groups = item_groups(text, hashtags)
    for i, a in enumerate(groups):
        for b in groups[i + 1:]:
            if frozenset((a, b)) not in lexicon.COMMON_PAIRS:
                flags.append(f"combinatie:{a} + {b}")
                return flags
    return flags


def looks_like_business(handle: str, name: str = "") -> bool:
    hay = (handle + " " + name).lower()
    return any(h in hay for h in lexicon.BUSINESS_HINTS)


def classify_rules(post: dict) -> dict:
    text_raw = post.get("text") or ""
    text = " " + text_raw.lower() + " "
    hashtags = post.get("hashtags") or extract_hashtags(text_raw)
    mentions = post.get("mentions") or extract_mentions(text_raw)
    tag_blob = " ".join(hashtags)
    tokens = set(TOKEN_RE.findall(text))

    # 'Kapsalon' is ook een kapperszaak. Gaat de post over haar, dan is het geen snack.
    hair = bool(lexicon.HAIR_WORDS & (tokens | set(hashtags)))
    categories: dict[str, float] = {}
    miss = 1.0
    for category, words in lexicon.CATEGORIES.items():
        best = 0.0
        for word, weight in words.items():
            if hair and word == "kapsalon":
                continue
            if _keyword_hit(word, text, tokens, tag_blob):
                best = max(best, weight)
                miss *= 1 - weight * 0.85
        if best >= 0.5:
            categories[category] = best
    food = 1 - miss

    brands: list[str] = []
    for brand, pattern in _BRAND_PATTERNS:
        squashed = norm(brand).replace(" ", "")
        # Korte merknamen ("Ola", "Lu") alleen als losse hashtag, anders zit
        # "ola" ook in #dubaichocolade.
        in_tags = squashed in hashtags or (len(squashed) >= 6 and squashed in tag_blob)
        if pattern.search(text) or in_tags:
            if brand.replace("’", "'") not in brands:
                brands.append(brand.replace("’", "'"))
    for store, hints in lexicon.SUPERMARKETS.items():
        if any((h in text) if " " in h or h.startswith("#") else (h in tokens or h in tag_blob)
               for h in hints):
            brands.append(store)
    is_store = any(b in lexicon.SUPERMARKETS for b in brands)
    if is_store and ("nieuw" in text or "nieuw" in tag_blob):
        categories.setdefault("Supermarkt & nieuwe producten", 1.0)
        food = max(food, 0.8)
    elif brands:
        food = min(1.0, food + 0.15)

    words = TOKEN_RE.findall(text)
    dutch = sum(1 for w in words if w in lexicon.DUTCH_WORDS)
    nl = min(1.0, dutch / max(4, len(words)) * 4) if words else 0.0
    city = find_city(text, hashtags, post.get("location"))
    if city:
        nl = min(1.0, nl + 0.5)
    if any(_dutch_food(food, text, tokens, hashtags) for food in lexicon.DUTCH_FOODS
           if not (hair and food == "kapsalon")):
        nl = min(1.0, nl + 0.5)
    if any(h in ("nederland", "holland", "netherlands", "dutchfood") for h in hashtags):
        nl = min(1.0, nl + 0.3)
    if is_store or any(b in ("FEBO", "Smullers", "Kwalitaria") for b in brands):
        nl = min(1.0, nl + 0.3)
    # Duidelijk een andere taal? Dan telt de post niet als Nederlands, ook niet
    # als er 'snackbar' of een Nederlandse plaatsnaam in staat.
    foreign = max(sum(1 for w in words if w in vocab) for vocab in lexicon.FOREIGN_WORDS.values())
    if foreign >= 2 and foreign > dutch:
        nl = min(nl, 0.1)
    if post.get("platform") in ("nieuws", "winkel"):
        nl = 1.0

    places: list[str] = []
    if post.get("location"):
        places.append(post["location"].strip())
    author = post.get("author") or ""
    if author and looks_like_business(author, post.get("author_name") or ""):
        places.append("@" + author)
    for m in mentions:
        if looks_like_business(m):
            places.append("@" + m)

    from .products import guess_from_text  # hier, om een kringverwijzing te voorkomen

    flags = find_flags(text, hashtags, round(food, 3))

    return {
        "flags": flags,
        "products": guess_from_text(text_raw, _is_food_word) if is_store or "nieuw" in text else [],
        "hashtags": hashtags,
        "mentions": mentions,
        "relevance": round(food, 3),
        "nl_score": round(nl, 3),
        "categories": sorted(categories, key=categories.get, reverse=True)[:3],
        "brands": brands[:8],
        "places": list(dict.fromkeys(places))[:5],
        "phrases": key_phrases(text_raw, hashtags=hashtags),
        "city": city,
    }


# --- Claude ----------------------------------------------------------------

AI_SCHEMA = {
    "type": "object",
    "properties": {
        "posts": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "id": {"type": "string"},
                    "relevant": {"type": "boolean"},
                    "relevantie": {"type": "number"},
                    "nederlands": {"type": "boolean"},
                    "categorieen": {"type": "array", "items": {
                        "type": "string", "enum": list(lexicon.CATEGORIES)}},
                    "producten": {"type": "array", "items": {
                        "type": "object",
                        "properties": {
                            "naam": {"type": "string"},
                            "merk": {"type": "string"},
                            "winkel": {"type": "string"},
                            "nieuw": {"type": "boolean"},
                        },
                        "required": ["naam", "merk", "winkel", "nieuw"],
                        "additionalProperties": False,
                    }},
                    "zaak": {"type": "string"},
                    "stad": {"type": "string"},
                    "sentiment": {"type": "string", "enum": ["positief", "neutraal", "negatief"]},
                    "samenvatting": {"type": "string"},
                },
                "required": ["id", "relevant", "relevantie", "nederlands", "categorieen",
                             "producten", "zaak", "stad", "sentiment", "samenvatting"],
                "additionalProperties": False,
            },
        }
    },
    "required": ["posts"],
    "additionalProperties": False,
}

AI_SYSTEM = """Je beoordeelt Nederlandse social-mediaposts voor Snackspert, een site die \
snackbars, streetfood en nieuwe supermarktproducten reviewt.

Per post geef je:
- relevant: gaat het over snacks, streetfood, een eetzaak/foodtruck, of een (nieuw) \
food-/drankproduct uit de supermarkt? Algemene recepten, restaurants met tafelservice \
en fine dining zijn niet relevant.
- relevantie: 0 tot 1, hoe interessant voor een Snackspert-review of trendanalyse.
- nederlands: gaat de post over Nederland of is hij voor Nederlanders geschreven?
- categorieen: kies uit de toegestane lijst, maximaal drie.
- producten: concrete producten met naam (bijv. "Paprika chips met limoen"), merk \
(leeg als onbekend), winkel (supermarkt of leeg) en nieuw=true als de post zegt dat het \
nieuw is.
- zaak: naam van de eetzaak/foodtruck als die genoemd wordt, anders leeg.
- stad: Nederlandse plaatsnaam als die genoemd of duidelijk is, anders leeg.
- sentiment over het eten.
- samenvatting: maximaal 12 woorden, Nederlands.

Verzin niets: wat niet in de post staat laat je leeg."""


def ai_available(settings: dict) -> bool:
    return bool(config.secret("ANTHROPIC_API_KEY")) and settings.get("ai_aan", True)


def classify_ai(posts: list[dict], settings: dict) -> tuple[dict[str, dict], float]:
    """Geeft {post_id: resultaat} en de kosten in dollars terug."""
    import anthropic

    client = anthropic.Anthropic(api_key=config.secret("ANTHROPIC_API_KEY"))
    model = settings.get("ai_model") or "claude-opus-5-5"
    payload = [
        {"id": p["id"], "platform": p["platform"], "account": p.get("author") or "",
         "locatie": p.get("location") or "", "tekst": (p.get("text") or "")[:1200]}
        for p in posts
    ]
    request = dict(
        model=model,
        max_tokens=16000,
        system=AI_SYSTEM,
        output_config={"effort": settings.get("ai_effort") or "low",
                       "format": {"type": "json_schema", "schema": AI_SCHEMA}},
        messages=[{"role": "user", "content": json.dumps(payload, ensure_ascii=False)}],
    )
    use_fallback = model in ("claude-opus-5-5", "claude-sonnet-5-5")
    try:
        if use_fallback:
            # Bij een (zeldzame) weigering van het model probeert de API het
            # zelf opnieuw met een passend ander model.
            response = client.beta.messages.create(
                betas=["server-side-fallback-2026-07-01"], fallbacks="default", **request)
        else:
            response = client.messages.create(**request)
    except anthropic.BadRequestError:
        if not use_fallback:
            raise
        response = client.messages.create(**request)

    in_price, out_price = config.ai_prices(model)
    usage = response.usage
    cost = (usage.input_tokens * in_price + usage.output_tokens * out_price) / 1_000_000

    if response.stop_reason in ("refusal", "max_tokens"):
        log.warning("AI-indeling gestopt: %s", response.stop_reason)
        return {}, cost
    text = next((b.text for b in response.content if b.type == "text"), "")
    try:
        data = json.loads(text)
    except ValueError:
        log.warning("AI gaf geen geldige JSON terug")
        return {}, cost
    return {item["id"]: item for item in data.get("posts", [])}, cost


def merge_ai(rule: dict, ai: dict) -> dict:
    out = dict(rule)
    rel = max(0.0, min(1.0, float(ai.get("relevantie", 0))))
    if not ai.get("relevant"):
        rel = min(rel, 0.15)
    out["relevance"] = round(0.3 * rule["relevance"] + 0.7 * rel, 3)
    out["nl_score"] = 1.0 if ai.get("nederlands") else min(rule["nl_score"], 0.3)
    out["categories"] = list(dict.fromkeys(ai.get("categorieen", []) + rule["categories"]))[:3]
    products = []
    for p in ai.get("producten", []):
        name = p.get("naam", "").strip()
        if not name:
            continue
        products.append({"naam": name, "merk": p.get("merk", ""),
                         "winkel": p.get("winkel", ""), "nieuw": bool(p.get("nieuw"))})
        if p.get("merk") and p["merk"] not in out["brands"]:
            out["brands"].append(p["merk"])
    out["products"] = products[:5] or rule.get("products", [])
    if ai.get("zaak"):
        out["places"] = list(dict.fromkeys([ai["zaak"].strip()] + rule["places"]))[:5]
    if ai.get("stad") and not rule.get("city"):
        out["city"] = ai["stad"].strip()
    out["sentiment"] = ai.get("sentiment")
    out["summary"] = ai.get("samenvatting")
    return out
