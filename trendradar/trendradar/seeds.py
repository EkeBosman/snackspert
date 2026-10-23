"""De startlijst. Daarna vult de tool zichzelf aan (zie discovery.py).

Hashtags zijn bewust Nederlands-specifiek gekozen: '#burger' levert wereldwijd
miljoenen posts op, '#frikandelbroodje' bijna alleen Nederlandse.

Accounts in deze lijst zijn de officiële kanalen van supermarkten. Bestaat
een account niet (meer) of levert het niets op, dan zet de tool het na twee
lege ophaalrondes zelf op 'ongeldig'.
"""

INSTAGRAM_HASHTAGS = [
    "snackbar", "frietje", "patatje", "frikandel", "frikandelbroodje", "kroket",
    "kapsalon", "shoarma", "streetfoodnederland", "streetfoodnl", "foodtrucknederland",
    "nieuwbijah", "nieuwbijjumbo", "nieuwindesupermarkt", "supermarktvondst",
    "ahnieuw", "foodspotsamsterdam", "rotterdamfood", "eten010", "utrechtfood",
    "denhaagfood", "eindhovenfood", "groningenfood", "foodreviewnl",
    "nederlandsefood", "cafetaria", "friettent", "snackspert",
]

TIKTOK_HASHTAGS = [
    "snackbar", "frikandel", "kapsalon", "frietje", "nieuwbijah", "ahnieuw",
    "supermarktvondsten", "foodreviewnederland", "streetfoodnl", "eten010",
    "snackbarreview", "nederlandsefood",
]

# Zoeken is op TikTok de beste bron: hashtagpagina's tonen steeds dezelfde
# populaire video's, zoekresultaten bevatten ook nieuwe video's van kleine makers.
# De zinnen zijn gekozen op het moment vóór een hype: een zaak die iets nieuws
# post, een maker die een rare combinatie probeert.
TIKTOK_SEARCHES = [
    # nieuw bij snackbars
    "nieuw op de kaart snackbar", "nieuwe snack cafetaria", "eigen creatie snackbar",
    "snackbar special", "weekspecial snackbar", "nieuw bij de snackbar", "gekste snack",
    "snack die je moet proberen", "snackbar viral", "rij voor de deur snackbar",
    # bekende snacks in een nieuw jasje
    "broodje kaassoufflé", "nieuwe kapsalon", "frikandel nieuw", "kroket nieuw",
    "loaded fries nederland", "smashburger nieuw", "nieuwe döner", "bitterbal nieuw",
    # reviews en smaaktesten
    "snackbar review", "eerlijke review snack", "smaaktest snacks", "beste friet van nederland",
    "beste kapsalon", "frikandel review",
    # supermarkt
    "nieuw bij albert heijn", "nieuw bij jumbo", "nieuw bij lidl", "nieuwe smaak chips",
    "supermarkt review nieuw",
    # streetfood
    "streetfood nederland", "foodtruck nederland",
]

AMSTERDAM_SEARCHES = [
    "nieuw in amsterdam eten", "amsterdam nieuwe zaak", "amsterdam food spot",
    "amsterdam snackbar", "amsterdam broodje", "amsterdam rij voor de deur", "amsterdam streetfood",
]
AMSTERDAM_HASHTAGS = ["amsterdamfood", "amsterdameats", "foodspotsamsterdam", "amsterdamfoodie"]

INSTAGRAM_ACCOUNTS = [
    "albertheijn", "jumbosupermarkten", "lidlnederland", "aldinederland",
    "plussupermarkt", "febo_nl", "smullers",
]

TIKTOK_ACCOUNTS = [
    "albertheijn", "jumbosupermarkten", "lidlnederland",
]

FACEBOOK_PAGES = [
    "AlbertHeijn", "JumboSupermarkten", "LidlNederland", "ALDINederland", "PLUSsupermarkt",
]

NEWS_QUERIES = [
    "nieuw bij Albert Heijn", "nieuw bij Jumbo", "nieuw bij Lidl", "nieuw in de supermarkt",
    "nieuwe smaak chips", "nieuwe snack", "snackbar", "foodtruck", "streetfood festival",
    "cafetaria", "frikandel", "kroket nieuw",
    # regionale snackhypes: zo vond de pers het broodje Koet en de suikerbroodburger
    "snackbar viraal", "snack gaat viraal", "snackhit", "nieuwe snackhit", "broodje viraal",
    "rij voor de deur snackbar", "snackbar populair TikTok", "cafetaria viraal",
    # jouw eigen impact
    "Snackspert",
    # Amsterdam
    "Amsterdam nieuwe zaak eten", "Amsterdam snackbar", "Amsterdam broodjeszaak",
    "Amsterdam rij eten", "Amsterdam foodhal",
]


def all_sources() -> list[tuple[str, str, str]]:
    out = []
    out += [("instagram", "hashtag", v) for v in INSTAGRAM_HASHTAGS]
    out += [("instagram", "account", v) for v in INSTAGRAM_ACCOUNTS]
    out += [("tiktok", "hashtag", v) for v in TIKTOK_HASHTAGS]
    out += [("tiktok", "zoekterm", v) for v in TIKTOK_SEARCHES + AMSTERDAM_SEARCHES]
    out += [("instagram", "hashtag", v) for v in AMSTERDAM_HASHTAGS]
    out += [("tiktok", "account", v) for v in TIKTOK_ACCOUNTS]
    out += [("facebook", "account", v) for v in FACEBOOK_PAGES]
    return out


# Verhoog als de startlijst uitbreidt: bestaande installaties krijgen de nieuwe
# bronnen dan één keer erbij. Bronnen die al bestaan (ook gepauzeerde of
# afgewezen) blijven zoals ze zijn.
SEEDS_VERSION = 3


def upgrade(conn, now_iso: str) -> int:
    from . import db
    if db.get_state(conn, "seeds_version", 1) >= SEEDS_VERSION:
        return 0
    added = install(conn, now_iso)
    # TikTok-hashtags geven vooral bekende video's: minder budget dan zoekopdrachten.
    conn.execute("UPDATE sources SET priority = 0.5 WHERE platform = 'tiktok' AND kind = 'hashtag' "
                 "AND origin = 'start'")
    # Een ontdekte kopie van een startaccount ('albertheijn' naast 'AlbertHeijn') weghalen: die
    # pakte de posts af, waarna het startaccount ten onrechte 'ongeldig' werd.
    conn.execute("DELETE FROM sources WHERE origin = 'ontdekt' AND kind = 'account' AND EXISTS ("
                 "SELECT 1 FROM sources s2 WHERE s2.origin = 'start' AND s2.kind = 'account' "
                 "AND s2.platform = sources.platform AND lower(s2.value) = lower(sources.value) "
                 "AND s2.id != sources.id)")
    conn.execute("UPDATE sources SET status = 'actief', empty_streak = 0, reason = 'startlijst' "
                 "WHERE origin = 'start' AND status = 'ongeldig' AND reason LIKE 'twee rondes zonder resultaat%'")
    db.set_state(conn, "seeds_version", SEEDS_VERSION)
    return added


def install(conn, now_iso: str) -> int:
    added = 0
    for platform, kind, value in all_sources():
        cur = conn.execute(
            "INSERT OR IGNORE INTO sources(platform, kind, value, status, origin, reason, added_at) "
            "VALUES (?, ?, ?, 'actief', 'start', 'startlijst', ?)",
            (platform, kind, value, now_iso))
        added += cur.rowcount
    return added
