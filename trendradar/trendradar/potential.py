"""Viral-potentie: welke tips hebben de meeste kans om viraal te gaan?

Een inschatting per tip uit Tips & routes, met de redenen erbij. De punten
volgen het patroon van eerdere snackhits (broodje Koet, broodje kaassoufflé,
suikerbroodburger): een kleine zaak met een eigen creatie of een onverwachte
combinatie van bekende snacks. Daarnaast telt wat er in je eigen posts werkt
(welke snacks, welke soort zaak, binnen of buiten Amsterdam) en of de tip nu
al besproken wordt.

Tips die je al gepost, gereviewd of afgewezen hebt, tellen niet mee: je
zoekt de volgende.
"""
from __future__ import annotations

import math
import re

from . import classify, db, imports, lexicon, ownposts, signals, spots, taste

# Punten per signaal. Bewust zichtbaar en eenvoudig, zodat je kunt zien waarom.
POINTS = {
    "creatie": 3.0,       # een eigen snack met een eigen naam
    "combinatie": 3.0,    # twee bekende snacks die normaal niet samengaan
    "twist": 2.0,         # bekende snack in een nieuwe vorm
    "getipt": 2.0,        # meerdere volgers tipten deze zaak
    "spektakel": 2.5,     # iets wat er spectaculair uitziet: werkt het best op video
    "huisgemaakt": 1.0,
    "claim": 1.0,         # 'beste burger van NL', 'prijswinnaar': daar wil iedereen een mening over
    "schaarste": 1.0,     # alleen op vrijdag: snel erbij zijn
    "prijs": 0.5,
    "herkenbaar": 1.0,    # mainstream snack
    "niche": -0.75,
    "algemeen": -1.0,     # 'geen gekke dingen'
    "radar": 1.5,         # nu al posts over
    "kleine_viral": 1.5,  # en een daarvan doet het ver boven normaal
}
SKIP = ("gereviewd", "afgevallen")


def _has(text: str, words) -> str | None:
    return next((w for w in words if w in text), None)


def _creation(raw: str) -> str | None:
    """'broodje lammert', 'Steenwijkerbal', 'luifel snack', 'Jacksalon': een eigen creatie?"""
    text = raw.lower()
    m = re.search(r"\bbroodje\s+([a-zà-ÿ][\w\-éëï]*)", text)
    if m and m.group(1) not in lexicon.NOT_A_NAME and m.group(1) not in lexicon.DUTCH_FOODS \
            and not classify.item_groups(f" {m.group(1)} ", []):
        return f"broodje {m.group(1)}"
    m = re.search(r"\bsnack\s+de\s+([a-zà-ÿ]{3,})", text)
    if m:
        return f"snack de {m.group(1)}"
    m = re.search(r"\b([a-zà-ÿ]{4,})\s+snack\b", text)
    if m and m.group(1) not in lexicon.NOT_A_NAME:
        return f"{m.group(1)} snack"
    for word in re.findall(r"[a-zà-ÿ\-]+", text):
        w = word.strip("-")
        if w in lexicon.COMMON_COMPOUNDS or w in lexicon.DUTCH_FOODS:
            continue
        for suffix in lexicon.CREATION_SUFFIXES:
            if w.endswith(suffix) and len(w) >= len(suffix) + 4:
                return w
    # Een eigennaam midden in de beschrijving: 'Briljantje (zelf ontwikkeld)', 'de Vlamburger'.
    if "zelf ontwikkeld" in text or "eigen creatie" in text:
        return "eigen creatie"
    return None


def _channel(name: str) -> str | None:
    low = name.lower()
    return next((ch for ch, hints in lexicon.CHANNEL_HINTS.items() if any(h in low for h in hints)), None)


def _num(x: float) -> str:
    return f"{x:.2f}".rstrip("0").rstrip(".").replace(".", ",")


def _candidates(conn) -> list[dict]:
    """Je tips, aangevuld met stops uit routes die (nog) niet als tip in je lijst staan."""
    out, seen = [], {}
    for r in conn.execute("SELECT * FROM spots"):
        d = db.row_to_dict(r)
        key = (taste.zaak_key(d["name"]), d["place"].lower())
        seen[key] = d
        out.append(d)
    for route in conn.execute("SELECT name, stops FROM routes"):
        for stop in db.row_to_dict(route)["stops"]:
            s = imports.parse_stop(stop)
            key = (taste.zaak_key(s["name"]), s["place"].lower())
            if key in seen:
                # Routes hebben soms een uitgebreidere beschrijving.
                if len(s["specialty"]) > len(seen[key]["specialty"] or ""):
                    seen[key]["specialty"] = s["specialty"]
                continue
            d = {"id": None, "name": s["name"], "place": s["place"], "specialty": s["specialty"], "region": "",
                 "lists": ["Uit routes"], "status": "te proberen", "note": ""}
            seen[key] = d
            out.append(d)
    return out


def score_tip(tip: dict, ctx: dict) -> dict:
    """Punten en redenen voor één tip."""
    raw = f"{tip['specialty'] or ''} {tip.get('note') or ''}"
    text = " " + raw.lower() + " "
    score, reasons, kinds = 0.0, [], set()

    def add(kind, why, pts=None):
        nonlocal score
        pts = POINTS[kind] if pts is None else pts
        score += pts
        kinds.add(kind)
        reasons.append({"kind": kind, "text": why, "points": round(pts, 1)})

    # Eerst de specialiteit; de naam van de zaak alleen als die zelf de snack is ('Steenwijkerbal').
    if creation := (_creation(tip["specialty"] or "") or (_creation(tip["name"]) if not tip["specialty"] else None)):
        add("creatie", f"Eigen creatie: {creation}")
    flags = classify.find_flags(text, [], 1.0)
    combo = next((f.split(":", 1)[1] for f in flags if f.startswith("combinatie:")), None)
    if combo:
        add("combinatie", f"Combinatie: {combo}")
    twist = next((f.split(":", 1)[1] for f in flags if f.startswith("twist:")), None)
    if twist:
        add("twist", f"Twist: {twist}")
    if w := _has(text, lexicon.TIPPED_WORDS):
        add("getipt", "Vaker getipt door volgers")
    if w := _has(text, lexicon.SPECTACLE_WORDS):
        add("spektakel", f"Opvallend: '{w}'")
    if _has(text, lexicon.HOMEMADE_WORDS):
        add("huisgemaakt", "Huisgemaakt")
    if w := _has(text, lexicon.CLAIM_WORDS):
        add("claim", f"Verhaal of claim: '{w}'")
    if w := _has(text, lexicon.SCARCITY_WORDS):
        add("schaarste", f"Schaars: '{w}'")
    if _has(text, lexicon.PRICE_WORDS):
        add("prijs", "Prijs als haakje")
    if _has(text, lexicon.GENERIC_WORDS):
        add("algemeen", "Weinig bijzonders genoemd")
    mainstream = _has(text, lexicon.MAINSTREAM_SNACKS)
    if mainstream:
        add("herkenbaar", f"Herkenbare snack: {mainstream}")
    elif w := _has(text, lexicon.NICHE_DISHES):
        add("niche", f"Niche: {w}")

    # Wat bij jouw publiek werkt (uit Mijn posts).
    groups = classify.item_groups(text, [])
    best = max(((g, ctx["snacks"][g]) for g in groups if g in ctx["snacks"]), key=lambda x: x[1]["lift"], default=None)
    if best and abs(best[1]["lift"] - 1) >= 0.05:
        add("publiek", f"Jouw publiek: {best[0]} {_num(best[1]['lift'])}×", max(-1.5, min(1.5, (best[1]["lift"] - 1) * 5)))
    loc = "Amsterdam" if (tip["place"] or "").lower() == "amsterdam" or "Amsterdam" in tip["lists"] else "Buiten Amsterdam"
    if loc in ctx["locations"]:
        lift = ctx["locations"][loc]["lift"]
        if abs(lift - 1) >= 0.05:
            add("locatie", f"{loc}: {_num(lift)}× bij jou", max(-1.0, min(1.0, (lift - 1) * 4)))
    ch = _channel(tip["name"])
    if ch and ch in ctx["channels"]:
        lift = ctx["channels"][ch]["lift"]
        if abs(lift - 1) >= 0.05:
            add("kanaal", f"{ch}: {_num(lift)}× bij jou", max(-1.0, min(1.0, (lift - 1) * 4)))

    # Nu al besproken in de radar?
    if tip["id"] is not None and (hit := ctx["radar"].get(tip["id"])):
        add("radar", f"🔥 {hit['posts']} {'post' if hit['posts'] == 1 else 'posts'} in 30 dagen")
        if hit.get("viral"):
            add("kleine_viral", f"Kleine viral: {_num(hit['viral'])}× views")

    # Past bij wat jij bewaart en een ♥ geeft.
    feats = taste.features(raw, flags=flags) | {f"zaak:{taste.zaak_key(tip['name'])}"}
    mine = sum(ctx["user"].get(f, 0) for f in feats)
    if abs(mine) >= 0.5:
        add("smaak", "Past bij jou" if mine > 0 else "Lijkt op wat je afwees", max(-2.0, min(2.0, mine)))

    strong = len(kinds & {"creatie", "combinatie", "twist", "getipt", "spektakel", "claim", "schaarste", "radar"})
    confidence = "hoog" if strong >= 2 else "middel" if strong == 1 or tip["specialty"] else "laag"
    return {"score": round(score, 2), "reasons": reasons, "confidence": confidence,
            # 0-100: een paar sterke signalen samen geven al snel een hoge kans.
            "potential": max(0, round(100 * (1 - math.exp(-max(score, 0) / 6))))}


def _context(conn, include_demo: bool) -> dict:
    hits = spots.radar_hits(conn, include_demo=include_demo)
    base = signals.baselines(conn, include_demo=include_demo)
    for hit in hits.values():
        best = 0.0
        for pid in hit["post_ids"]:
            row = conn.execute("SELECT * FROM posts WHERE id = ?", (pid,)).fetchone()
            if row:
                best = max(best, signals.of_post(row, base)["views_x"] or 0)
        hit["viral"] = best if best >= 3 else None
    prof = taste.profile(conn)
    return {
        "radar": hits,
        "snacks": ownposts.lifts(conn),
        "locations": ownposts.dimension_lifts(conn, "location"),
        "channels": ownposts.dimension_lifts(conn, "channel"),
        "recognition": ownposts.dimension_lifts(conn, "recognition"),
        "user": prof.user,
    }


def ranking(conn, limit: int = 10, include_demo: bool = True) -> dict:
    ctx = _context(conn, include_demo)
    handles = {taste.zaak_key(h): v for h, v in ownposts.posted_handles(conn).items()}
    captions = ownposts.caption_index(conn)
    route_rows = [db.row_to_dict(r) for r in conn.execute("SELECT id, name, stops FROM routes")]
    scored, skipped = [], {"gepost": 0, "status": 0}
    for tip in _candidates(conn):
        if tip["status"] in SKIP:
            skipped["status"] += 1
            continue
        key = spots._distinctive(tip["name"])
        if handles.get(taste.zaak_key(tip["name"])) or (key and ownposts.find_posted(key, captions)):
            skipped["gepost"] += 1
            continue
        s = score_tip(tip, ctx)
        tkey = taste.zaak_key(tip["name"])
        s.update({k: tip[k] for k in ("id", "name", "place", "specialty", "region", "lists", "status")})
        s["maps"] = spots.maps_search(tip["name"], tip["place"])
        s["routes"] = [r["name"] for r in route_rows
                       if any(taste.zaak_key(imports.parse_stop(x)["name"]) == tkey for x in r["stops"])][:3]
        scored.append(s)
    scored.sort(key=lambda s: (s["score"], s["specialty"] != ""), reverse=True)
    top = scored[:limit]
    # Routes met de meeste potentie: de som van de beste stops.
    by_key = {taste.zaak_key(s["name"]): s for s in scored}
    best_routes = []
    for r in route_rows:
        stops = [by_key.get(taste.zaak_key(imports.parse_stop(x)["name"])) for x in r["stops"]]
        total = sum(s["score"] for s in stops if s)
        best_routes.append({"id": r["id"], "name": r["name"], "score": round(total, 1),
                            "stops": [{"name": imports.parse_stop(x)["name"], "place": imports.parse_stop(x)["place"],
                                       "potential": s["potential"] if s else None} for x, s in zip(r["stops"], stops)],
                            "maps": spots.maps_url(r["stops"])})
    best_routes.sort(key=lambda r: r["score"], reverse=True)
    lifts = {"snacks": [{"snack": k, **v} for k, v in list(ctx["snacks"].items())[:3]],
             "locations": ctx["locations"], "recognition": ctx["recognition"]}
    return {"top": top, "total": len(scored), "skipped": skipped, "routes": best_routes[:3],
            "points": POINTS, "own_posts": conn.execute("SELECT COUNT(*) FROM own_posts").fetchone()[0],
            "lifts": lifts}
