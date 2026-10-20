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

TIKTOK_SEARCHES = [
    "nieuw bij albert heijn", "nieuw bij jumbo", "nieuw bij lidl", "snackbar review",
    "beste friet van nederland", "beste kapsalon", "streetfood nederland",
    "foodtruck nederland", "nieuwe smaak chips", "supermarkt review nieuw",
    "smaaktest snacks", "frikandel review",
]

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
]


def all_sources() -> list[tuple[str, str, str]]:
    out = []
    out += [("instagram", "hashtag", v) for v in INSTAGRAM_HASHTAGS]
    out += [("instagram", "account", v) for v in INSTAGRAM_ACCOUNTS]
    out += [("tiktok", "hashtag", v) for v in TIKTOK_HASHTAGS]
    out += [("tiktok", "zoekterm", v) for v in TIKTOK_SEARCHES]
    out += [("tiktok", "account", v) for v in TIKTOK_ACCOUNTS]
    out += [("facebook", "account", v) for v in FACEBOOK_PAGES]
    return out


def install(conn, now_iso: str) -> int:
    added = 0
    for platform, kind, value in all_sources():
        cur = conn.execute(
            "INSERT OR IGNORE INTO sources(platform, kind, value, status, origin, reason, added_at) "
            "VALUES (?, ?, ?, 'actief', 'start', 'startlijst', ?)",
            (platform, kind, value, now_iso))
        added += cur.rowcount
    return added
