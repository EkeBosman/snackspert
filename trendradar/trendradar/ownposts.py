"""Analyse van je eigen posts, en wat de trendradar daarvan leert.

De pagina 'Mijn posts' rekent alles zelf uit: per maand, per format, kanaal,
locatie en herkenbaarheid, de toppers en de supermarkttests. Daarnaast kijkt
de tool welke snacks het bij jouw publiek beter doen dan je gemiddelde post.
Dat gebruikt de trendradar als extra signaal: een kandidaat over een snack
waar jouw volgers dol op zijn, krijgt voorrang.

Volgers bij collabs zijn onbetrouwbaar (ze worden gedeeld met een ander
account) en tellen daarom niet mee in 'volgers per post'.
"""
from __future__ import annotations

import re
from collections import defaultdict
from statistics import median

from . import classify

DIMENSIONS = {"format": "Format", "channel": "Kanaal", "location": "Locatie", "recognition": "Herkenbaarheid"}
MIN_GROUP = 5          # minder posts zegt te weinig
MIN_SNACK = 6
SUPERMARKET_TEST = re.compile(r"de grote (.+?) uit de supermarkt", re.I)
SUPERMARKET_TEST_SHORT = re.compile(r"de grote (.+?)\s*test\b", re.I)  # 'De grote knoflooksaus test'


def _test_product(caption: str) -> str | None:
    m = SUPERMARKET_TEST.search(caption) or SUPERMARKET_TEST_SHORT.search(caption)
    return m.group(1).strip() if m else None


def _rows(conn, year: str | None = None) -> list[dict]:
    sql, args = "SELECT * FROM own_posts", []
    if year:
        sql += " WHERE month LIKE ?"
        args.append(f"{year}-%")
    return [dict(r) for r in conn.execute(sql + " ORDER BY COALESCE(date, month) DESC", args)]


def _med(values) -> float:
    values = [v for v in values if v is not None]
    return float(median(values)) if values else 0.0


def _followers(rows) -> tuple[int, int]:
    """(volgers, aantal posts) zonder collabs."""
    counted = [r for r in rows if r["followers_count"] and r["followers"] is not None]
    return sum(r["followers"] for r in counted), len(counted)


def _stats(rows, overall_median: float) -> dict:
    fol, n_fol = _followers(rows)
    med = _med(r["views"] for r in rows)
    return {
        "posts": len(rows),
        "median_views": round(med),
        "avg_views": round(sum(r["views"] or 0 for r in rows) / len(rows)) if rows else 0,
        "followers_per_post": round(fol / n_fol, 1) if n_fol else None,
        "median_shares": round(_med(r["shares"] for r in rows)),
        "index": round(100 * med / overall_median) if overall_median else None,
    }


def years(conn) -> list[str]:
    return [r["y"] for r in conn.execute(
        "SELECT DISTINCT substr(month, 1, 4) AS y FROM own_posts WHERE month IS NOT NULL ORDER BY y DESC")]


def snack_lifts(rows: list[dict], overall_median: float | None = None) -> dict[str, dict]:
    """Welke snacks doen het beter dan je mediane post? {snack: {lift, posts, median_views}}."""
    if overall_median is None:
        overall_median = _med(r["views"] for r in rows)
    groups = defaultdict(list)
    for r in rows:
        text = " " + (r["caption"] or "").lower() + " "
        for g in classify.item_groups(text, classify.extract_hashtags(r["caption"] or "")):
            groups[g].append(r)
    out = {}
    for g, items in groups.items():
        if len(items) < MIN_SNACK or not overall_median:
            continue
        med = _med(i["views"] for i in items)
        out[g] = {"lift": round(med / overall_median, 2), "posts": len(items), "median_views": round(med)}
    return dict(sorted(out.items(), key=lambda kv: kv[1]["lift"], reverse=True))


def dimension_lifts(conn, dim: str) -> dict[str, dict]:
    """Per waarde (bijv. 'Buiten Amsterdam'): mediaan views gedeeld door de mediaan van alle ingedeelde posts."""
    rows = [r for r in _rows(conn) if r[dim]]
    overall = _med(r["views"] for r in rows)
    per = defaultdict(list)
    for r in rows:
        per[r[dim]].append(r)
    return {k: {"lift": round(_med(i["views"] for i in v) / overall, 2), "posts": len(v)}
            for k, v in per.items() if len(v) >= MIN_GROUP and overall}


def lifts(conn) -> dict[str, dict]:
    """Snack-lift over al je posts: gebruikt door de trendradar."""
    return snack_lifts(_rows(conn))


def posted_handles(conn) -> dict[str, dict]:
    """Accounts die je in een eigen post noemde: {handle zonder @, kleine letters: {date, url}}."""
    out = {}
    for r in conn.execute("SELECT caption, date, month, url FROM own_posts WHERE caption LIKE '%@%' "
                          "ORDER BY COALESCE(date, month)"):
        for m in classify.extract_mentions(r["caption"] or ""):
            out[m.lower()] = {"date": r["date"] or r["month"], "url": r["url"]}
    return out


def caption_index(conn) -> list[tuple[str, dict]]:
    """Je captions als doorzoekbare tekst: [(tekst zonder spaties, {date, url})]."""
    return [(re.sub(r"[^a-z0-9]", "", classify.norm(r["caption"] or "")),
             {"date": r["date"] or r["month"], "url": r["url"]})
            for r in conn.execute("SELECT caption, date, month, url FROM own_posts ORDER BY COALESCE(date, month) DESC")]


def find_posted(key: str, index: list[tuple[str, dict]]) -> dict | None:
    """De laatste eigen post waarin een zaak (als sleutel zonder spaties) voorkomt."""
    return next((info for blob, info in index if key and key in blob), None)


def _supermarket_tests(rows) -> list[dict]:
    out = []
    for r in rows:
        product = _test_product(r["caption"] or "")
        if (r["format"] or "") != "Supermarkttest" and not SUPERMARKET_TEST.search(r["caption"] or ""):
            continue
        out.append({"product": product or (r["caption"] or "")[:40], "month": r["month"],
                    "views": r["views"], "followers": r["followers"] if r["followers_count"] else None,
                    "shares": r["shares"], "url": r["url"]})
    return sorted(out, key=lambda x: x["views"] or 0, reverse=True)


def _slim(r) -> dict:
    return {k: r[k] for k in ("id", "date", "month", "caption", "url", "views", "shares", "saves",
                              "followers", "followers_count", "format", "channel", "location")}


def _fmt(n) -> str:
    return f"{round(n):,}".replace(",", ".")


def _insights(rows, groups, snacks, all_rows, overall) -> list[str]:
    out = []
    fmts = [(k, v) for k, v in groups["format"].items() if v["posts"] >= MIN_GROUP]
    if fmts:
        k, v = max(fmts, key=lambda kv: kv[1]["median_views"])
        out.append(f"Je best bekeken format is <b>{k}</b>: mediaan {_fmt(v['median_views'])} views, "
                   f"{v['index'] - 100:+d}% ten opzichte van je mediaan.")
        with_f = [(k, v) for k, v in fmts if v["followers_per_post"] is not None]
        if with_f:
            k, v = max(with_f, key=lambda kv: kv[1]["followers_per_post"])
            out.append(f"De meeste nieuwe volgers per post haal je met <b>{k}</b>: "
                       f"{str(v['followers_per_post']).replace('.', ',')} per post.")
    loc = groups["location"]
    if loc.get("Amsterdam", {}).get("posts", 0) >= MIN_GROUP and loc.get("Buiten Amsterdam", {}).get("posts", 0) >= MIN_GROUP:
        a, b = loc["Amsterdam"]["median_views"], loc["Buiten Amsterdam"]["median_views"]
        better, worse = ("buiten Amsterdam", "in Amsterdam") if b > a else ("in Amsterdam", "buiten Amsterdam")
        out.append(f"Zaken {better} doen het beter dan {worse}: mediaan {_fmt(max(a, b))} "
                   f"tegen {_fmt(min(a, b))} views.")
    rec = groups["recognition"]
    if rec.get("Mainstream", {}).get("posts", 0) >= MIN_GROUP and rec.get("Niche", {}).get("posts", 0) >= MIN_GROUP:
        out.append(f"Herkenbare snacks werken: <b>mainstream</b> haalt mediaan "
                   f"{_fmt(rec['Mainstream']['median_views'])} views, <b>niche</b> {_fmt(rec['Niche']['median_views'])}.")
    top = [(k, v) for k, v in snacks.items() if v["lift"] >= 1.1][:3]
    if top:
        parts = [f"<b>{k}</b> ({str(v['lift']).replace('.', ',')}×)" for k, v in top]
        out.append("Snacks die het bij jouw publiek beter doen dan gemiddeld: " + ", ".join(parts) + ".")
    # Laatste 3 maanden tegen dezelfde maanden een jaar eerder.
    months = sorted({r["month"] for r in all_rows if r["month"]})
    if len(months) >= 15:
        last = months[-3:]
        before = [f"{int(m[:4]) - 1}{m[4:]}" for m in last]
        now_med = _med(r["views"] for r in all_rows if r["month"] in last)
        then_med = _med(r["views"] for r in all_rows if r["month"] in before)
        if then_med:
            diff = round(100 * (now_med / then_med - 1))
            out.append(f"De laatste drie maanden ({last[0]} t/m {last[-1]}) haal je mediaan {_fmt(now_med)} views: "
                       f"{diff:+d}% ten opzichte van een jaar eerder.")
    tests = _supermarket_tests(rows)
    if tests:
        out.append(f"Je best bekeken supermarkttest: <b>{tests[0]['product']}</b> ({_fmt(tests[0]['views'] or 0)} views).")
    return out


def overview(conn, year: str | None = None) -> dict:
    all_rows = _rows(conn)
    rows = [r for r in all_rows if not year or (r["month"] or "").startswith(year)]
    if not rows:
        return {"posts": 0, "years": years(conn)}
    overall = _med(r["views"] for r in rows)
    fol, n_fol = _followers(rows)
    views_total = sum(r["views"] or 0 for r in rows)
    kpis = {
        "posts": len(rows),
        "views_total": views_total,
        "median_views": round(overall),
        "followers": fol,
        "followers_per_post": round(fol / n_fol, 1) if n_fol else None,
        "followers_per_10k": round(10000 * fol / sum(r["views"] or 0 for r in rows if r["followers_count"]), 1)
        if n_fol else None,
        "collabs": sum(1 for r in rows if (r["format"] or "") in ("Samenwerking", "Collab")),
    }
    by_month = defaultdict(list)
    for r in all_rows:
        if r["month"]:
            by_month[r["month"]].append(r)
    months = []
    for m in sorted(by_month):
        if year and not m.startswith(year):
            continue
        items = by_month[m]
        prev = by_month.get(f"{int(m[:4]) - 1}{m[4:]}")
        f, _ = _followers(items)
        months.append({"month": m, "posts": len(items), "median_views": round(_med(i["views"] for i in items)),
                       "views_total": sum(i["views"] or 0 for i in items), "followers": f,
                       "median_prev_year": round(_med(i["views"] for i in prev)) if prev else None})
    groups = {}
    for dim in DIMENSIONS:
        subset = [r for r in rows if r[dim]]
        sub_med = _med(r["views"] for r in subset)
        per = defaultdict(list)
        for r in subset:
            per[r[dim]].append(r)
        groups[dim] = dict(sorted(((k, _stats(v, sub_med)) for k, v in per.items()),
                                  key=lambda kv: kv[1]["median_views"], reverse=True))
    # Als lijsten: JSON-objecten verliezen hun volgorde (Flask sorteert de sleutels).
    group_lists = {dim: [{"name": k, **v} for k, v in g.items()] for dim, g in groups.items()}
    snacks = snack_lifts(rows, overall)
    counted = [r for r in rows if r["followers_count"] and r["followers"] is not None]
    return {
        "years": years(conn),
        "year": year,
        "kpis": kpis,
        "months": months,
        "dimensions": [[k, v] for k, v in DIMENSIONS.items()],
        "groups": group_lists,
        "classified": sum(1 for r in rows if r["format"] or r["channel"]),
        "snacks": [{"snack": k, **v} for k, v in snacks.items()],
        "top_views": [_slim(r) for r in sorted(rows, key=lambda r: r["views"] or 0, reverse=True)[:10]],
        "top_followers": [_slim(r) for r in sorted(counted, key=lambda r: r["followers"], reverse=True)[:10]],
        "top_shares": [_slim(r) for r in sorted(rows, key=lambda r: r["shares"] or 0, reverse=True)[:10]],
        "supermarket_tests": _supermarket_tests(rows)[:25],
        "insights": _insights(rows, groups, snacks, all_rows, overall),
    }
