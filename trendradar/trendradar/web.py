"""De webinterface en de JSON-API waar die op draait."""
from __future__ import annotations

import csv
import io
import json
import re
import threading
from datetime import timedelta
from urllib.parse import urlsplit

from flask import Flask, Response, jsonify, request, send_from_directory
from werkzeug.exceptions import HTTPException

from . import (budget, collector, config, db, geo, imports, lexicon, onderhoud, ownposts, potential, products,
               nieuwezaken, routeplan, signals, snackspert, spots, taste, trefkans, trends)
from .sources import apify, meta_graph

app = Flask(__name__, static_folder="static", static_url_path="/static")
app.config["MAX_CONTENT_LENGTH"] = 25 * 1024 * 1024  # Excel-bestanden tot 25 MB

TOPIC_COLUMNS = {"hashtag": "hashtags", "categorie": "categories", "merk": "brands",
                 "zaak": "places", "zin": "phrases", "woord": "phrases"}
LOCAL_HOSTS = {"localhost", "127.0.0.1", "::1"}


class BadInput(ValueError):
    """Een ongeldige waarde in een verzoek: een nette melding (400) in plaats van een serverfout."""


@app.before_request
def _only_this_tool():
    """Alleen de tool zelf mag iets veranderen.

    Een website die je bezoekt kan je browser stiekem een verzoek naar localhost laten
    sturen, bijvoorbeeld 'start een betaalde ronde' of 'zet het budget op 1000'. Zulke
    verzoeken van een andere website, of via een vreemde domeinnaam, weigert de tool.
    """
    if urlsplit("//" + request.host).hostname not in LOCAL_HOSTS:
        port = request.environ.get("SERVER_PORT", "8050")
        return jsonify({"fout": f"onbekend adres; open de tool via http://localhost:{port}"}), 403
    if request.method in ("GET", "HEAD", "OPTIONS"):
        return None
    origin = request.headers.get("Origin")
    if origin is not None:
        foreign = urlsplit(origin).netloc != request.host
    else:
        foreign = request.headers.get("Sec-Fetch-Site") not in (None, "same-origin", "none")
    if foreign:
        return jsonify({"fout": "verzoek van een andere website geweigerd"}), 403
    return None


@app.errorhandler(BadInput)
def _bad_input(exc):
    return jsonify({"fout": str(exc)}), 400


_HTTP_FOUT = {400: "ongeldig verzoek", 403: "niet toegestaan", 404: "niet gevonden",
              405: "niet toegestaan", 413: "bestand te groot (maximaal 25 MB)"}


@app.errorhandler(HTTPException)
def _http_error(exc):
    if not request.path.startswith("/api/"):
        return exc
    return jsonify({"fout": _HTTP_FOUT.get(exc.code, exc.name)}), exc.code


@app.errorhandler(Exception)
def _server_error(exc):
    if isinstance(exc, HTTPException):
        return _http_error(exc)
    app.logger.exception("Fout bij %s %s", request.method, request.path)
    return jsonify({"fout": "er ging iets mis in de tool (details staan in het terminalvenster)"}), 500


def _num(name: str, default, cast=float, lo=None, hi=None):
    """Getal uit de adresregel, binnen grenzen. Onzin geeft een 400, geen serverfout."""
    raw = request.args.get(name)
    if raw in (None, ""):
        return default
    try:
        value = cast(raw)
    except (TypeError, ValueError):
        raise BadInput(f"ongeldige waarde voor {name}") from None
    if lo is not None:
        value = max(lo, value)
    return min(hi, value) if hi is not None else value


def _window(default: str) -> str:
    window = request.args.get("window", default)
    if window not in trends.WINDOWS:
        raise BadInput("onbekende periode")
    return window


def _body() -> dict:
    data = request.get_json(force=True, silent=True)
    if not isinstance(data, dict):
        raise BadInput("verwacht een JSON-object")
    return data


def _text(d: dict, key: str, limit: int) -> str:
    value = d.get(key)
    return "" if value is None else str(value).strip()[:limit]


def _args():
    a = request.args
    return {
        "platform": a.get("platform") or None,
        "min_rel": _num("min_rel", 0.35),
        "min_nl": _num("min_nl", 0.4),
        "include_demo": a.get("demo", "1") != "0",
        "city": a.get("city") or None,
    }


@app.get("/")
def index():
    return send_from_directory(app.static_folder, "index.html")


@app.get("/api/status")
def status():
    with db.session() as conn:
        settings = db.get_settings(conn)
        last = collector.last_run(conn)
        last_done = conn.execute(
            "SELECT started_at FROM runs WHERE status != 'bezig' AND trigger != 'supermarkt' "
            "ORDER BY started_at DESC, id DESC LIMIT 1").fetchone()
        next_at = None
        if last_done:
            next_at = db.iso(db.parse_iso(last_done["started_at"])
                             + timedelta(hours=settings["interval_uren"]))
        counts = conn.execute(
            "SELECT COUNT(*) AS posts, SUM(demo) AS demo FROM posts").fetchone()
        sources = {r["status"]: r["n"] for r in conn.execute(
            "SELECT status, COUNT(*) AS n FROM sources GROUP BY status")}
        return jsonify({
            "running": collector.is_running(),
            "demo": collector.demo_active(conn),
            "demo_data": bool(counts["demo"]),
            "keys": {
                "apify": apify.available(),
                "meta": meta_graph.available(),
                "anthropic": bool(config.secret("ANTHROPIC_API_KEY")),
            },
            "last_run": last,
            "next_run": next_at,
            "interval_uren": settings["interval_uren"],
            "posts": counts["posts"],
            "sources": sources,
            "supermarkt": db.get_state(conn, "supermarkt_status", {}),
            "reviewed": conn.execute("SELECT COUNT(*) AS n FROM reviewed").fetchone()["n"],
        })


@app.get("/api/trends")
def api_trends():
    a = _args()
    window = _window("24u")
    with db.session() as conn:
        result = trends.compute(conn, window, a["platform"], 60, a["min_rel"], a["min_nl"],
                                a["include_demo"], a["city"])
        result["volume"] = trends.volume(conn, window, a["platform"], a["min_rel"], a["min_nl"],
                                         a["include_demo"], a["city"])
        base = signals.baselines(conn, include_demo=a["include_demo"])
        result["rising_posts"] = [_slim(p, base) for p in trends.rising_posts(
            conn, max(12, trends.WINDOWS[window]["hours"]), 8, a["include_demo"])]
        ids = {b["id"] for b in result["breakouts"]}
        result["post_lookup"] = _posts_by_id(conn, ids, base)
    return jsonify(result)


def _posts_by_id(conn, ids, base) -> dict:
    if not ids:
        return {}
    marks = ",".join("?" * len(ids))
    return {r["id"]: _slim(db.row_to_dict(r), base) for r in conn.execute(
        f"SELECT * FROM posts WHERE id IN ({marks})", list(ids))}


def _slim(p: dict, base: dict | None = None) -> dict:
    keep = ("id", "platform", "author", "author_name", "author_followers", "text", "url",
            "thumbnail", "location", "posted_at", "likes", "comments", "shares", "views",
            "relevance", "nl_score", "categories", "brands", "products", "places", "city",
            "sentiment", "summary", "hashtags", "demo", "gain_per_hour", "flags")
    out = {k: p.get(k) for k in keep if k in p}
    if out.get("text") and len(out["text"]) > 600:
        out["text"] = out["text"][:600] + "…"
    if base is not None and p.get("platform") != "nieuws":
        sig = signals.of_post(p, base)
        out["signals"] = sig
        out["labels"] = signals.labels(sig)
    return out


def _topic_where(kind: str, name: str) -> tuple[str, list]:
    if kind == "stad":
        return "city = ?", [name]
    if kind == "product":
        return "products LIKE ?", ['%"naam": ' + json.dumps(name, ensure_ascii=False) + "%"]
    col = TOPIC_COLUMNS.get(kind)
    if not col:
        raise ValueError(kind)
    value = name[1:] if kind == "hashtag" and name.startswith("#") else name
    return f"{col} LIKE ?", ["%" + json.dumps(value, ensure_ascii=False) + "%"]


@app.get("/api/posts")
def api_posts():
    a = _args()
    q = request.args
    ids = [x.strip() for x in (q.get("ids") or "").split(",") if x.strip()][:200]
    if ids:
        # Precies deze posts (bijvoorbeeld waarmee een tip in de radar kwam), zonder periode of strengheid.
        where, args = [f"id IN ({','.join('?' * len(ids))})"], list(ids)
    else:
        where = ["relevance >= ?", "nl_score >= ?"]
        args = [a["min_rel"], a["min_nl"]]
        if a["platform"]:
            where.append("platform = ?")
            args.append(a["platform"])
        if a["city"]:
            where.append("city = ?")
            args.append(a["city"])
        window = q.get("window")
        if window in trends.WINDOWS:
            where.append("posted_at >= ?")
            args.append(db.iso(db.now() - timedelta(hours=trends.WINDOWS[window]["hours"])))
    if not a["include_demo"]:
        where.append("demo = 0")
    if q.get("category"):
        where.append("categories LIKE ?")
        args.append("%" + json.dumps(q["category"], ensure_ascii=False) + "%")
    if q.get("topic_type") and q.get("topic"):
        try:
            clause, extra = _topic_where(q["topic_type"], q["topic"])
        except ValueError:
            return jsonify({"fout": "onbekend onderwerptype"}), 400
        where.append(clause)
        args += extra
    if q.get("q"):
        where.append("(text LIKE ? OR author LIKE ?)")
        args += [f"%{q['q']}%", f"%{q['q']}%"]
    order = {
        "nieuw": "posted_at DESC",
        "interactie": "(likes + 2*comments + 3*shares + views/50.0) DESC",
        "relevantie": "relevance DESC, posted_at DESC",
        "snelheid": "views / MAX(1.0, (julianday(fetched_at) - julianday(posted_at)) * 24) DESC",
    }.get(q.get("sort", "nieuw"), "posted_at DESC")
    limit = _num("limit", 60, int, 1, 200)
    offset = _num("offset", 0, int, 0)
    with db.session() as conn:
        total = conn.execute(f"SELECT COUNT(*) AS n FROM posts WHERE {' AND '.join(where)}",
                             args).fetchone()["n"]
        rows = conn.execute(
            f"SELECT * FROM posts WHERE {' AND '.join(where)} ORDER BY {order} LIMIT ? OFFSET ?",
            args + [limit, offset]).fetchall()
        base = signals.baselines(conn, include_demo=a["include_demo"])
    return jsonify({"total": total, "posts": [_slim(db.row_to_dict(r), base) for r in rows]})


@app.get("/api/topic")
def api_topic():
    a = _args()
    kind, name = request.args.get("type"), request.args.get("name", "")
    window = request.args.get("window", "7d")
    w = trends.WINDOWS.get(window, trends.WINDOWS["7d"])
    try:
        clause, extra = _topic_where(kind, name)
    except ValueError:
        return jsonify({"fout": "onbekend onderwerptype"}), 400
    span = timedelta(hours=w["hours"] * (w["baseline"] + 1))
    start = db.now() - span
    n = int(w["hours"] * (w["baseline"] + 1) / w["bucket_h"])
    bucket = timedelta(hours=w["bucket_h"])
    where = f"{clause} AND posted_at >= ? AND relevance >= ? AND nl_score >= ?"
    args = extra + [db.iso(start), a["min_rel"], a["min_nl"]]
    if not a["include_demo"]:
        where += " AND demo = 0"
    with db.session() as conn:
        rows = [db.row_to_dict(r) for r in conn.execute(
            f"SELECT * FROM posts WHERE {where} ORDER BY posted_at DESC", args)]
        base = signals.baselines(conn, include_demo=a["include_demo"])
    sigs = []
    for p in rows:
        sig = signals.of_post(p, base)
        sig["_views"] = p["views"] or 0
        sigs.append(sig)
    series = [0] * n
    platforms: dict[str, int] = {}
    co: dict[str, int] = {}
    for p in rows:
        idx = min(n - 1, max(0, int((db.parse_iso(p["posted_at"]) - start) / bucket)))
        series[idx] += 1
        platforms[p["platform"]] = platforms.get(p["platform"], 0) + 1
        for t in p["hashtags"]:
            if "#" + t != name and t not in lexicon.GENERIC_HASHTAGS:
                co["#" + t] = co.get("#" + t, 0) + 1
    top = sorted(rows, key=lambda p: trends.engagement(p), reverse=True)[:12]
    makers = {(p["platform"], p["author"] or p["id"]) for p in rows}
    return jsonify({
        "type": kind, "name": name, "window": window,
        "labels": [db.iso(start + bucket * i) for i in range(n)],
        "series": series,
        "current_from": n - int(w["hours"] / w["bucket_h"]),
        "platforms": platforms,
        "related": sorted(co.items(), key=lambda kv: kv[1], reverse=True)[:12],
        "posts": [_slim(p, base) for p in top],
        "signals": signals.topic_summary(sigs),
        "makers": len(makers),
        "total": len(rows),
    })


@app.get("/api/supermarkt")
def api_supermarkt():
    a = _args()
    days = _num("days", 30, int, 1, 365)
    with db.session() as conn:
        result = products.overview(conn, a["include_demo"], days,
                                   only_relevant=request.args.get("alles") != "1")
        result["status"] = db.get_state(conn, "supermarkt_status", {})
        result["test_ideas"] = products.test_ideas(conn, a["include_demo"], limit=10)
        base = signals.baselines(conn, include_demo=a["include_demo"])
    for m in result["mentioned"]:
        if m["example"]:
            m["example"] = _slim(m["example"], base)
    return jsonify(result)


_shop_tests: dict[str, dict] = {}


@app.post("/api/supermarkt/test")
def api_supermarket_test():
    """Test de scraper(s) van één winkel op de achtergrond; de pagina vraagt de voortgang op.

    Een scraper voor het hele assortiment levert pas aan het eind (AH ± 20 minuten): die laat
    de test afmaken, en de uitkomst telt meteen als nulmeting. Het zoeken op woorden stopt
    zodra er 5 producten binnen zijn.
    """
    from .sources import supermarket

    code = _text(_body(), "winkel", 30).lower()
    if not code:
        return jsonify({"fout": "kies een winkel"}), 400
    if not apify.available():
        return jsonify({"fout": "zet eerst APIFY_TOKEN in .env"}), 400
    if _shop_tests.get(code, {}).get("running"):
        return jsonify({"started": False})
    store = supermarket.STORE_NAMES.get(code, code.title())
    with db.session() as conn:
        settings = db.get_settings(conn)
    test = _shop_tests[code] = {"running": True, "winkel": store, "now": None, "tried": [], "result": None}

    def work():
        try:
            for src in supermarket.sources(code, settings):
                body = (src.get("input") or {}) if src["volledig"] else \
                    {"keyterms": ["kroket"], "supermarkets": [code], "maxResults": 5}
                test["now"] = {"scraper": src["actor"], "volledig": src["volledig"], "seconden": 0, "gevonden": 0}
                if src["volledig"]:
                    if _test_full(test, store, code, src, settings):
                        break
                    continue

                def progress(sec, found, status, _now=test["now"]):
                    _now.update(seconden=sec, gevonden=found, status=status)
                try:
                    items, cost, status = apify.sample_actor(src["actor"], body, n=5, wait_s=150, progress=progress)
                except Exception as exc:  # noqa: BLE001
                    test["tried"].append({"scraper": src["actor"], "fout": config.redact(str(exc))[:300]})
                    continue
                with db.session() as conn:
                    budget.record(conn, "apify", cost, None, f"supermarkttest {store}")
                parsed = [p for p in (supermarket.parse_apify(i, store, code) for i in items) if p]
                if not parsed:
                    why = (f"{len(items)} resultaten zonder productnaam" if items
                           else f"na {test['now'].get('seconden', 0)} seconden nog geen producten (status {status})")
                    test["tried"].append({"scraper": src["actor"], "fout": why,
                                          "velden": sorted({k for i in items for k in i})[:30]})
                    continue
                test["result"] = {"scraper": src["actor"], "volledig": src["volledig"], "gelezen": len(parsed),
                                  "kosten_usd": round(cost, 3), "velden": sorted({k for i in items for k in i})[:30],
                                  "voorbeelden": [{"naam": p["name"], "prijs": p["price"], "url": p["url"]}
                                                  for p in parsed[:5]]}
                break
        finally:
            test["now"] = None
            test["running"] = False
    threading.Thread(target=work, daemon=True).start()
    return jsonify({"started": True})


def _test_full(test: dict, store: str, code: str, src: dict, settings: dict) -> bool:
    """Draai een scraper voor het hele assortiment helemaal; gelukt = meteen de nulmeting."""
    from .sources import supermarket

    def progress(sec, status, line, _now=test["now"]):
        _now.update(seconden=sec, status=status, log=line)
    cap = float(settings.get("supermarkt_max_usd_volledig", 2.0) or 2.0)
    try:
        items, cost = apify.run_actor("actor", src["actor"], [], 0, cap, timeout_s=collector.FULL_TIMEOUT_S,
                                      extra_input=src.get("input") or {}, max_items=80000, progress=progress)
    except Exception as exc:  # noqa: BLE001
        test["tried"].append({"scraper": src["actor"], "fout": config.redact(str(exc))[:300]})
        return False
    products = [p for p in (supermarket.parse_apify(i, store, code) for i in items) if p]
    now = db.iso(db.now())
    with db.session() as conn:
        budget.record(conn, "apify", cost, None, f"supermarkttest {store}: hele assortiment")
        if len(products) < supermarket.MIN_FULL:
            test["tried"].append({"scraper": src["actor"], "fout": f"klaar, maar maar {len(products)} producten",
                                  "velden": sorted({k for i in items for k in i})[:30]})
            return False
        st, _ = collector._store_products(conn, store, products, now, "volledig")
        st.update(scraper=src["actor"], volledig=True)
        status = db.get_state(conn, "supermarkt_status", {}) or {}
        status[store] = st
        db.set_state(conn, "supermarkt_status", status)
    test["result"] = {"scraper": src["actor"], "volledig": True, "gelezen": len(products), "kosten_usd": round(cost, 3),
                      "nulmeting": True, "velden": sorted({k for i in items for k in i})[:30],
                      "voorbeelden": [{"naam": p["name"], "prijs": p["price"], "url": p["url"]} for p in products[:5]]}
    return True


@app.get("/api/supermarkt/test")
def api_supermarket_test_status():
    code = (request.args.get("winkel") or "").lower()
    return jsonify(_shop_tests.get(code) or {"running": False, "result": None, "tried": []})


@app.get("/api/supermarkt/zoek")
def api_supermarket_search():
    """Staat dit product in de data? Op naam, of met de link van de winkel."""
    q = (request.args.get("q") or "").strip()
    if len(q) < 3:
        return jsonify({"fout": "typ minstens 3 tekens of plak een link"}), 400
    m = re.search(r"/(wi\d+)/", q)
    words = [w for w in re.sub(r"[^a-z0-9 ]", " ", q.lower().split("/")[-1].replace("-", " ")).split() if len(w) > 2]
    with db.session() as conn:
        if m:
            rows = conn.execute("SELECT * FROM products WHERE url LIKE ? LIMIT 20", (f"%{m.group(1)}%",)).fetchall()
        else:
            rows = []
        if not rows and words:
            where = " AND ".join("lower(name) LIKE ?" for _ in words[:5])
            rows = conn.execute(f"SELECT * FROM products WHERE {where} ORDER BY first_seen DESC LIMIT 20",
                                [f"%{w}%" for w in words[:5]]).fetchall()
        status = db.get_state(conn, "supermarkt_status", {}) or {}
    return jsonify({"products": [{"name": r["name"], "store": r["store"], "first_seen": r["first_seen"],
                                  "last_seen": r["last_seen"], "is_new": bool(r["is_new"]), "url": r["url"],
                                  "price": r["price"]} for r in rows],
                    "full_stores": sorted(s for s, v in status.items() if v.get("volledig"))})


@app.get("/api/zaken")
def api_zaken():
    a = _args()
    window = _window("7d")
    with db.session() as conn:
        result = trends.compute(conn, window, a["platform"], 1000, a["min_rel"], a["min_nl"],
                                a["include_demo"], a["city"])
        reviewed = [dict(r) for r in conn.execute("SELECT * FROM reviewed")]
    places = []
    for t in result["topics"]:
        if t["type"] != "zaak":
            continue
        name = t["name"]
        city = None
        if ", " in name:
            name, city = name.rsplit(", ", 1)
        hit = snackspert.match(name, reviewed)
        places.append({**t, "display": name.lstrip("@"), "city": city,
                       "reviewed": {"name": hit["name"], "url": hit["url"]} if hit else None})
    places = _merge_places(places)[:60]
    with db.session() as conn:
        _mark_posted_and_tips(conn, places)
    return jsonify({"window": window, "places": places, "cities": result["cities"],
                    "reviewed_count": len(reviewed)})


def _mark_posted_and_tips(conn, places: list[dict]) -> None:
    """Heb je deze zaak al eens gepost (Mijn posts), of staat hij in je tips?"""
    handles = {taste.zaak_key(h): v for h, v in ownposts.posted_handles(conn).items()}
    captions = ownposts.caption_index(conn)
    tips = {taste.zaak_key(r["name"]): {"id": r["id"], "status": r["status"]}
            for r in conn.execute("SELECT id, name, status FROM spots")}
    for p in places:
        keys = [taste.zaak_key(n) for n in [p["display"], *p.get("aliases", [])]]
        p["posted"] = next((handles[k] for k in keys if k in handles), None) or next(
            (hit for k in keys if len(k) >= 10 for hit in [ownposts.find_posted(k, captions)] if hit), None)
        p["tip"] = next((tips[k] for k in keys if k in tips), None)


def _merge_places(places: list[dict]) -> list[dict]:
    """'@degoudenhoek_snackbar' en 'Snackbar De Gouden Hoek' zijn dezelfde zaak."""
    import difflib

    places.sort(key=lambda p: (p["posts"], p["engagement"]), reverse=True)
    merged: list[dict] = []
    for p in places:
        key = snackspert.core_name(p["display"]).replace(" ", "")
        home = None
        for m in merged:
            short, long_ = sorted((key, m["_key"]), key=len)
            if (len(short) >= 6 and short in long_) or \
                    difflib.SequenceMatcher(None, key, m["_key"]).ratio() >= 0.86:
                home = m
                break
        if home is None:
            merged.append({**p, "_key": key, "aliases": []})
            continue
        # Posts kunnen onder beide namen geteld zijn; neem dus het maximum.
        home["city"] = home["city"] or p["city"]
        home["reviewed"] = home["reviewed"] or p["reviewed"]
        home["platforms"] = sorted(set(home["platforms"]) | set(p["platforms"]))
        # Toon liever de echte naam ("Snackbar De Gouden Hoek") dan de handle.
        if not home["display"][:1].isupper() and p["display"][:1].isupper():
            home["display"], alias = p["display"], home["display"]
        else:
            alias = p["display"]
        home["aliases"].append(alias)
    for m in merged:
        m.pop("_key", None)
    return merged


# --- bronnen ---------------------------------------------------------------

@app.get("/api/sources")
def api_sources():
    with db.session() as conn:
        rows = [dict(r) for r in conn.execute(
            "SELECT * FROM sources ORDER BY CASE status WHEN 'kandidaat' THEN 0 WHEN 'actief' THEN 1 "
            "WHEN 'gepauzeerd' THEN 2 ELSE 3 END, platform, kind, value")]
        used, free = meta_graph.hashtag_slots(conn)
        rate = db.get_settings(conn)["eur_per_usd"] or 0.92
    for r in rows:
        r["eur_per_useful"] = (round(r["cost_usd"] * rate / r["useful_total"], 3)
                               if r.get("useful_total") and r.get("cost_usd") else None)
        r["eur_total"] = round((r.get("cost_usd") or 0) * rate, 2)
    return jsonify({"sources": rows, "graph_slots_free": free, "graph_used": sorted(used)})


@app.post("/api/sources")
def add_source():
    data = _body()
    platform = data.get("platform")
    kind = data.get("kind")
    value = _text(data, "value", 200).lstrip("#@").strip()
    if platform not in ("instagram", "tiktok", "facebook") or kind not in ("hashtag", "account", "zoekterm") \
            or not value:
        return jsonify({"fout": "kies platform, soort en een waarde"}), 400
    if kind != "account" or platform != "facebook":
        value = value.lower() if kind != "zoekterm" else value
    with db.session() as conn:
        conn.execute(
            "INSERT INTO sources(platform, kind, value, status, origin, reason, added_at) "
            "VALUES (?, ?, ?, 'actief', 'handmatig', 'zelf toegevoegd', ?) "
            "ON CONFLICT(platform, kind, value) DO UPDATE SET status = 'actief', origin = 'handmatig'",
            (platform, kind, value, db.iso(db.now())))
    return jsonify({"ok": True})


@app.patch("/api/sources/<int:sid>")
def update_source(sid: int):
    data = _body()
    sets, args = [], []
    if data.get("status") in ("actief", "gepauzeerd", "afgewezen", "kandidaat"):
        sets.append("status = ?")
        args.append(data["status"])
        if data["status"] == "actief":
            # Opnieuw beginnen: met de oude, lage opbrengst zou hij na één ronde weer op pauze gaan.
            sets.append("empty_streak = 0, yield_score = NULL, fetch_count = 0, next_due = NULL")
    if "priority" in data:
        try:
            priority = float(data["priority"])
        except (TypeError, ValueError):
            raise BadInput("ongeldige prioriteit") from None
        sets.append("priority = ?")
        args.append(max(0.1, min(3.0, priority)))
    if not sets:
        return jsonify({"fout": "niets te wijzigen"}), 400
    with db.session() as conn:
        conn.execute(f"UPDATE sources SET {', '.join(sets)} WHERE id = ?", args + [sid])
    return jsonify({"ok": True})


@app.delete("/api/sources/<int:sid>")
def delete_source(sid: int):
    with db.session() as conn:
        conn.execute("DELETE FROM sources WHERE id = ?", (sid,))
    return jsonify({"ok": True})


# --- instellingen, budget, rondes -------------------------------------------

@app.get("/api/settings")
def get_settings():
    with db.session() as conn:
        return jsonify(db.get_settings(conn))


@app.post("/api/settings")
def save_settings():
    data = _body()
    clean = {}
    for key, default in config.DEFAULTS.items():
        if key not in data:
            continue
        value = data[key]
        try:
            if isinstance(default, bool):
                value = bool(value)
            elif isinstance(default, (int, float)):
                value = type(default)(value)
                if value < 0:
                    raise ValueError
            elif isinstance(default, dict):
                value = {k: float(v) for k, v in value.items()}
                if any(x < 0 for x in value.values()):
                    raise ValueError
            elif isinstance(default, list):
                value = [str(v).strip() for v in value if str(v).strip()]
            else:
                value = str(value)
        except (TypeError, ValueError, AttributeError):
            return jsonify({"fout": f"ongeldige waarde voor {key}"}), 400
        clean[key] = value
    if "interval_uren" in clean and clean["interval_uren"] < 1:
        return jsonify({"fout": "interval minimaal 1 uur"}), 400
    if "min_per_bron" in clean and clean["min_per_bron"] < 1:
        return jsonify({"fout": "minimaal 1 post per bron"}), 400
    if "max_per_bron" in clean and clean["max_per_bron"] < clean.get("min_per_bron", 1):
        return jsonify({"fout": "het maximum per bron moet minstens het minimum zijn"}), 400
    with db.session() as conn:
        current = db.get_settings(conn)
        # Een deel van de verdeling opslaan laat de andere platforms staan.
        clean = {k: {**current[k], **v} if isinstance(v, dict) else v for k, v in clean.items()}
        db.set_settings(conn, clean)
        return jsonify(db.get_settings(conn))


@app.get("/api/budget")
def api_budget():
    with db.session() as conn:
        settings = db.get_settings(conn)
        return jsonify(budget.overview(conn, settings))


@app.get("/api/onderhoud")
def api_onderhoud():
    with db.session() as conn:
        settings = db.get_settings(conn)
        out = onderhoud.status(conn, settings)
        out["cleanup"] = db.get_state(conn, "opruimen_laatst")
    return jsonify(out)


@app.post("/api/backup")
def api_backup():
    with db.session() as conn:
        settings = db.get_settings(conn)
    try:
        return jsonify(onderhoud.make_backup(settings))
    except OSError as exc:
        return jsonify({"fout": f"back-up mislukt: {exc}"}), 500


@app.get("/api/runs")
def api_runs():
    with db.session() as conn:
        rows = [db.row_to_dict(r) for r in conn.execute(
            "SELECT * FROM runs WHERE trigger != 'demo' ORDER BY id DESC LIMIT 30")]
    return jsonify(rows)


@app.post("/api/run")
def start_run():
    if collector.is_running():
        return jsonify({"ok": False, "melding": "er loopt al een ronde"}), 409
    force = bool((request.get_json(silent=True) or {}).get("supermarkt"))
    threading.Thread(target=collector.run_once, args=("handmatig", force), daemon=True).start()
    return jsonify({"ok": True})


@app.post("/api/demo/clear")
def clear_demo():
    from . import demo
    with db.session() as conn:
        demo.clear(conn)
    return jsonify({"ok": True})


# --- export ----------------------------------------------------------------

_FORMULA_START = ("=", "+", "-", "@", "\t", "\r")


def _cell(value):
    if isinstance(value, list):
        value = ", ".join(map(str, value))
    # Een post die met '=' of '@' begint, zou Excel als formule uitvoeren.
    if isinstance(value, str) and value.startswith(_FORMULA_START):
        return "'" + value
    return value


def _csv(rows: list[dict], columns: list[str], filename: str) -> Response:
    buf = io.StringIO()
    buf.write("﻿")  # zodat Excel/Sheets de accenten goed leest
    writer = csv.DictWriter(buf, fieldnames=columns, delimiter=";", extrasaction="ignore")
    writer.writeheader()
    for r in rows:
        writer.writerow({k: _cell(r.get(k)) for k in columns})
    return Response(buf.getvalue(), mimetype="text/csv",
                    headers={"Content-Disposition": f"attachment; filename={filename}"})


@app.get("/api/export/trends.csv")
def export_trends():
    a = _args()
    window = _window("24u")
    with db.session() as conn:
        result = trends.compute(conn, window, a["platform"], 500, a["min_rel"], a["min_nl"],
                                a["include_demo"])
    return _csv(result["topics"], ["type_label", "name", "posts", "baseline", "growth_pct", "new",
                                   "authors", "engagement", "platforms", "score"],
                f"trends-{window}.csv")


@app.get("/api/export/posts.csv")
def export_posts():
    a = _args()
    window = request.args.get("window", "7d")
    hours = trends.WINDOWS.get(window, trends.WINDOWS["7d"])["hours"]
    with db.session() as conn:
        rows = [db.row_to_dict(r) for r in trends.load_posts(
            conn, db.now() - timedelta(hours=hours), db.now() + timedelta(minutes=1),
            a["platform"], a["min_rel"], a["min_nl"], a["include_demo"])]
    return _csv(rows, ["posted_at", "platform", "author", "text", "url", "likes", "comments",
                       "shares", "views", "relevance", "categories", "brands", "places", "city",
                       "hashtags"], f"posts-{window}.csv")


# --- Vandaag ------------------------------------------------------------------

def _news(conn, kind: str, include_demo: bool, days: int = 14, limit: int = 8) -> list[dict]:
    """Nieuws per soort: 'snackspert' (jouw naam in het nieuws), 'amsterdam' of 'snack'."""
    since = db.iso(db.now() - timedelta(days=days))
    demo = "" if include_demo else " AND n.demo = 0"
    if kind == "snackspert":
        where = "n.title LIKE '%snackspert%'"
    elif kind == "amsterdam":
        where = ("(n.title LIKE '%amsterdam%' OR n.query LIKE 'Amsterdam%') "
                 "AND (p.relevance >= 0.35 OR n.demo = 1)")
    else:
        where = "(p.relevance >= 0.35 OR n.demo = 1)"
    return [dict(r) for r in conn.execute(
        "SELECT n.* FROM news n LEFT JOIN posts p ON p.id = n.id "
        f"WHERE n.published_at >= ? AND {where}{demo} ORDER BY n.published_at DESC LIMIT ?",
        (since, limit))]


def _watched(conn) -> dict:
    return {(r["kind"], r["ref"]): r["status"] for r in conn.execute("SELECT kind, ref, status FROM watchlist")}


def _candidates(conn, include_demo: bool, city: str | None = None, limit: int = 12) -> list[dict]:
    base = signals.baselines(conn, include_demo=include_demo)
    cands = trends.candidates(conn, 72, city, include_demo, limit)
    posts = _posts_by_id(conn, {c["id"] for c in cands}, base)
    watched = _watched(conn)
    out = []
    for c in cands:
        p = posts.get(c["id"])
        if p:
            p["reasons"] = c["reasons"]
            p["watch"] = watched.get(("post", c["id"]))
            out.append(p)
    return out


@app.get("/api/vandaag")
def api_vandaag():
    a = _args()
    with db.session() as conn:
        cands = _candidates(conn, a["include_demo"])
        topics = trends.compute(conn, "24u", None, 60, include_demo=a["include_demo"])["topics"]
        early = [t for t in topics if t["phase"] in ("vroeg", "groeit")
                 and t["type"] in ("woord", "zin", "product", "zaak")][:8]
        prods = products.overview(conn, a["include_demo"], days=2, only_relevant=False)["products"][:8]
        amsterdam = _candidates(conn, a["include_demo"], "Amsterdam", 4)
        lijst = {r["status"]: r["n"] for r in conn.execute(
            "SELECT status, COUNT(*) AS n FROM watchlist GROUP BY status")}
        prof = taste.profile(conn)
        hits = spots.radar_hits(conn, days=7, include_demo=a["include_demo"])
        tips_in_radar = []
        for r in conn.execute("SELECT * FROM spots"):
            if r["id"] in hits and r["status"] not in spots.DONE:
                tips_in_radar.append({**db.row_to_dict(r), "radar": hits[r["id"]]})
        tips_in_radar.sort(key=lambda t: t["radar"]["posts"], reverse=True)
        tips_in_radar = tips_in_radar[:6]
        return jsonify({
            "candidates": cands,
            "early_topics": early,
            "phases": trends.PHASES,
            "new_products": prods,
            "snackspert_news": _news(conn, "snackspert", a["include_demo"], days=30, limit=5),
            "snack_news": _news(conn, "snack", a["include_demo"], days=3, limit=6),
            "amsterdam": amsterdam,
            "watchlist": lijst,
            "learned": taste.summary(prof),
            "learned_from": {**prof.sources, "eigen_posts": conn.execute("SELECT COUNT(*) FROM own_posts").fetchone()[0]},
            "audience": [{"snack": k, **v} for k, v in list(ownposts.lifts(conn).items())[:5] if v["lift"] >= 1.1],
            "tips_in_radar": tips_in_radar,
            "test_ideas": products.test_ideas(conn, a["include_demo"], limit=5),
        })


@app.get("/api/kandidaten")
def api_kandidaten():
    a = _args()
    with db.session() as conn:
        return jsonify(_candidates(conn, a["include_demo"], a["city"], 20))


@app.get("/api/nieuws")
def api_nieuws():
    a = _args()
    kind = request.args.get("soort", "snack")
    with db.session() as conn:
        return jsonify(_news(conn, kind, a["include_demo"], days=14, limit=30))


# --- Te proberen-lijst -----------------------------------------------------------

WATCH_STATUSES = ("te proberen", "gepland", "bezocht", "gereviewd", "afgevallen")


@app.get("/api/lijst")
def api_lijst():
    marks = ",".join("?" * len(spots.PLANNED))
    with db.session() as conn:
        rows = [dict(r) for r in conn.execute(
            "SELECT * FROM watchlist ORDER BY CASE status WHEN 'te proberen' THEN 0 WHEN 'gepland' THEN 1 "
            "WHEN 'bezocht' THEN 2 WHEN 'gereviewd' THEN 3 ELSE 4 END, updated_at DESC")]
        # Tips en routes die je op 'te proberen' of 'gepland' zette: je eigen plan.
        tips = [db.row_to_dict(r) for r in conn.execute(
            f"SELECT * FROM spots WHERE status IN ({marks}) ORDER BY status DESC, updated_at DESC", spots.PLANNED)]
        routes = [d for d in spots.routes(conn) if d["status"] in spots.PLANNED]
    for t in tips:
        t["maps"] = spots.maps_search(t["name"], t["place"])
    return jsonify({"items": rows, "statuses": WATCH_STATUSES, "tips": tips, "routes": routes,
                    "tip_statuses": spots.STATUSES})


@app.post("/api/lijst")
def add_lijst():
    d = _body()
    kind, ref, title = d.get("kind"), _text(d, "ref", 300), _text(d, "title", 300)
    if kind not in ("post", "zaak", "product", "onderwerp") or not ref or not title:
        return jsonify({"fout": "soort, verwijzing en titel zijn nodig"}), 400
    now = db.iso(db.now())
    with db.session() as conn:
        conn.execute(
            "INSERT INTO watchlist(kind, ref, title, url, city, note, added_at, updated_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?) ON CONFLICT(kind, ref) DO UPDATE SET updated_at = excluded.updated_at",
            (kind, ref, title, _text(d, "url", 1000) or None, _text(d, "city", 100) or None,
             _text(d, "note", 2000), now, now))
    return jsonify({"ok": True})


@app.patch("/api/lijst/<int:wid>")
def update_lijst(wid: int):
    d = _body()
    sets, args = [], []
    if d.get("status") in WATCH_STATUSES:
        sets.append("status = ?")
        args.append(d["status"])
    if "note" in d:
        sets.append("note = ?")
        args.append(str(d["note"])[:2000])
    if not sets:
        return jsonify({"fout": "niets te wijzigen"}), 400
    sets.append("updated_at = ?")
    args.append(db.iso(db.now()))
    with db.session() as conn:
        conn.execute(f"UPDATE watchlist SET {', '.join(sets)} WHERE id = ?", args + [wid])
    return jsonify({"ok": True})


@app.delete("/api/lijst/<int:wid>")
def delete_lijst(wid: int):
    with db.session() as conn:
        conn.execute("DELETE FROM watchlist WHERE id = ?", (wid,))
    return jsonify({"ok": True})


@app.get("/api/export/lijst.csv")
def export_lijst():
    with db.session() as conn:
        rows = [dict(r) for r in conn.execute("SELECT * FROM watchlist ORDER BY added_at")]
    return _csv(rows, ["status", "kind", "title", "city", "note", "url", "added_at", "updated_at"],
                "te-proberen.csv")


# --- ♥ en 👎 -----------------------------------------------------------------

@app.get("/api/feedback")
def api_feedback():
    with db.session() as conn:
        return jsonify({r["post_id"]: r["value"] for r in conn.execute("SELECT post_id, value FROM feedback")})


@app.post("/api/feedback")
def set_feedback():
    d = _body()
    post_id, value = _text(d, "post_id", 200), d.get("value")
    if not post_id or value not in (-1, 0, 1):
        return jsonify({"fout": "post en waarde (1, -1 of 0) zijn nodig"}), 400
    with db.session() as conn:
        if value == 0:
            conn.execute("DELETE FROM feedback WHERE post_id = ?", (post_id,))
        else:
            conn.execute("INSERT INTO feedback(post_id, value, at) VALUES (?, ?, ?) "
                         "ON CONFLICT(post_id) DO UPDATE SET value = excluded.value, at = excluded.at",
                         (post_id, value, db.iso(db.now())))
    return jsonify({"ok": True})


# --- importeren: je postoverzicht en je tips & routes -------------------------

@app.post("/api/import")
def api_import():
    f = request.files.get("bestand")
    if not f or not f.filename:
        return jsonify({"fout": "Kies eerst een Excel-bestand (.xlsx)."}), 400
    try:
        parsed = imports.read_workbook(f.read())
    except imports.ImportError_ as exc:
        return jsonify({"fout": str(exc)}), 400
    with db.session() as conn:
        result = imports.save(conn, parsed)
    parts = []
    if result["posts"]:
        parts.append(f"{result['posts']} eigen posts")
    if result["spots"]:
        parts.append(f"{result['spots']} tips ({result['spots_new']} nieuw)")
    if result["routes"]:
        parts.append(f"{result['routes']} routes")
    return jsonify({**result, "melding": "Ingelezen: " + ", ".join(parts) + "."})


# --- mijn posts ----------------------------------------------------------------

@app.get("/api/mijnposts")
def api_mijnposts():
    year = request.args.get("jaar") or None
    with db.session() as conn:
        return jsonify(ownposts.overview(conn, year))


@app.get("/api/trefkans")
def api_trefkans():
    with db.session() as conn:
        return jsonify(trefkans.report(conn))


@app.post("/api/hookcheck")
def api_hookcheck():
    d = _body()
    caption = _text(d, "caption", 3000)
    if not caption:
        return jsonify({"fout": "plak eerst een caption"}), 400
    with db.session() as conn:
        return jsonify(ownposts.hook_check(conn, caption, _text(d, "format", 60) or None))


# --- tips & routes -----------------------------------------------------------------

@app.get("/api/tips")
def api_tips():
    a = _args()
    with db.session() as conn:
        out = spots.listing(conn, a["include_demo"])
    out["statuses"] = spots.STATUSES
    return jsonify(out)


@app.post("/api/tips")
def add_tip():
    d = _body()
    name = _text(d, "name", 200)
    if not name:
        return jsonify({"fout": "een naam is nodig"}), 400
    now = db.iso(db.now())
    lst = _text(d, "list", 60) or "Eigen tips"
    with db.session() as conn:
        conn.execute(
            "INSERT INTO spots(name, place, specialty, region, lists, note, status, origin, added_at, updated_at) "
            "VALUES (?, ?, ?, ?, ?, ?, 'nieuw', 'handmatig', ?, ?) ON CONFLICT(name, place) DO UPDATE SET "
            "specialty = excluded.specialty, updated_at = excluded.updated_at",
            (name, _text(d, "place", 100), _text(d, "specialty", 500), _text(d, "region", 60),
             json.dumps([lst]), _text(d, "note", 2000), now, now))
    return jsonify({"ok": True})


@app.patch("/api/tips/<int:sid>")
def update_tip(sid: int):
    d = _body()
    sets, args = [], []
    if d.get("status") in spots.STATUSES:
        sets.append("status = ?")
        args.append(d["status"])
    if "note" in d:
        sets.append("note = ?")
        args.append(str(d["note"])[:2000])
    if not sets:
        return jsonify({"fout": "niets te wijzigen"}), 400
    sets.append("updated_at = ?")
    args.append(db.iso(db.now()))
    with db.session() as conn:
        conn.execute(f"UPDATE spots SET {', '.join(sets)} WHERE id = ?", args + [sid])
    return jsonify({"ok": True})


@app.delete("/api/tips/<int:sid>")
def delete_tip(sid: int):
    with db.session() as conn:
        conn.execute("DELETE FROM spots WHERE id = ?", (sid,))
    return jsonify({"ok": True})


@app.get("/api/routes")
def api_routes():
    with db.session() as conn:
        return jsonify({"routes": spots.routes(conn), "statuses": spots.STATUSES})


@app.patch("/api/routes/<int:rid>")
def update_route(rid: int):
    d = _body()
    if d.get("status") not in spots.STATUSES:
        return jsonify({"fout": "onbekende status"}), 400
    with db.session() as conn:
        conn.execute("UPDATE routes SET status = ? WHERE id = ?", (d["status"], rid))
    return jsonify({"ok": True})


@app.get("/api/export/tips.csv")
def export_tips():
    with db.session() as conn:
        rows = [db.row_to_dict(r) for r in conn.execute("SELECT * FROM spots ORDER BY region, place, name")]
    for r in rows:
        r["lists"] = ", ".join(r["lists"])
    return _csv(rows, ["name", "place", "region", "specialty", "lists", "status", "note"], "tips.csv")


# --- viral-potentie ----------------------------------------------------------

@app.get("/api/potentie")
def api_potentie():
    a = _args()
    limit = _num("limit", 10, int, 1, 50)
    with db.session() as conn:
        out = potential.ranking(conn, limit, a["include_demo"])
    out["statuses"] = spots.STATUSES
    return jsonify(out)


# --- routes die de tool bedenkt, en nieuwe tips uit de radar ------------------------

@app.get("/api/routes/voorstellen")
def api_route_proposals():
    a = _args()
    with db.session() as conn:
        return jsonify(routeplan.proposals(conn, a["include_demo"]))


@app.post("/api/routes/bewaar")
def api_route_save():
    d = _body()
    if not isinstance(d.get("stops"), list) or not d["stops"] or not d.get("name"):
        return jsonify({"fout": "route zonder stops"}), 400
    with db.session() as conn:
        rid = routeplan.save(conn, d)
    return jsonify({"ok": True, "id": rid})


@app.post("/api/routes/afwijzen")
def api_route_reject():
    key = _text(_body(), "key", 500)
    if not key:
        return jsonify({"fout": "geen route"}), 400
    with db.session() as conn:
        routeplan.reject(conn, key)
    return jsonify({"ok": True})


@app.post("/api/locaties")
def api_geocode():
    started = geo.fill_in_background()
    return jsonify({"started": started, **geo.progress()})


@app.get("/api/nieuwezaken")
def api_new_places():
    with db.session() as conn:
        return jsonify({"places": nieuwezaken.new_places(conn), **nieuwezaken.summary(conn)})


@app.post("/api/tips/plekken")
def api_spot_places():
    from . import plekken

    with db.session() as conn:
        settings = db.get_settings(conn)
    if not apify.available():
        return jsonify({"fout": "zet eerst APIFY_TOKEN in .env"}), 400
    return jsonify({"started": plekken.fill_in_background(settings)})


@app.get("/api/tips/suggesties")
def api_tip_suggestions():
    a = _args()
    with db.session() as conn:
        return jsonify(spots.radar_suggestions(conn, a["include_demo"]))
