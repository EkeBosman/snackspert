"""Lezen en schrijven van reviewbestanden.

Een review is een tekstbestand met een YAML-kop tussen twee `---` regels en
daaronder de reviewtekst. Dat formaat is met opzet saai: het is met elke editor
te maken, het is te versiehouden in git, en er gaat niets stuk als de laptop
halverwege dichtklapt.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

import yaml

from .model import Review, ReviewFout
from .vocab import CATEGORIEEN, DIETEN

# Nederlandse sleutel => veld op Review. De ACF-namen mogen ook, zodat een
# payload uit een ander script zonder vertaalslag werkt.
SLEUTELS: dict[str, str] = {
    "naam": "naam",
    "titel": "naam",
    "sterren": "sterren",
    "sterren_positie": "sterren_positie",
    "categorie": "category",
    "category": "category",
    "hoofdcategorie": "main_category",
    "main_category": "main_category",
    "dieet": "diet",
    "diet": "diet",
    "adres": "adres",
    "address": "adres",
    "plaats": "plaats",
    "lat": "lat",
    "lng": "lng",
    "zoom": "zoom",
    "foto": "foto",
    "image": "foto",
    "foto_url": "foto_url",
    "image_url": "foto_url",
    "foto_alt": "foto_alt",
    "image_alt": "foto_alt",
    "slug": "slug",
    "maak_locatie_aan": "maak_locatie_aan",
    "ook_post_content": "ook_post_content",
}

LIJSTVELDEN = {"category", "diet"}
GETALVELDEN = {"sterren": float, "lat": float, "lng": float, "zoom": int}
JANEEVELDEN = {"maak_locatie_aan", "ook_post_content"}

SCHEIDING = re.compile(r"^---\s*$", re.MULTILINE)


def split_frontmatter(inhoud: str) -> tuple[str, str]:
    """Splitst de YAML-kop van de tekst eronder."""
    if not inhoud.lstrip().startswith("---"):
        raise ReviewFout(
            "Het bestand begint niet met een --- regel. Een reviewbestand heeft een "
            "YAML-kop tussen twee --- regels, met daaronder de reviewtekst."
        )
    inhoud = inhoud.lstrip()
    delen = SCHEIDING.split(inhoud, maxsplit=2)
    # delen[0] is leeg (voor de eerste ---), delen[1] is de kop, delen[2] de tekst.
    if len(delen) < 3:
        raise ReviewFout("De afsluitende --- regel onder de YAML-kop ontbreekt.")
    return delen[1], delen[2]


def lees(pad: str | Path) -> Review:
    pad = Path(pad)
    try:
        inhoud = pad.read_text(encoding="utf-8")
    except FileNotFoundError:
        raise ReviewFout(f"Bestand niet gevonden: {pad}") from None
    except UnicodeDecodeError:
        raise ReviewFout(f"{pad} is geen UTF-8 tekstbestand.") from None

    kop, tekst = split_frontmatter(inhoud)
    try:
        meta = yaml.safe_load(kop) or {}
    except yaml.YAMLError as exc:
        raise ReviewFout(f"De YAML-kop van {pad.name} klopt niet: {exc}") from None
    if not isinstance(meta, dict):
        raise ReviewFout(f"De YAML-kop van {pad.name} moet een lijst met sleutels zijn.")

    review = Review(bron=pad.resolve(), tekst=tekst.strip())
    onbekend: list[str] = []

    for sleutel, waarde in meta.items():
        naam = str(sleutel).strip().lower()
        veld = SLEUTELS.get(naam)
        if veld is None:
            onbekend.append(str(sleutel))
            continue
        setattr(review, veld, _normaliseer(veld, waarde, pad))

    if onbekend:
        raise ReviewFout(
            f"Onbekende sleutel(s) in {pad.name}: {', '.join(onbekend)}. "
            f"Toegestaan: {', '.join(sorted(set(SLEUTELS)))}."
        )

    return review


def _normaliseer(veld: str, waarde: Any, pad: Path) -> Any:
    if waarde is None:
        return [] if veld in LIJSTVELDEN else ("" if veld not in GETALVELDEN else None)

    if veld in LIJSTVELDEN:
        if isinstance(waarde, str):
            waarde = [d.strip() for d in waarde.split(",")]
        if not isinstance(waarde, list):
            raise ReviewFout(f'"{veld}" in {pad.name} moet een lijst zijn.')
        return [str(d).strip() for d in waarde if str(d).strip()]

    if veld in GETALVELDEN:
        try:
            return GETALVELDEN[veld](waarde)
        except (TypeError, ValueError):
            raise ReviewFout(f'"{veld}" in {pad.name} moet een getal zijn, niet "{waarde}".') from None

    if veld in JANEEVELDEN:
        if isinstance(waarde, bool):
            return waarde
        return str(waarde).strip().lower() in ("true", "ja", "yes", "1")

    return str(waarde).strip()


SJABLOON = """---
naam: {naam}
sterren:            # halve sterren mogen: 3.5, 4, 4.5
hoofdcategorie:     # een uit: {categorieen}
categorie: []       # nul of meer uit dezelfde lijst
dieet: []           # leeg laten, of {dieten}
plaats:             # bestaande plaatspagina, bv. Neede
adres: |
  Straatnaam 1
  1234 AB Plaatsnaam
lat:
lng:
foto:               # pad naar de foto, relatief aan dit bestand
foto_alt:
---

Schrijf hier de review. Losse spreektaal, humor via onverwachte vergelijkingen,
alleen echte ankers uit je eigen bezoek. Geen liggende streepjes, geen emoji
buiten de sterren, en frietpatat heet frietpatat.
"""


def sjabloon(naam: str) -> str:
    return SJABLOON.format(
        naam=naam,
        categorieen=", ".join(CATEGORIEEN),
        dieten=" / ".join(DIETEN),
    )
