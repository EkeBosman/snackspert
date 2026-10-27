"""Houdt de maandkosten onder het ingestelde budget.

Per ophaalronde: (resterend maandbudget) / (resterende rondes deze maand).
Wordt een ronde goedkoper dan gepland, dan is er de volgende keer meer ruimte;
wordt hij duurder, dan minder. Elke Apify-run krijgt bovendien een hard
bedragplafond mee, dus ook een fout in de planning kan het budget niet
overschrijden.
"""
from __future__ import annotations

import calendar
import math
from datetime import datetime, timedelta

from . import db

PLATFORMS = ("instagram", "tiktok", "facebook")


def month_start(now: datetime) -> datetime:
    return now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)


def month_end(now: datetime) -> datetime:
    days = calendar.monthrange(now.year, now.month)[1]
    return month_start(now) + timedelta(days=days)


def spent_usd(conn, kind: str, now: datetime | None = None) -> float:
    now = now or db.now()
    row = conn.execute("SELECT COALESCE(SUM(usd), 0) AS s FROM spend WHERE kind = ? AND at >= ?",
                       (kind, db.iso(month_start(now)))).fetchone()
    return float(row["s"])


def record(conn, kind: str, usd: float, platform: str | None = None, detail: str = "",
           correction: bool = False) -> int | None:
    """Leg kosten vast. Een correctie mag negatief zijn (eerder te hoog ingeschat)."""
    if usd == 0 or (usd < 0 and not correction):
        return None
    cur = conn.execute("INSERT INTO spend(at, kind, platform, usd, detail) VALUES (?, ?, ?, ?, ?)",
                       (db.iso(db.now()), kind, platform, usd, detail))
    return cur.lastrowid


def runs_left(settings: dict, now: datetime) -> int:
    hours = (month_end(now) - now).total_seconds() / 3600
    return max(1, math.ceil(hours / max(1, settings["interval_uren"])))


def plan(conn, settings: dict, now: datetime | None = None) -> dict:
    now = now or db.now()
    rate = settings["eur_per_usd"] or 0.92
    budget_usd = settings["maandbudget_eur"] / rate
    spent = spent_usd(conn, "apify", now)
    left = max(0.0, budget_usd - spent)
    n_runs = runs_left(settings, now)
    # Hooguit twee keer een normale ronde: stond de laptop vaak uit, dan stapelt het restbudget
    # zich anders op in de laatste rondes van de maand (tot tientallen dollars in één ronde).
    days = calendar.monthrange(now.year, now.month)[1]
    normal = budget_usd / max(1.0, days * 24 / max(1, settings["interval_uren"]))
    per_run = min(left / n_runs, 2 * normal)
    weights = smart_split(conn, settings)
    total_w = sum(weights.get(p, 0) for p in PLATFORMS) or 1
    per_platform = {}
    for p in PLATFORMS:
        usd = per_run * weights.get(p, 0) / total_w
        price = settings[f"prijs_{p}_per_1000"] or 1
        per_platform[p] = {"usd": round(usd, 4), "results": int(usd / price * 1000)}
    return {
        "budget_usd": round(budget_usd, 2),
        "spent_usd": round(spent, 2),
        "left_usd": round(left, 2),
        "runs_left": n_runs,
        "per_run_usd": round(per_run, 4),
        "platforms": per_platform,
    }


MIN_COST_USD = 2.0   # pas na een paar dollar per platform is 'per dollar' betrouwbaar


def efficiency(conn) -> dict[str, dict]:
    """Per platform: nuttige posts (nieuw, relevant, Nederlands) per uitgegeven dollar."""
    out = {}
    for r in conn.execute("SELECT platform, SUM(cost_usd) AS usd, SUM(useful_total) AS useful FROM sources "
                          "WHERE platform IN ('instagram', 'tiktok', 'facebook') GROUP BY platform"):
        usd = r["usd"] or 0.0
        out[r["platform"]] = {"usd": round(usd, 2), "useful": r["useful"] or 0,
                              "per_usd": round((r["useful"] or 0) / usd, 2) if usd >= MIN_COST_USD else None}
    return out


def smart_split(conn, settings: dict) -> dict[str, float]:
    """De ingestelde verdeling, bijgestuurd naar wat elk platform per dollar oplevert.

    Een platform dat twee keer zo veel nuttige posts per dollar oplevert als gemiddeld
    krijgt tot twee keer zijn aandeel; een slecht platform houdt minstens de helft,
    zodat het nog meetelt (en kan herstellen).
    """
    base = settings["verdeling"]
    if not settings.get("verdeling_automatisch", True):
        return dict(base)
    eff = {p: e["per_usd"] for p, e in efficiency(conn).items() if e["per_usd"] is not None and base.get(p, 0) > 0}
    if len(eff) < 2:
        return dict(base)
    mean = sum(eff.values()) / len(eff)
    if mean <= 0:
        return dict(base)
    return {p: round(w * (min(2.0, max(0.5, eff[p] / mean)) if p in eff else 1.0), 4) for p, w in base.items()}


def overview(conn, settings: dict) -> dict:
    now = db.now()
    p = plan(conn, settings, now)
    rate = settings["eur_per_usd"] or 0.92
    ai_spent = spent_usd(conn, "ai", now)
    days = calendar.monthrange(now.year, now.month)[1]
    elapsed_days = max(0.25, (now - month_start(now)).total_seconds() / 86400)
    # Google Maps en de supermarkten hebben geen platform: die vallen onder 'overig'.
    by_platform = {r["platform"] or "overig": r["s"] for r in conn.execute(
        "SELECT platform, SUM(usd) AS s FROM spend WHERE kind = 'apify' AND at >= ? GROUP BY platform",
        (db.iso(month_start(now)),))}
    useful = conn.execute(
        "SELECT COUNT(*) AS n FROM posts WHERE first_fetched >= ? AND demo = 0 AND platform != 'nieuws' "
        "AND relevance >= 0.35 AND nl_score >= 0.4", (db.iso(month_start(now)),)).fetchone()["n"]
    total_eur = (p["spent_usd"] + ai_spent) * rate
    return {
        "nuttige_posts": useful,
        "per_nuttige_post_eur": round(total_eur / useful, 4) if useful else None,
        "maand": now.strftime("%Y-%m"),
        "data_budget_eur": settings["maandbudget_eur"],
        "data_uitgegeven_eur": round(p["spent_usd"] * rate, 2),
        "data_per_platform_eur": {k: round((v or 0) * rate, 2) for k, v in by_platform.items()},
        "ai_budget_eur": settings["ai_maandbudget_eur"],
        "ai_uitgegeven_eur": round(ai_spent * rate, 2),
        "prognose_eur": round((p["spent_usd"] + ai_spent) * rate / elapsed_days * days, 2),
        "rondes_over": p["runs_left"],
        "per_ronde_eur": round(p["per_run_usd"] * rate, 2),
        "plan": p["platforms"],
        "verdeling": _shares(smart_split(conn, settings)),
        "verdeling_ingesteld": _shares(settings["verdeling"]),
        "rendement": efficiency(conn),
        # Wat Apify zelf meldt over je account (bijgewerkt bij elke ophaalronde).
        "apify_account": db.get_state(conn, "apify_account"),
    }


def _shares(weights: dict[str, float]) -> dict[str, int]:
    total = sum(weights.get(p, 0) for p in PLATFORMS) or 1
    return {p: round(100 * weights.get(p, 0) / total) for p in PLATFORMS}


def allocate(sources: list[dict], results: int, min_per: int, max_per: int,
             now: datetime | None = None) -> list[tuple[dict, int]]:
    """Verdeel een aantal resultaten over bronnen.

    Bronnen die veel relevants opleveren en lang niet zijn opgehaald gaan voor.
    Past niet alles in één ronde, dan komen de overige de volgende keer aan bod.
    """
    min_per = max(1, int(min_per or 1))
    max_per = max(min_per, int(max_per or min_per))
    if results < min_per or not sources:
        return []
    now = now or db.now()

    def score(s):
        yield_ = s["yield_score"] if s["yield_score"] is not None else 0.6
        if s["last_fetched"]:
            hours = (now - db.parse_iso(s["last_fetched"])).total_seconds() / 3600
        else:
            hours = 72
        return yield_ * (s["priority"] or 1) + min(hours, 96) / 48

    ranked = sorted(sources, key=score, reverse=True)
    n = min(len(ranked), results // min_per)
    per = max(min_per, min(max_per, results // max(1, n)))
    chosen = []
    remaining = results
    for s in ranked[:n]:
        take = min(per, remaining)
        if take < min_per:
            break
        chosen.append((s, take))
        remaining -= take
    return chosen
