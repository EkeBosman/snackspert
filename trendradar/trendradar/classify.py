"""Herkent of een post over Snackspert-terrein gaat, en waarover precies.

Twee lagen:
1. Regels (altijd, gratis): woordenlijsten uit lexicon.py.
2. Claude (optioneel, met ANTHROPIC_API_KEY): leest de posts die de regels
   twijfelachtig of relevant vinden en haalt er producten, zaken en steden uit.
"""
from __future__ import annotations

import functools
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


@functools.lru_cache(maxsize=8192)
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


def _food_forms(food: str) -> re.Pattern:
    """'frikandel' ook als frikandellen, frikandelletje; 'kroket' als kroketten, kroketjes."""
    last = re.escape(food[-1])
    return re.compile(rf"^{re.escape(food)}(?:{last}?en|s|je|jes|tje|tjes|{last}?etje|{last}?etjes|pje|pjes)?$")


_FOOD_FORMS: dict[str, re.Pattern] = {}


def _dutch_food(food: str, text: str, tokens: set[str], hashtags: list[str]) -> bool:
    # Hele woorden, geen stukjes: 'patat' mag niet matchen op het Spaanse 'patatas'.
    if " " in food:
        return f" {food} " in text or food.replace(" ", "") in hashtags
    if food in tokens or food in hashtags:
        return True
    forms = _FOOD_FORMS.setdefault(food, _food_forms(food))
    if any(forms.match(t) for t in tokens):
        return True
    return len(food) >= 6 and any(food in tag for tag in hashtags)


def _place_in_text(name: str, hay: str) -> bool:
    """Staat de plaatsnaam als los woord in de tekst? Twijfelnamen alleen na 'in', 'uit', 'bij'."""
    n = re.escape(name.lower())
    if name.lower() in lexicon.AMBIGUOUS_PLACES:
        preps = "|".join(lexicon.PLACE_PREPOSITIONS)
        return bool(re.search(rf"(?<![\w])(?:{preps})\s+{n}(?![\w])", hay))
    return bool(re.search(rf"(?<![\w]){n}(?![\w-])", hay))


def _place_in_tag(name: str, tag: str) -> bool:
    """#amsterdam, #amsterdamfood, #foodspotsamsterdam: ja. #ijshoorn, #goudakaas: nee."""
    n = name.lower().replace(" ", "").replace("-", "").replace("'", "")
    if len(n) < 3:
        return False
    if tag == n:
        return True
    if tag.startswith(n):
        rest = tag[len(n):]
        return any(rest.startswith(a) for a in lexicon.CITY_TAG_AFFIXES)
    if tag.endswith(n):
        rest = tag[:-len(n)]
        return any(rest.endswith(a) for a in lexicon.CITY_TAG_AFFIXES)
    return False


def _alias_in_tag(alias: str, tag: str) -> bool:
    """Netnummers en bijnamen: #eten010 en #rdamfood wel, #oliebollen2026 en #madam niet."""
    if tag == alias:
        return True
    if alias.isdigit():
        # Een netnummer achter letters (#eten010, #food020), niet in een jaartal (#2026).
        return bool(re.search(rf"[a-z]{alias}$", tag) or re.match(rf"^{alias}[a-z]", tag))
    if tag.startswith(alias):
        return any(tag[len(alias):].startswith(a) for a in lexicon.CITY_TAG_AFFIXES)
    if tag.endswith(alias):
        return any(tag[:-len(alias)].endswith(a) for a in lexicon.CITY_TAG_AFFIXES)
    return False


def find_city(text: str, hashtags: list[str], location: str | None) -> str | None:
    loc = " " + (location or "").lower() + " "
    hay = " " + text.lower() + " "
    big = sorted(lexicon.CITIES, key=len, reverse=True)
    towns = sorted(lexicon.NL_TOWNS, key=len, reverse=True)
    # 1. De locatie die bij de post hoort is het betrouwbaarst.
    if loc.strip():
        for name in big + towns:
            if re.search(r"(?<![\w])" + re.escape(name.lower()) + r"(?![\w])", loc):
                return "Den Bosch" if name == "'s-Hertogenbosch" else name
        if any(re.search(r"(?<![\w])" + re.escape(a) + r"(?![\w-])", loc) for a in lexicon.AMSTERDAM_AREAS):
            return "Amsterdam"
    # 2. Een stad of buurt in de tekst.
    for city in big:
        if _place_in_text(city, hay):
            return "Den Bosch" if city == "'s-Hertogenbosch" else city
    tags = set(hashtags)
    if (any(re.search(r"(?<![\w])" + re.escape(a) + r"(?![\w-])", hay) for a in lexicon.AMSTERDAM_AREAS)
            or tags & set(lexicon.AMSTERDAM_TAGS)):
        return "Amsterdam"
    for town in towns:
        if _place_in_text(town, hay):
            return town
    # 3. Hashtags: eerst volledige namen (#foodamsterdam), dan bijnamen en netnummers (#eten010).
    for tag in hashtags:
        for name in big + towns:
            if _place_in_tag(name, tag):
                return "Den Bosch" if name == "'s-Hertogenbosch" else name
    for tag in hashtags:
        for alias, city in lexicon.CITY_ALIASES.items():
            if _alias_in_tag(alias, tag):
                return city
    return None


_POSTCODE_RE = re.compile(r"\b\d{4}\s?[a-z]{2}\b")
_STREET_RE = re.compile(r"\d+.*|.*(straat|weg|laan|plein|gracht|kade|dijk|singel|steeg|hof)\s*\d+")
_PLACE_NOISE = re.compile(r"\b(centrum|centraal|station|binnenstad|city|stad|noord|zuid|oost|west|nl)\b")


def location_is_business(location: str) -> bool:
    """Is de locatie van een post een zaak, of alleen een stad, land of adres?

    'Snackbar De Poppe' is een zaak. 'Amsterdam, Netherlands', 'Nederland' en
    'Kalverstraat 12, 1012 NX Amsterdam' zijn dat niet.
    """
    low = (location or "").lower().strip()
    if not low or _POSTCODE_RE.search(low):
        return False
    parts = [p.strip() for p in re.split(r"[,|/·]", low) if p.strip() and p.strip() not in lexicon.COUNTRY_WORDS]
    if not parts:
        return False
    first = parts[0]
    if _STREET_RE.fullmatch(first):
        return False
    known = ({c.lower() for c in lexicon.CITIES} | {t.lower() for t in lexicon.NL_TOWNS}
             | set(lexicon.AMSTERDAM_AREAS) | lexicon.COUNTRY_WORDS)
    stripped = re.sub(r"\s+", " ", _PLACE_NOISE.sub(" ", first)).strip(" -")
    return first not in known and stripped not in known and bool(stripped)


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


# Achtervoegsels die een woord niet tot een nieuwe snack maken: #burgerlover, #snacktime.
_LIFESTYLE_SUFFIXES = ("lover", "lovers", "time", "addict", "addicts", "life", "love", "queen", "king", "fan", "fans",
                       "gang", "squad", "mood", "day", "dag", "tour", "review", "reviews", "porn", "holic", "holics",
                       "spot", "spots", "guide", "blog", "vlog", "tiktok", "insta", "lifestyle", "challenge")


def _base_form(word: str) -> str:
    """Meervoud en verkleinwoord terug naar het gewone woord: frikandellen -> frikandel."""
    for suffix in ("etjes", "etje", "tjes", "tje", "jes", "je", "en", "s"):
        if word.endswith(suffix) and len(word) - len(suffix) >= 4:
            base = word[:-len(suffix)]
            if len(base) >= 2 and base[-1] == base[-2]:
                base = base[:-1]  # frikandell -> frikandel, kroket+t -> kroket
            if base in _KNOWN_WORDS or base in _FOOD_WORDS:
                return base
    return word


_BRAND_WORDS = {norm(b).replace(" ", "") for b in lexicon.BRANDS} | {"burgerking", "mcdonalds", "kfc", "dominos",
                                                                      "newyorkpizza", "febo", "smullers"}


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
        if any(p in w for p in _PLACE_WORDS) or w in _BRAND_WORDS:
            continue
        if _base_form(w) != w or w.endswith(_LIFESTYLE_SUFFIXES):
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
    return list(_item_groups(text, tuple(hashtags)))


@functools.lru_cache(maxsize=8192)
def _item_groups(text: str, hashtags: tuple[str, ...]) -> tuple[str, ...]:
    # Dezelfde posts en captions komen bij elke pagina terug: één keer uitrekenen is genoeg.
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
    return tuple(found)


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


# Woorden die twee snacks tot één gerecht maken ('döner met kaassoufflé', 'burger tussen
# suikerbrood'), tegenover opsommingen ('een frikandel en een kipcorn').
_JOINERS = {"met", "in", "op", "tussen", "gevuld", "gevulde", "vol", "plus", "+", "&", "x", "×", "à", "ín"}
_ARTICLES = {"een", "1", "2", "3", "twee", "drie", "vier", "paar", "wat", "extra"}
_LIST_WORDS = {",", "en"}
_SENTENCE_END = {".", "!", "?", ";", ":"}
_COMBI_CUES = ("combi", "combinatie", "mix", "samen", "fusion", "kruising", "in één", "erop", "ertussen", "erin")
# Een woord als 'burgerbar', 'kebabhouse' of 'pizzeria' is een zaak, geen snack.
_BUSINESS_SUFFIXES = ("bar", "house", "huis", "huys", "corner", "paleis", "palace", "express", "point", "plaza",
                      "shop", "ria", "grill", "kitchen", "keuken", "boys", "brothers", "bros", "company", "kingdom",
                      "time", "lover", "lovers", "spot", "spots", "review", "reviews", "tour")
# Kaas en kip zijn een gewone vulling of topping; alleen bij zoet is het bijzonder.
_TOPPINGS = {"kaas", "kip"}
_SWEET = {"donut", "wafel", "chocolade", "softijs", "poffertjes", "pannenkoek", "oliebol", "suikerbrood"}
_COMBI_TOKEN_RE = re.compile(r"[a-zà-ÿ0-9][a-zà-ÿ0-9'’-]*|[+&×,.!?;:]")


def _token_groups(token: str) -> list[str]:
    """Snackgroepen in één woord. 'kroketburger' -> kroket en burger; 'kaassoufflé' alleen kaassoufflé."""
    if token.endswith(_BUSINESS_SUFFIXES) and len(token) > 6 and token not in ("ijsbar",):
        return []
    spans = []
    for group, keywords in lexicon.ITEM_GROUPS.items():
        for kw in keywords:
            k = kw.strip()
            if " " in k:
                continue
            start = token.find(k)
            if start >= 0 and (token == k or len(k) >= 4):
                spans.append((start, start + len(k), group))
                break
    if not spans and len(token) > 6 and token.endswith("ijs"):
        spans.append((len(token) - 3, len(token), "softijs"))  # frikandelijs
    elif len(token) > 6 and token.endswith("ijs") and not any(g == "softijs" for *_, g in spans):
        spans.append((len(token) - 3, len(token), "softijs"))
    # 'kaas' binnen 'kaassoufflé' en 'kip' binnen 'kipcorn' tellen niet apart.
    keep = [sp for sp in spans if not any(o is not sp and o[0] <= sp[0] and sp[1] <= o[1]
                                          and (o[1] - o[0]) > (sp[1] - sp[0]) for o in spans)]
    return list(dict.fromkeys(g for *_, g in sorted(keep)))


def _uncommon(a: str, b: str) -> bool:
    if a == b or frozenset((a, b)) in lexicon.COMMON_PAIRS:
        return False
    for x, y in ((a, b), (b, a)):
        if x in _TOPPINGS and y not in _SWEET:
            return False
    return True


def _pair_name(a: str, b: str) -> str:
    order = list(lexicon.ITEM_GROUPS)
    a, b = sorted((a, b), key=order.index)
    return f"{a} + {b}"


def find_combination(text: str, hashtags: list[str]) -> str | None:
    """Twee snacks in één gerecht, die normaal niet samengaan: 'kaassoufflé + döner'.

    Telt mee: één woord met twee snacks (kroketburger, #kapsalonchips), twee snacks
    vlak naast elkaar (croissant döner, pistache kroket) of verbonden door 'met',
    'in', 'op' of 'tussen'. Niet: een opsomming ('een frikandel en een kipcorn'),
    snacks in de naam van een zaak ('bij Burgerbar Smash') of in een @account.
    """
    t = " " + text.lower() + " "
    t = re.sub(r"@[\w.]+", " ", t)
    t = re.sub(r"https?://\S+", " ", t)
    t = re.sub(r"#[\w]+", " ", t)
    # De naam na 'bij' is meestal de zaak: 'kroket bij Burgerbar Smash'.
    t = re.sub(r"\bbij\s+[^\s.,!?;:]+(?:\s+[^\s.,!?;:]+){0,3}", " bij . ", t)
    tokens = _COMBI_TOKEN_RE.findall(t)
    found = []  # (afstand, paar)
    hits = [(i, _token_groups(tok)) for i, tok in enumerate(tokens)]
    hits = [(i, gs) for i, gs in hits if gs]
    # Eén woord met twee snacks, ook in hashtags.
    for tok_groups in [gs for _, gs in hits] + [_token_groups(h) for h in hashtags]:
        for x in range(len(tok_groups)):
            for y in range(x + 1, len(tok_groups)):
                if _uncommon(tok_groups[x], tok_groups[y]):
                    found.append((0, _pair_name(tok_groups[x], tok_groups[y])))
    for n, (i, gi) in enumerate(hits):
        for j, gj in hits[n + 1:]:
            d = j - i
            if d > 5:
                break
            between = tokens[i + 1:j]
            if any(b in _SENTENCE_END for b in between) or "of" in between:
                continue
            separate = (i > 0 and tokens[i - 1] in _ARTICLES) and tokens[j - 1] in _ARTICLES
            if separate:
                continue
            joined = any(b in _JOINERS for b in between)
            if not joined and d <= 2 and between and all(b not in lexicon.DUTCH_WORDS and b not in _LIST_WORDS
                                                          for b in between):
                joined = True  # 'pizza calzone kapsalon'
            if not joined and d == 1:
                joined = True  # 'croissant döner', 'pistache kroket'
            if not joined and all(b in _LIST_WORDS for b in between):
                # Een opsomming telt alleen binnen één gerecht: 'pita met döner, kaassoufflé en ...'
                before = tokens[max(0, i - 3):i]
                if any(b in _SENTENCE_END for b in before):
                    before = before[max(k for k, b in enumerate(before) if b in _SENTENCE_END) + 1:]
                sentence = " ".join(tokens[i:j + 8])
                joined = any(b in _JOINERS for b in before) or any(c in sentence for c in _COMBI_CUES)
            if not joined:
                continue
            for a in gi:
                for b in gj:
                    if _uncommon(a, b):
                        found.append((d, _pair_name(a, b)))
    return min(found)[1] if found else None


def find_flags(text: str, hashtags: list[str], relevance: float) -> list[str]:
    """Labels voor kandidaten: 'nieuw_op_kaart', 'combinatie:a + b' en 'twist:loaded kipcorn'."""
    flags = []
    if relevance >= 0.5 and any(p in text for p in lexicon.NEW_MENU_PHRASES):
        flags.append("nieuw_op_kaart")
    if relevance >= 0.5:
        twist = find_twist(text, hashtags)
        if twist:
            flags.append(f"twist:{twist}")
    combo = find_combination(text, hashtags)
    if combo:
        flags.append(f"combinatie:{combo}")
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
    if post.get("location") and location_is_business(post["location"]):
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
