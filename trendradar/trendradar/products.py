"""Nieuwe producten: winkeldata, social en nieuws aan elkaar koppelen.

Drie bronnen kunnen een nieuw product melden:
1. de winkel zelf (het product duikt op in het assortiment, via checkjebon)
2. social (makers posten erover, vaak met "nieuw bij ...")
3. nieuws (vakbladen, persberichten)

Hoe meer bronnen hetzelfde product melden, hoe zekerder. Het interessantste
is het **vroege signaal**: makers posten over een nieuw product dat nog niet in
de winkeldata staat. Dan ben je er eerder bij dan de supermarkt-app.
"""
from __future__ import annotations

import re
from datetime import timedelta

from . import db, lexicon, trends
from .classify import norm

FILLER = {"de", "het", "een", "met", "van", "en", "st", "stuks", "g", "gr", "ml", "l", "kg",
          "nieuw", "nieuwe", "smaak", "x", "pak", "zak", "per"}
STORE_WORDS = {w for names in lexicon.SUPERMARKETS.values() for n in names
               for w in norm(n).split()} | {"ah", "albert", "heijn", "jumbo"}


def key(name: str) -> set[str]:
    words = set(norm(name).split()) - FILLER - STORE_WORDS
    return {w for w in words if len(w) > 1 and not w.isdigit()}


def same(a: str | set, b: str | set) -> bool:
    ka = a if isinstance(a, set) else key(a)
    kb = b if isinstance(b, set) else key(b)
    if not ka or not kb:
        return False
    overlap = len(ka & kb)
    # "Kapsalon Chips" hoort bij "Smaakmakers Kapsalon Chips 150g".
    return overlap >= 2 and overlap / min(len(ka), len(kb)) >= 0.75 or \
        overlap / len(ka | kb) >= 0.6


def tracked_stores(conn) -> set[str]:
    """Winkels waarvan we het assortiment kennen. Alleen daar zegt
    'niet in winkeldata' iets."""
    status = db.get_state(conn, "supermarkt_status", {}) or {}
    return {store for store, s in status.items() if s.get("ok")} | {"Albert Heijn", "Jumbo"}


def overview(conn, include_demo: bool = True, days: int = 30, only_relevant: bool = True) -> dict:
    demo = "" if include_demo else " AND demo = 0"
    relevant = " AND relevant = 1" if only_relevant else ""
    since = db.iso(db.now() - timedelta(days=days))
    week = db.iso(db.now() - timedelta(days=7))
    tracked = tracked_stores(conn)
    new_products = [dict(r) for r in conn.execute(
        f"SELECT * FROM products WHERE is_new = 1 AND first_seen >= ?{demo}{relevant} "
        "ORDER BY relevant DESC, first_seen DESC LIMIT 600", (since,))]
    if not only_relevant:  # alles wat je kunt eten of drinken, geen shampoo of batterijen
        new_products = [p for p in new_products if not any(w in p["name"].lower() for w in lexicon.NON_FOOD)][:300]
    all_keys = [(key(r["name"]), r["is_new"]) for r in conn.execute(
        f"SELECT name, is_new FROM products WHERE 1=1{demo}")]
    # Alleen nieuws dat de woordenlijsten relevant vinden: Google News geeft bij
    # 'snackbar' ook berichten over stormweer en dialectverhalen.
    news_rows = [dict(r) for r in conn.execute(
        "SELECT n.* FROM news n LEFT JOIN posts p ON p.id = n.id "
        f"WHERE n.published_at >= ? AND (p.relevance >= 0.35 OR n.demo = 1){demo.replace('demo', 'n.demo')} "
        "ORDER BY n.published_at DESC LIMIT 80", (week,))]
    posts = [db.row_to_dict(r) for r in conn.execute(
        "SELECT * FROM posts WHERE posted_at >= ? AND relevance >= 0.35 AND nl_score >= 0.4 "
        f"AND platform != 'nieuws' AND (categories LIKE '%Supermarkt%' OR products != '[]'){demo}",
        (week,))]

    stores = set(lexicon.SUPERMARKETS)
    mentioned: dict[str, dict] = {}
    for p in posts:
        prods = [pr for pr in p["products"] if isinstance(pr, dict) and pr.get("naam")]
        if not prods:
            # Zonder productnaam: merk + winkel als benadering.
            shop = [b for b in p["brands"] if b in stores]
            other = [b for b in p["brands"] if b not in stores]
            if shop and other:
                prods = [{"naam": f"{other[0]} ({shop[0]})", "winkel": shop[0], "nieuw": False}]
        for pr in prods:
            name = pr["naam"].strip()
            k = key(name)
            # Varianten van dezelfde naam samenvoegen.
            home = next((m for m in mentioned.values() if same(k, m["_key"])), None)
            if home is None:
                home = mentioned[name] = {"name": name, "_key": k, "posts": 0, "engagement": 0,
                                          "makers": set(), "platforms": set(), "stores": set(),
                                          "said_new": 0, "first": p["posted_at"], "example": None}
            home["posts"] += 1
            eng = trends.engagement(p)
            home["engagement"] += eng
            home["makers"].add((p["platform"], p["author"] or p["id"]))
            home["platforms"].add(p["platform"])
            if pr.get("winkel"):
                home["stores"].add(pr["winkel"])
            home["stores"].update(b for b in p["brands"] if b in stores)
            home["said_new"] += bool(pr.get("nieuw")) or "nieuw" in (p["text"] or "").lower()
            home["first"] = min(home["first"], p["posted_at"])
            if not home["example"] or eng > home["example"][0]:
                home["example"] = (eng, p)

    out_mentioned = []
    for m in mentioned.values():
        in_store = any(same(m["_key"], k) for k, _ in all_keys)
        out_mentioned.append({
            "name": m["name"], "posts": m["posts"], "makers": len(m["makers"]),
            "engagement": round(m["engagement"]), "platforms": sorted(m["platforms"]),
            "stores": sorted(m["stores"]), "first": m["first"], "said_new": m["said_new"],
            "in_store": in_store,
            # Alleen bij winkels die we zelf controleren zegt 'niet in winkeldata' iets.
            "store_tracked": any(st in tracked for st in m["stores"]),
            "news": sum(1 for n in news_rows if same(m["_key"], n["title"])),
            "example": m["example"][1] if m["example"] else None,
        })
    out_mentioned.sort(key=lambda m: (m["makers"], m["posts"], m["engagement"]), reverse=True)

    # Vroeg signaal: (nog) niet in de winkeldata, wel gemeld als nieuw.
    early = [m for m in out_mentioned if not m["in_store"] and m["said_new"]]

    for prod in new_products:
        k = key(prod["name"])
        social = [m for m in out_mentioned if same(k, key(m["name"]))]
        prod["social_posts"] = sum(m["posts"] for m in social)
        prod["social_makers"] = sum(m["makers"] for m in social)
        prod["news"] = sum(1 for n in news_rows if same(k, n["title"]))
        prod["confirmed_by"] = ["winkel"] + (["social"] if social else []) + \
            (["nieuws"] if prod["news"] else [])
    return {"products": new_products, "mentioned": out_mentioned[:40], "early": early[:20],
            "news": news_rows}


# --- productnaam uit tekst zonder AI ------------------------------------------

_STORES_RE = "|".join(sorted({re.escape(n.strip("# ")) for names in lexicon.SUPERMARKETS.values()
                               for n in names if len(n.strip("# ")) > 2}, key=len, reverse=True)) + "|ah"
_BRANDS_RE = "|".join(sorted({re.escape(b).replace("'", "['’]?").replace("’", "['’]?")
                               for b in lexicon.BRANDS if len(b) > 2}, key=len, reverse=True))
_PATTERNS = [
    re.compile(rf"nieuw(?:e)? (?:bij|in de|van de) (?:de )?(?:{_STORES_RE})\s*[:!\-–]\s*(.{{4,60}}?)(?=[.!?#@\n]|$)", re.I),
    re.compile(rf"(?:gespot|gevonden) bij (?:de )?(?:{_STORES_RE})\s*[:!\-–]\s*(.{{4,60}}?)(?=[.!?#@\n]|$)", re.I),
    # 'De nieuwe Doritos Loaded Cheese bij de Jumbo': alleen met een winkel of merk erachter, anders
    # wordt 'de nieuwe Smashburger van de week' van een snackbar een supermarktproduct.
    re.compile(rf"(?:de )?nieuwe ([A-Z][\w'’&-]+(?: [\w'’&-]+){{0,4}}?) (?:van|bij) (?:de )?(?:{_STORES_RE}|{_BRANDS_RE})\b",
               re.U | re.I),
]


def guess_from_text(text: str, is_food) -> list[dict]:
    """Probeer een productnaam te vinden in zinnen als 'Nieuw bij AH: Paprika Chips Limoen'."""
    out = []
    for pattern in _PATTERNS:
        for m in pattern.finditer(text or ""):
            name = re.sub(r"[^\w\s'’&-]", "", m.group(1)).strip()
            words = name.split()
            if not 1 <= len(words) <= 6:
                continue
            if not any(is_food(w.lower()) for w in words):
                continue
            found = m.group(0).lower()
            store = next((s for s, hints in lexicon.SUPERMARKETS.items()
                          if any(h.strip("# ") in found for h in hints
                                 if len(h.strip("# ")) > 2)), "")
            if not store and re.search(r"\bah\b", found):
                store = "Albert Heijn"
            out.append({"naam": name, "merk": "", "winkel": store, "nieuw": True})
    unique = {p["naam"].lower(): p for p in out}
    return list(unique.values())[:3]


# --- testlijst: welke nieuwe producten zijn een supermarkttest waard? ----------

_WORD = lambda w, text: re.search(rf"(?<![\w]){re.escape(w)}", text) is not None  # noqa: E731


def test_ideas(conn, include_demo: bool = True, limit: int = 5, days: int = 14) -> list[dict]:
    """De top nieuwe producten om te testen.

    Supermarkttests zijn je sterkste volgersformat. Hoe herkenbaarder de snack, hoe
    gekker de draai eraan, hoe meer makers er al over posten en hoe beter die snack
    het bij jouw publiek doet, hoe hoger. Wat je al getest hebt, valt af.
    """
    from . import classify, ownposts

    ov = overview(conn, include_demo, days=days)
    tested = [k for k in (key(t["product"]) for t in ownposts._supermarket_tests(ownposts._rows(conn))) if k]
    lifts = ownposts.lifts(conn)
    brands = [b for b in lexicon.BRANDS if len(b) > 2]
    fresh = db.now() - timedelta(days=3)
    ideas: list[dict] = []
    for p in ov["products"]:
        k = key(p["name"])
        if not k or any(same(k, t) for t in tested):
            continue
        twin = next((i for i in ideas if same(k, i["_key"])), None)
        if twin:  # hetzelfde product in een andere winkel
            if p["store"] not in twin["stores"]:
                twin["stores"].append(p["store"])
            continue
        text = " " + norm(p["name"]) + " "
        reasons, score = [], 0.0
        snack = next((m for m in lexicon.MAINSTREAM_SNACKS if _WORD(norm(m), text)), None)
        if snack:
            score += 2
            reasons.append(f"Herkenbare snack: {snack}")
        groups = classify.item_groups(text, [])
        if len(groups) >= 2:
            score += 2
            reasons.append("Combinatie: " + " + ".join(groups[:2]))
        twist = next((w for w in lexicon.TWIST_WORDS if _WORD(w, text)), None)
        if twist:
            score += 1
            reasons.append(f"Twist: {twist}")
        brand = next((b for b in brands if _WORD(norm(b), text)), None)
        if brand:
            score += 0.5
            reasons.append(f"Bekend merk: {brand}")
        best = max(((g, lifts[g]) for g in groups if g in lifts), key=lambda x: x[1]["lift"], default=None)
        if best and best[1]["lift"] >= 1.1:
            score += min(1.5, (best[1]["lift"] - 1) * 3)
            reasons.append(f"Jouw publiek: {best[0]} {str(best[1]['lift']).replace('.', ',')}×")
        if p["social_makers"]:
            score += min(3.0, float(p["social_makers"]))
            reasons.append(f"{p['social_makers']} makers posten erover")
        if p["news"]:
            score += 1
            reasons.append("In het nieuws")
        if db.parse_iso(p["first_seen"]) >= fresh:
            score += 0.5
            reasons.append("Net in het schap")
        if score < 2:
            continue
        ideas.append({"id": p["id"], "name": p["name"], "stores": [p["store"]], "price": p["price"],
                      "url": p["url"], "first_seen": p["first_seen"], "score": round(score, 1),
                      "reasons": reasons, "demo": p.get("demo"), "_key": k})
    ideas.sort(key=lambda i: i["score"], reverse=True)
    for i in ideas:
        i.pop("_key")
    return ideas[:limit]
