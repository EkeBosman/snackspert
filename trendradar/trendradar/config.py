"""Instellingen: geheime sleutels uit `.env`, de rest uit de database.

Sleutels (API-tokens) staan alleen in `.env` en worden nooit naar de browser
gestuurd. Alles wat je in de interface aanpast (budget, interval, prijzen)
staat in de tabel `settings`, zodat het een herstart overleeft.
"""
from __future__ import annotations

import json
import os
from pathlib import Path

PROJECT_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = Path(os.environ.get("TRENDRADAR_DATA", PROJECT_DIR / "data"))
DB_PATH = DATA_DIR / "trendradar.db"


def load_env(path: Path = PROJECT_DIR / ".env") -> None:
    """Minimale .env-lezer, zodat er geen extra package nodig is."""
    if not path.exists():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        value = value.strip().strip('"').strip("'")
        os.environ.setdefault(key.strip(), value)


def secret(name: str) -> str:
    return os.environ.get(name, "").strip()


SECRET_NAMES = ("APIFY_TOKEN", "META_ACCESS_TOKEN", "ANTHROPIC_API_KEY")


def redact(text: str) -> str:
    """Haal sleutels uit foutmeldingen voordat ze in het logboek of de interface komen."""
    for name in SECRET_NAMES:
        value = secret(name)
        if len(value) >= 3:
            text = text.replace(value, "***")
    return text


# Standaardwaarden voor alles wat in de interface instelbaar is.
# Prijzen zijn in dollars per 1000 resultaten, zoals Apify ze rekent.
# Controleer ze op de "Pricing"-tab van de actor; de werkelijke kosten per run
# worden achteraf uit Apify gelezen, deze prijzen dienen alleen voor de planning.
DEFAULTS: dict = {
    "interval_uren": 6,
    "maandbudget_eur": 60.0,          # alleen voor data (Apify); AI apart
    "ai_maandbudget_eur": 10.0,
    "eur_per_usd": 0.92,
    "prijs_instagram_per_1000": 2.30,
    "prijs_tiktok_per_1000": 1.70,
    "prijs_facebook_per_1000": 3.00,
    # Hoe het Apify-budget per run over de platforms wordt verdeeld.
    # Instagram krijgt minder omdat de gratis Meta-API een deel afdekt.
    "verdeling": {"instagram": 0.30, "tiktok": 0.45, "facebook": 0.25},
    "verdeling_automatisch": True,    # bijsturen naar nuttige posts per dollar (zie budget.smart_split)
    "min_per_bron": 10,
    "max_per_bron": 40,
    "auto_toevoegen": True,
    "max_nieuwe_bronnen_per_run": 6,
    "max_actieve_bronnen_per_platform": 60,
    "ai_model": "claude-opus-5-5",
    "ai_effort": "low",
    "ai_aan": True,
    "supermarkt_aan": True,
    "supermarkt_interval_uren": 12,
    "alleen_nieuwe_posts": True,      # datumfilter: niet betalen voor posts die we al hebben
    "herhaalmeting_per_ronde": 15,    # snelste posts per platform opnieuw meten
    "nieuws_aan": True,
    "thuisbasis": "Amsterdam",        # vanaf hier rekent de tool routes (retour)
    "extra_rss": [],
    "backup_map": "",                 # leeg: Google Drive-map 'Snackspert Trendradar', anders data/backups
    "backup_dagen": 7,
    "bewaar_maanden": 6,
    "eigen_instagram": "",            # je eigen account: wekelijks je nieuwe posts en cijfers ophalen
    "eigen_posts_dagen": 7,
    # Nieuwe zaken via Google Maps: elke week een paar steden, op rij af.
    "maps_aan": True,
    "maps_zoektermen": ["snackbar", "foodtruck", "streetfood", "frituur"],
    "maps_steden": ["Amsterdam", "Rotterdam", "Utrecht", "Den Haag", "Eindhoven", "Groningen", "Arnhem",
                    "Nijmegen", "Tilburg", "Breda", "Zwolle", "Haarlem", "Leiden", "Almere"],
    "maps_steden_per_week": 2,
    "maps_per_zoekopdracht": 30,
    "prijs_maps_per_1000": 4.00,              # oudere posts opruimen (bewaarde en beoordeelde blijven); 0 = nooit
}


def ai_prices(model: str) -> tuple[float, float]:
    """Dollar per miljoen input/output-tokens, voor de kostenteller."""
    table = {
        "claude-opus-5-5": (4.00, 20.00),
        "claude-sonnet-5-5": (2.00, 10.00),
        "claude-haiku-5-5": (0.10, 0.50),
    }
    return table.get(model, (4.00, 20.00))


def dumps(value) -> str:
    return json.dumps(value, ensure_ascii=False)
