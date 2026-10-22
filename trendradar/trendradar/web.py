"""De webinterface en de JSON-API waar die op draait."""
from __future__ import annotations

import csv
import io
import json
import threading
from datetime import timedelta

from flask import Flask, Response, jsonify, request, send_from_directory

from . import (budget, collector, config, db, lexicon, products, signals, snackspert,
               trends)
from .sources import apify, meta_graph

app = Flask(__name__, static_folder="static", static_url_path="/static")

TOPIC_COLUMNS = {"hashtag": "hashtags", "categorie": "categories", "merk": "brands",
                 "zaak": "places", "zin": "phrases", "woord": "phrases"}


def _args():
    a = request.args
    return {
        "platform": a.get("platform") or None,
        "min_rel": float(a.get("min_rel", 0.35)),
        "min_nl": float(a.get("min_nl", 0.4)),
        "include_demo": a.get("demo", "1") != "0",
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
            "SELECT started_at FROM runs WHERE status != 'bezig' ORDER BY started_at DESC, id DESC LIMIT 1").fetchone()
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
    window = request.args.get("window", "24u")
    if window not in trends.WINDOWS:
        return jsonify({"fout": "onbekende periode"}), 400
    with db.session() as conn:
        result = trends.compute(conn, window, a["platform"], 60, a["min_rel"], a["min_nl"],
                                a["include_demo"])
        result["volume"] = trends.volume(conn, window, a["platform"], a["min_rel"], a["min_nl"],
                                         a["include_demo"])
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
            "sentiment", "summary", "hashtags", "demo", "gain_per_hour")
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
    where = ["relevance >= ?", "nl_score >= ?"]
    args: list = [a["min_rel"], a["min_nl"]]
    if a["platform"]:
        where.append("platform = ?")
        args.append(a["platform"])
    if not a["include_demo"]:
        where.append("demo = 0")
    window = q.get("window")
    if window in trends.WINDOWS:
        where.append("posted_at >= ?")
        args.append(db.iso(db.now() - timedelta(hours=trends.WINDOWS[window]["hours"])))
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
    limit = min(200, int(q.get("limit", 60)))
    offset = int(q.get("offset", 0))
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
    days = int(request.args.get("days", 30))
    with db.session() as conn:
        result = products.overview(conn, a["include_demo"], days,
                                   only_relevant=request.args.get("alles") != "1")
        result["status"] = db.get_state(conn, "supermarkt_status", {})
        base = signals.baselines(conn, include_demo=a["include_demo"])
    for m in result["mentioned"]:
        if m["example"]:
            m["example"] = _slim(m["example"], base)
    return jsonify(result)


@app.get("/api/zaken")
def api_zaken():
    a = _args()
    window = request.args.get("window", "7d")
    with db.session() as conn:
        result = trends.compute(conn, window, a["platform"], 1000, a["min_rel"], a["min_nl"],
                                a["include_demo"])
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
    places = _merge_places(places)
    return jsonify({"window": window, "places": places[:60], "cities": result["cities"],
                    "reviewed_count": len(reviewed)})


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
    data = request.get_json(force=True)
    platform = data.get("platform")
    kind = data.get("kind")
    value = (data.get("value") or "").strip().lstrip("#@").strip()
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
    data = request.get_json(force=True)
    sets, args = [], []
    if data.get("status") in ("actief", "gepauzeerd", "afgewezen", "kandidaat"):
        sets.append("status = ?")
        args.append(data["status"])
        if data["status"] == "actief":
            sets.append("empty_streak = 0")
    if "priority" in data:
        sets.append("priority = ?")
        args.append(max(0.1, min(3.0, float(data["priority"]))))
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
    data = request.get_json(force=True)
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
            elif isinstance(default, list):
                value = [str(v).strip() for v in value if str(v).strip()]
            else:
                value = str(value)
        except (TypeError, ValueError):
            return jsonify({"fout": f"ongeldige waarde voor {key}"}), 400
        clean[key] = value
    if "interval_uren" in clean and clean["interval_uren"] < 1:
        return jsonify({"fout": "interval minimaal 1 uur"}), 400
    with db.session() as conn:
        db.set_settings(conn, clean)
        return jsonify(db.get_settings(conn))


@app.get("/api/budget")
def api_budget():
    with db.session() as conn:
        settings = db.get_settings(conn)
        return jsonify(budget.overview(conn, settings))


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

def _csv(rows: list[dict], columns: list[str], filename: str) -> Response:
    buf = io.StringIO()
    buf.write("﻿")  # zodat Excel/Sheets de accenten goed leest
    writer = csv.DictWriter(buf, fieldnames=columns, delimiter=";", extrasaction="ignore")
    writer.writeheader()
    for r in rows:
        writer.writerow({k: (", ".join(map(str, r[k])) if isinstance(r.get(k), list) else r.get(k))
                         for k in columns})
    return Response(buf.getvalue(), mimetype="text/csv",
                    headers={"Content-Disposition": f"attachment; filename={filename}"})


@app.get("/api/export/trends.csv")
def export_trends():
    a = _args()
    window = request.args.get("window", "24u")
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
