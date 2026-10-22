"""Verzonnen voorbeelddata, zodat je de interface kunt beoordelen zonder sleutels.

Alle zaken, accounts en producten hieronder zijn fictief. Demodata is in de
database gemarkeerd (demo = 1) en verdwijnt met de knop 'Demodata wissen' of
automatisch zodra er een echte databron is ingesteld.

In de data zitten bewust een paar trends verstopt, zodat je kunt zien of de
trendradar ze vindt:
- 'pistache kroket' stijgt sinds 3 dagen (Rotterdam)
- 'birria taco' groeit gestaag de hele week (foodtrucks)
- 'Kapsalon Chips' (fictief nieuw product bij AH) piekt in de laatste 24 uur
- '#frikandelijs' ontploft in de laatste 6 uur
- 'dubai chocolade' was vorige week hot en zakt nu weg
- 'Bitterbal Chips' (fictief) duikt op social op, maar staat nog niet in de winkeldata
- @demo_kleinemaker (900 volgers) gaat viraal met #frikandelijs
"""
from __future__ import annotations

import hashlib
import math
import random
from datetime import timedelta

from . import db

AUTHORS = {
    "instagram": ["demo_foodspotter", "demo_snackliefde", "demo_eetavonturen", "demo_frietkenner",
                  "demo_hapjesjager", "demo_proefpanel_nl", "demo_lekkerweg", "demo_smulpaapje",
                  "demo_streetfoodgids", "demo_supermarktspotter"],
    "tiktok": ["demo_snacktok", "demo_proeftmeteen", "demo_frikandelman", "demo_supermarktreview",
               "demo_foodtour_nl", "demo_eetmeteva", "demo_snackcheck", "demo_tasttestnl"],
    "facebook": ["Demo Snackliefhebbers NL", "Demo Foodtruck Agenda", "Demo Eten in de Stad"],
}

PLACES = [
    ("Snackbar De Gouden Hoek", "Rotterdam", "demo_degoudenhoek_snackbar"),
    ("Frituur Bakkie Patat", "Utrecht", "demo_bakkiepatat_friet"),
    ("Taqueria El Fuego", "Amsterdam", "demo_elfuego_foodtruck"),
    ("Grillroom Anatolia", "Den Haag", "demo_anatolia_grill"),
    ("Burgerbar Smash & Co", "Eindhoven", "demo_smashco_burger"),
    ("Cafetaria 't Hoekje", "Groningen", "demo_thoekje_cafetaria"),
    ("Cafetaria De Reiger", "Gorinchem", "demo_dereiger_cafetaria"),
    ("Broodjesbar Stoep", "Amsterdam", "demo_stoep_broodjesbar"),
]

# (sleutel, teksten, hashtags, gewicht-functie van 'uren geleden', platformen)
STEADY = [
    ("friet", ["Beste friet van {stad}? Ik zeg {zaak}. Krokant en die mayo is top 🍟",
               "Patatje oorlog bij {zaak} in {stad}, echt een aanrader",
               "Vandaag friet speciaal gehaald bij {zaak}. Lekker zoals altijd"],
     ["frietje", "patatje", "snackbar"]),
    ("kroket", ["Broodje kroket bij {zaak}, gewoon klassiek en goed",
                "Kroket test: deze van {zaak} in {stad} wint het van de rest"],
     ["kroket", "snackbar"]),
    ("frikandel", ["Frikandel speciaal bij {zaak}, niks mis mee",
                   "Frikandelbroodje van de bakker vs die van {zaak}. Wie wint?"],
     ["frikandel", "frikandelbroodje"]),
    ("kapsalon", ["Kapsalon bij {zaak} in {stad}: veel te groot en heel lekker",
                  "Beste kapsalon van {stad} getest, {zaak} staat bovenaan"],
     ["kapsalon", "shoarma"]),
    ("smashburger", ["Smashburger bij {zaak}, dunne randjes zoals het hoort",
                     "Nieuwe smashburger spot in {stad}: {zaak}. Echt de moeite"],
     ["smashburger", "burger"]),
]

TRENDS = [
    ("pistache kroket",
     ["Pistache kroket bij {zaak} 🤯 klinkt raar maar is echt lekker",
      "Iedereen praat over de pistache kroket van {zaak} in Rotterdam. Getest!",
      "Rij van 20 minuten voor de pistache kroket bij {zaak}. Waard?"],
     ["pistachekroket", "kroket", "eten010"],
     lambda h: 0.2 + (6.0 * math.exp(-h / 30) if h < 72 else 0), 0),
    ("birria taco",
     ["Birria tacos bij foodtruck {zaak}, dippen in de consommé 🌮",
      "Birria taco gespot op de foodmarkt in {stad}, nieuwe favoriet",
      "Eerste keer birria tacos geprobeerd bij {zaak}. Wat een smaak"],
     ["birriatacos", "streetfoodnl", "foodtrucknederland"],
     lambda h: 0.3 + 2.5 * max(0, (168 - h) / 168), 2),
    ("kapsalon chips",
     ["Nieuw bij Albert Heijn: Smaakmakers Kapsalon Chips 😳 smaaktest!",
      "Kapsalon Chips nieuwe smaak gevonden bij AH. Lijkt echt op kapsalon??",
      "Smaaktest: de nieuwe Kapsalon Chips van Smaakmakers. Eerlijke review"],
     ["nieuwbijah", "ahnieuw", "supermarktvondst", "kapsalonchips"],
     lambda h: 5.0 * math.exp(-h / 10) if h < 30 else 0.0, None),
    ("frikandelijs",
     ["Softijs met frikandel?! {zaak} doet het gewoon 😂 #frikandelijs",
      "Frikandelijs geprobeerd bij {zaak}. Ik weet niet wat ik ervan vind",
      "Deze frikandelijs trend moet stoppen haha"],
     ["frikandelijs", "snackbar", "frikandel"],
     lambda h: 7.0 * math.exp(-h / 2.5) if h < 8 else 0.0, 5),
    ("dubai chocolade",
     ["Dubai chocolade broodje bij de bakker in {stad}, nog steeds hype?",
      "Dubai chocolade reep van de Lidl getest, nieuwe smaak",
      "Dubai chocolade donut bij {zaak}. Pistache overload"],
     ["dubaichocolade", "nieuwbijlidl", "pistache"],
     lambda h: 3.0 * math.exp(-((h - 220) / 60) ** 2), None),
    ("bitterbal chips",
     ["Gespot bij Jumbo: Bitterbal Chips?! Nieuwe smaak, eerlijke smaaktest",
      "Bitterbal Chips van Smaakmakers bij de Jumbo gevonden. Lijkt nergens op 😂",
      "Nieuwe chips met bitterbalsmaak, wie heeft ze al geproefd?"],
     ["bitterbalchips", "nieuwbijjumbo", "supermarktvondst"],
     lambda h: 2.2 * math.exp(-h / 8) if h < 20 else 0.0, None),
    # Een zaak post zelf een nieuwe combinatie: het moment vóór een hype.
    ("broodje reiger",
     ["Nieuw op de kaart: het broodje Reiger! Pita met döner, kaassoufflé en knoflooksaus 🔥",
      "Broodje Reiger gehaald bij {zaak} in Gorinchem. Döner met kaassoufflé in een pita, echt goed",
      "Wie heeft het broodje Reiger al geprobeerd? Kaassoufflé en döner, wat een combi"],
     ["broodjereiger", "gorinchem"],
     lambda h: 0.9 * math.exp(-h / 20) if h < 40 else 0.0, 6),
    # Amsterdam: nieuwe tosti in De Pijp.
    ("soufflé tosti",
     ["Nieuw bij ons in De Pijp: de soufflé tosti! Tosti met kaassoufflé en truffelmayo",
      "Soufflé tosti bij {zaak} in De Pijp geprobeerd, kaassoufflé in een tosti 🤯",
      "Rij voor de deur bij {zaak} voor die nieuwe tosti met kaassoufflé #amsterdamfood"],
     ["souffletosti", "amsterdamfood"],
     lambda h: 1.2 * math.exp(-h / 15) if h < 36 else 0.0, 7),
    # Twist op een bekende snack.
    ("loaded kipcorn",
     ["Loaded kipcorn bij {zaak}! Kipcorn vol met cheddar, jalapeños en crispy uitjes",
      "Eerste keer loaded kipcorn geprobeerd, dit is echt next level #loadedkipcorn",
      "Wie kent de loaded kipcorn al? Gehaald bij {zaak}, aanrader"],
     ["loadedkipcorn", "snackbar"],
     lambda h: 0.8 * math.exp(-h / 18) if h < 30 else 0.0, 1),
]

DEMO_PRODUCTS = [
    ("Albert Heijn", "Smaakmakers Kapsalon Chips", "Smaakmakers", "Chips", 2.19, 1, 1),
    ("Albert Heijn", "AH Frikandel Bites", "AH", "Diepvriessnacks", 3.49, 1, 3),
    ("Jumbo", "Jumbo Pistache Kroketten 4 st", "Jumbo", "Snacks", 3.99, 1, 2),
    ("Jumbo", "Knapperig Birria Kruidenmix", "Smaakmakers", "Kruiden", 1.89, 1, 5),
    ("Albert Heijn", "AH Dubai Style Reep", "AH", "Chocolade", 2.99, 0, 12),
    ("Jumbo", "Jumbo Mini Loempia's Kip", "Jumbo", "Diepvriessnacks", 2.79, 0, 20),
    ("Albert Heijn", "Smaakmakers Ribbelchips Patatje Oorlog", "Smaakmakers", "Chips", 2.19, 1, 6),
]

DEMO_NEWS = [
    ("Albert Heijn komt met chips met kapsalonsmaak (demo)", 1),
    ("Pistache kroket verovert Rotterdamse snackbars (demo)", 2),
    ("Foodtrucks met birria tacos populair op zomerfestivals (demo)", 4),
    ("Supermarkten breiden assortiment snacks uit in najaar (demo)", 6),
    ("Dubai chocolade-hype lijkt over zijn hoogtepunt (demo)", 8),
    ("Snackspert zet cafetaria in Gorinchem op de kaart (demo)", 3),
    ("Rij voor de deur bij nieuwe Amsterdamse broodjesbar (demo)", 1),
]


def _rng(seed: str) -> random.Random:
    return random.Random(int(hashlib.sha1(seed.encode()).hexdigest()[:12], 16))


def _make_post(rng: random.Random, key: str, texts, tags, hours_ago: float, boost: float,
               place_idx: int | None, now) -> dict:
    platform = rng.choices(["instagram", "tiktok", "facebook"], [0.5, 0.38, 0.12])[0]
    zaak, stad, handle = PLACES[place_idx if place_idx is not None else rng.randrange(len(PLACES))]
    text = rng.choice(texts).format(zaak=zaak, stad=stad)
    use_tags = rng.sample(tags, k=min(len(tags), rng.randint(1, len(tags))))
    if rng.random() < 0.35:
        text += f" @{handle}"
    text += " " + " ".join("#" + t for t in use_tags)
    if rng.random() < 0.4:
        text += " #food #reels"
    posted = now - timedelta(hours=hours_ago)
    base = rng.lognormvariate(4.2, 1.0) * (1 + boost)
    views = int(base * rng.uniform(15, 40)) if platform == "tiktok" else int(base * rng.uniform(0, 8))
    native = hashlib.sha1(f"{key}{hours_ago:.4f}{rng.random()}".encode()).hexdigest()[:14]
    # In demomodus doen we alsof de AI de productnaam al heeft herkend.
    products = []
    if key == "kapsalon chips":
        products = [{"naam": "Smaakmakers Kapsalon Chips", "merk": "Smaakmakers",
                     "winkel": "Albert Heijn", "nieuw": True}]
    elif key == "dubai chocolade" and "Lidl" in text:
        products = [{"naam": "Dubai chocolade reep", "merk": "", "winkel": "Lidl", "nieuw": True}]
    elif key == "bitterbal chips":
        products = [{"naam": "Smaakmakers Bitterbal Chips", "merk": "Smaakmakers",
                     "winkel": "Jumbo", "nieuw": True}]
    author = rng.choice(AUTHORS[platform]).lower()
    followers = int(rng.lognormvariate(8.5, 1.2))
    # Een onbekende maker met 900 volgers die viraal gaat met #frikandelijs.
    if key == "frikandelijs" and rng.random() < 0.3:
        platform, author, followers = "tiktok", "demo_kleinemaker", 900
        views = int(rng.uniform(60_000, 220_000))
        base = views * rng.uniform(0.06, 0.1)
    return {
        "products": products,
        "id": f"{platform}:demo{native}",
        "platform": platform,
        "author": author,
        "author_name": None,
        "author_followers": followers,
        "text": text,
        "url": None,
        "thumbnail": None,
        "location": f"{zaak}, {stad}" if platform == "instagram" and rng.random() < 0.5 else None,
        "posted_at": db.iso(posted),
        "likes": int(base),
        "comments": int(base * rng.uniform(0.02, 0.12)),
        "shares": int(base * rng.uniform(0, 0.2) * (4 if key == "frikandelijs" else 1))
        if platform != "instagram" else 0,
        "views": views,
        "snapshot_at": db.iso(min(now, posted + timedelta(hours=rng.uniform(1, 6)))),
    }


def generate(start_h: float, end_h: float, now, seed: str) -> list[dict]:
    """Posts met 'uren geleden' tussen end_h (recent) en start_h (oud)."""
    rng = _rng(seed)
    posts = []
    h = end_h
    while h < start_h:
        step = rng.uniform(0.05, 0.35)
        h += step
        # Vaste onderwerpen: ongeveer 4 per uur.
        if rng.random() < step * 4:
            key, texts, tags = rng.choice(STEADY)
            posts.append(_make_post(rng, key, texts, tags, h, 0, None, now))
        for key, texts, tags, weight, place in TRENDS:
            if rng.random() < step * weight(h) * 0.5:
                posts.append(_make_post(rng, key, texts, tags, h, min(3, weight(h) / 2), place, now))
        # Ruis: niet-relevant of niet-Nederlands.
        if rng.random() < step * 0.8:
            posts.append(_make_post(rng, "ruis", ["Great sunset today, love this city",
                                                   "Nieuwe sneakers binnen, wat vinden jullie?",
                                                   "Gym session done 💪"], ["instagood"], h, 0, None, now))
    return posts


def _later_snapshot(p: dict, now) -> dict:
    grow = 1.15 if "frikandelijs" in p["text"] or "Kapsalon Chips" in p["text"] else 1.03
    q = dict(p)
    q["likes"] = int(p["likes"] * grow) + 1
    q["views"] = int(p["views"] * grow)
    q["snapshot_at"] = db.iso(now)
    return q


def seed_history(conn, days: int = 14) -> int:
    from .collector import store_posts

    now = db.now()
    posts = generate(days * 24, 0, now, "historie")
    store_posts(conn, posts, None, demo=True)
    store_posts(conn, [_later_snapshot(p, now) for p in posts
                       if db.parse_iso(p["posted_at"]) > now - timedelta(hours=24)], None, demo=True)
    conn.execute("UPDATE posts SET demo = 1 WHERE id LIKE '%:demo%'")
    for i in range(days * 4, 0, -1):
        t = db.iso(now - timedelta(hours=6 * i))
        conn.execute("INSERT INTO runs(started_at, finished_at, status, trigger, results, new_posts, log) "
                     "VALUES (?, ?, 'klaar', 'demo', 0, 0, '[]')", (t, t))
    for store, name, brand, cat, price, is_new, days_ago in DEMO_PRODUCTS:
        t = db.iso(now - timedelta(days=days_ago))
        pid = "demo:" + hashlib.sha1(name.encode()).hexdigest()[:10]
        conn.execute("INSERT OR IGNORE INTO products(id, store, name, brand, category, price, url, "
                     "image, first_seen, last_seen, is_new, demo) VALUES (?,?,?,?,?,?,NULL,NULL,?,?,?,1)",
                     (pid, store, name, brand, cat, price, t, db.iso(now), is_new))
    for title, days_ago in DEMO_NEWS:
        nid = "nieuws:demo" + hashlib.sha1(title.encode()).hexdigest()[:10]
        t = db.iso(now - timedelta(days=days_ago, hours=3))
        conn.execute("INSERT OR IGNORE INTO news(id, title, url, outlet, published_at, query, "
                     "fetched_at, demo) VALUES (?, ?, NULL, 'Demo Nieuws', ?, 'demo', ?, 1)",
                     (nid, title, t, db.iso(now)))
    conn.execute("INSERT OR IGNORE INTO reviewed(slug, name, url, norm) VALUES "
                 "('demo-grillroom-anatolia', 'Grillroom Anatolia', NULL, 'anatolia')")
    db.set_state(conn, "demo_last_round", db.iso(now))
    db.set_state(conn, "demo_seeded", True)
    return len(posts)


def simulate_round(conn) -> int:
    from .collector import store_posts

    if not db.get_state(conn, "demo_seeded"):
        return seed_history(conn)
    now = db.now()
    last = db.get_state(conn, "demo_last_round") or db.iso(now - timedelta(hours=6))
    hours = max(0.2, (now - db.parse_iso(last)).total_seconds() / 3600)
    posts = generate(hours, 0, now, "ronde" + db.iso(now))
    store_posts(conn, posts, None, demo=True)
    conn.execute("UPDATE posts SET demo = 1 WHERE id LIKE '%:demo%'")
    db.set_state(conn, "demo_last_round", db.iso(now))
    return len(posts)


def clear(conn) -> None:
    conn.execute("DELETE FROM metric_snapshots WHERE post_id IN (SELECT id FROM posts WHERE demo = 1)")
    for table in ("posts", "products", "news", "sources"):
        conn.execute(f"DELETE FROM {table} WHERE demo = 1")
    conn.execute("DELETE FROM runs WHERE trigger IN ('demo')")
    conn.execute("DELETE FROM reviewed WHERE slug LIKE 'demo-%'")
    conn.execute("DELETE FROM state WHERE key IN ('demo_seeded', 'demo_last_round')")

