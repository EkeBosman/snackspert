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
from html import escape
from statistics import median

from . import classify, db

DIMENSIONS = {"format": "Format", "channel": "Kanaal", "location": "Locatie", "recognition": "Herkenbaarheid"}
MIN_GROUP = 5          # minder posts zegt te weinig
MIN_SNACK = 6
SUPERMARKET_TEST = re.compile(r"de grote (.+?) uit de supermarkt", re.I)
SUPERMARKET_TEST_SHORT = re.compile(r"de grote (.+?)\s*test\b", re.I)  # 'De grote knoflooksaus test'


def _test_product(caption: str) -> str | None:
    m = SUPERMARKET_TEST.search(caption) or SUPERMARKET_TEST_SHORT.search(caption)
    return m.group(1).strip() if m else None


_MONTH_RE = re.compile(r"^\d{4}-\d{2}$")


def _rows(conn, year: str | None = None) -> list[dict]:
    sql, args = "SELECT * FROM own_posts", []
    if year:
        sql += " WHERE month LIKE ?"
        args.append(f"{year}-%")
    rows = [dict(r) for r in conn.execute(sql + " ORDER BY COALESCE(date, month) DESC", args)]
    for r in rows:
        # Een maand als 'maart 2026' uit een oudere import: niet laten crashen, gewoon overslaan.
        if not _MONTH_RE.match(r["month"] or ""):
            r["month"] = None
    return rows


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
        "SELECT DISTINCT substr(month, 1, 4) AS y FROM own_posts "
        "WHERE month GLOB '[0-9][0-9][0-9][0-9]-[0-9][0-9]' ORDER BY y DESC")]


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


def _per_10k(followers: int, rows) -> float | None:
    views = sum(r["views"] or 0 for r in rows if r["followers_count"] and r["followers"] is not None)
    return round(10000 * followers / views, 1) if views else None


def _fmt(n) -> str:
    return f"{round(n):,}".replace(",", ".")


def _insights(rows, groups, snacks, all_rows, overall) -> list[str]:
    out = []
    fmts = [(k, v) for k, v in groups["format"].items() if v["posts"] >= MIN_GROUP]
    if fmts:
        k, v = max(fmts, key=lambda kv: kv[1]["median_views"])
        vs = f", {v['index'] - 100:+d}% ten opzichte van je mediaan" if v["index"] is not None else ""
        out.append(f"Je best bekeken format is <b>{escape(k)}</b>: mediaan {_fmt(v['median_views'])} views{vs}.")
        with_f = [(k, v) for k, v in fmts if v["followers_per_post"] is not None]
        if with_f:
            k, v = max(with_f, key=lambda kv: kv[1]["followers_per_post"])
            out.append(f"De meeste nieuwe volgers per post haal je met <b>{escape(k)}</b>: "
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
        parts = [f"<b>{escape(k)}</b> ({str(v['lift']).replace('.', ',')}×)" for k, v in top]
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
        out.append(f"Je best bekeken supermarkttest: <b>{escape(tests[0]['product'])}</b> "
                   f"({_fmt(tests[0]['views'] or 0)} views).")
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
        "followers_per_10k": _per_10k(fol, rows),
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
        "timing": fair_timing(all_rows),
        "formats": [g["name"] for g in group_lists.get("format", [])],
    }


# --- eerlijk vergelijken: dag en maand binnen hetzelfde format of jaar -----------------

DAYS = ["maandag", "dinsdag", "woensdag", "donderdag", "vrijdag", "zaterdag", "zondag"]
MONTHS = ["januari", "februari", "maart", "april", "mei", "juni", "juli", "augustus", "september",
          "oktober", "november", "december"]
MIN_FAIR = 8


def _ratios(rows, ref) -> list[tuple[dict, float, float | None]]:
    """Elke post gedeeld door de mediaan van zijn eigen groep (format, of anders het jaar)."""
    groups = defaultdict(list)
    for r in rows:
        groups[ref(r)].append(r)
    out = []
    for items in groups.values():
        if len(items) < 5:
            continue
        mv = _med(i["views"] for i in items)
        fol = [i["followers"] for i in items if i["followers_count"] and i["followers"] is not None]
        mf = _med(fol) if fol else 0
        for i in items:
            if not mv:
                continue
            f = i["followers"] / mf if mf and i["followers_count"] and i["followers"] is not None else None
            out.append((i, (i["views"] or 0) / mv, f))
    return out


def _index(ratios, key) -> list[dict]:
    per = defaultdict(list)
    for r, v, f in ratios:
        k = key(r)
        if k is not None:
            per[k].append((r, v, f))
    out = []
    for k, items in per.items():
        if len(items) < MIN_FAIR:
            continue
        fol = [f for _, _, f in items if f is not None]
        formats = defaultdict(int)
        for r, _, _ in items:
            formats[r["format"] or "zonder format"] += 1
        top, n_top = max(formats.items(), key=lambda kv: kv[1])
        out.append({"key": k, "posts": len(items), "views_index": round(100 * _med(v for _, v, _ in items)),
                    "followers_index": round(100 * _med(fol)) if len(fol) >= 5 else None,
                    "mostly": top if n_top / len(items) >= 0.5 else None,
                    "mostly_pct": round(100 * n_top / len(items))})
    return out


def _weekday(r) -> int | None:
    from datetime import date
    try:
        return date.fromisoformat((r["date"] or "")[:10]).weekday()
    except ValueError:
        return None


def fair_timing(rows) -> dict:
    """Welke dag en maand doen het beter, eerlijk vergeleken?

    Dag: elke post tegen de mediaan van zijn eigen format (zondag is bij jou vooral
    supermarkttest-dag; zonder deze correctie meet je het format in plaats van de dag).
    Maand: elke post tegen de mediaan van zijn eigen jaar (je groeit, dus oude maanden
    zouden anders altijd slechter lijken).
    """
    by_format = _ratios(rows, lambda r: ("format", r["format"]) if r["format"] else ("jaar", (r["month"] or "")[:4]))
    days = sorted(_index(by_format, _weekday), key=lambda d: d["key"])
    for d in days:
        d["name"] = DAYS[d.pop("key")]
    by_year = _ratios(rows, lambda r: (r["month"] or "")[:4])
    months = sorted(_index(by_year, lambda r: int(r["month"][5:7]) if r["month"] else None), key=lambda d: d["key"])
    for m in months:
        m["name"] = MONTHS[m.pop("key") - 1]
    return {"days": days, "months": months}


# --- hook-check: hoe deed een eerste zin als deze het eerder? --------------------------

HOOK_WORDS = ("nieuw", "test", "eerlijk", "beste", "slechtste", "duurste", "goedkoopste", "viral", "nederland",
              "amsterdam", "geheim", "eerste", "laatste", "nooit", "iedereen", "waarom")


def _first_line(caption: str) -> str:
    return (caption or "").strip().split("\n")[0].strip()


def _hook_features(line: str) -> dict[str, str]:
    low = line.lower()
    out = {"vraag": "met vraagteken" if "?" in line else "zonder vraagteken",
           "lengte": "korte eerste zin (onder 40 tekens)" if len(line) < 40
           else "middellange eerste zin (40-80 tekens)" if len(line) < 80 else "lange eerste zin (80+ tekens)",
           "getal": "met een getal of prijs" if re.search(r"\d|€", line) else "zonder getal of prijs"}
    if line and not line[0].isalnum() and not line[0] in "\"'(":
        out["emoji"] = "begint met een emoji of teken"
    for w in HOOK_WORDS:
        if re.search(rf"(?<![\w]){w}", low):
            out[f"woord:{w}"] = f"het woord '{w}'"
    return out


def hook_check(conn, caption: str, fmt: str | None = None) -> dict:
    rows = [r for r in _rows(conn) if r["caption"]]
    if fmt:
        same = [r for r in rows if r["format"] == fmt]
        if len(same) >= 20:
            rows = same
        else:
            fmt = None
    line = _first_line(caption)
    if not line or len(rows) < 20:
        return {"findings": [], "similar": [], "posts": len(rows), "format": fmt}
    feats = [(r, _hook_features(_first_line(r["caption"]))) for r in rows]
    overall = _med(r["views"] for r in rows)
    findings = []
    for k, label in _hook_features(line).items():
        with_ = [r for r, f in feats if f.get(k) == label]
        without = [r for r, f in feats if f.get(k) != label]
        if len(with_) < 5 or len(without) < 5:
            continue
        mw, mo = _med(r["views"] for r in with_), _med(r["views"] for r in without)
        if not mo:
            continue
        fw = [r["followers"] for r in with_ if r["followers_count"] and r["followers"] is not None]
        fo = [r["followers"] for r in without if r["followers_count"] and r["followers"] is not None]
        findings.append({"label": label, "posts": len(with_), "index": round(100 * mw / mo),
                         "median_views": round(mw),
                         "followers": round(_med(fw)) if len(fw) >= 5 else None,
                         "followers_other": round(_med(fo)) if len(fo) >= 5 else None})
    findings.sort(key=lambda f: abs(f["index"] - 100), reverse=True)
    words = {w for w in re.findall(r"[a-zà-ÿ]{4,}", line.lower())}
    similar = []
    for r in rows:
        other = {w for w in re.findall(r"[a-zà-ÿ]{4,}", _first_line(r["caption"]).lower())}
        if words and other:
            overlap = len(words & other) / len(words | other)
            if overlap >= 0.2:
                similar.append((overlap, r))
    similar.sort(key=lambda x: x[0], reverse=True)
    return {"findings": findings, "posts": len(rows), "format": fmt, "median_views": round(overall),
            "similar": [{**_slim(r), "first_line": _first_line(r["caption"])[:120]} for _, r in similar[:3]]}


# --- je eigen posts automatisch bijwerken (Apify) ---------------------------------------

_SHORTCODE = re.compile(r"instagram\.com/(?:[\w.]+/)?(?:p|reel|reels|tv)/([\w-]+)")


def shortcode(url: str | None) -> str | None:
    m = _SHORTCODE.search(url or "")
    return m.group(1) if m else None


def merge_fetched(conn, posts: list[dict]) -> dict:
    """Zet opgehaalde posts (genormaliseerd door apify.normalize) in Mijn posts.

    Bestaat de post al (zelfde link), dan alleen de cijfers bijwerken die Apify kan zien
    (views, likes, reacties). Volgers per post en bewaard komen uit Instagram Insights,
    dus uit je Excel-export: die laat de tool staan.
    """
    by_code = {}
    for r in conn.execute("SELECT id, url FROM own_posts"):
        code = shortcode(r["url"])
        if code:
            by_code[code] = r["id"]
    now = db.iso(db.now())
    new = updated = 0
    for p in posts:
        code = shortcode(p.get("url"))
        if not code or not p.get("posted_at"):
            continue
        if code in by_code:
            conn.execute("UPDATE own_posts SET views = MAX(COALESCE(views, 0), ?), likes = MAX(COALESCE(likes, 0), ?), "
                         "comments = MAX(COALESCE(comments, 0), ?) WHERE id = ?",
                         (p["views"] or 0, p["likes"] or 0, p["comments"] or 0, by_code[code]))
            updated += 1
        else:
            conn.execute("INSERT INTO own_posts(id, date, month, type, caption, url, views, likes, comments, "
                         "followers_count, note, imported_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 1, 'automatisch', ?)",
                         (p["url"], p["posted_at"][:10], p["posted_at"][:7], "IG-reel" if p["views"] else "Instagram-post",
                          p["text"], p["url"], p["views"], p["likes"], p["comments"], now))
            by_code[code] = p["url"]
            new += 1
    return {"new": new, "updated": updated}
