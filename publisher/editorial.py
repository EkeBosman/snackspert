"""Huisstijlcontrole op een review.

Dit is geen smaakpolitie: het vangt de dingen af die je bij dagelijks publiceren
een keer over het hoofd ziet en die daarna live staan. Alles wat inhoudelijk is
(geen verzonnen anekdotes, echte ankers) kan een script niet weten; daar geeft
het hooguit een seintje bij.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from .model import Review
from .vocab import TOEGESTANE_SYMBOLEN, ZOETE_WOORDEN

FOUT = "fout"
WAARSCHUWING = "waarschuwing"

# Emoji en pictogrammen. De sterren van de beoordeling vallen hier ook onder en
# worden er daarna weer uit gefilterd via TOEGESTANE_SYMBOLEN.
EMOJI = re.compile(
    "["
    "\U0001F000-\U0001FAFF"  # emoji, vlaggen, symbolen
    "\u2600-\u27BF"          # weer-, dingbat- en pictogramblok
    "\u2B00-\u2BFF"          # pijlen en sterren (\u2B50 is de gewone ster)
    "\uFE00-\uFE0F"          # variatieselectors die emoji kleuren
    "\u2122\u2139\u3030\u303D"
    "]"
)

EM_STREEPJE = re.compile("—")
EN_STREEPJE = re.compile("–")
CITAAT = re.compile("[\"“„][^\"“”„]{12,}[\"”]")
LOSSE_FRIET = re.compile(r"\b(?<!friet)(friet|patat)(en|je|jes)?\b(?!\s*patat)", re.IGNORECASE)

MIN_TEKENS = 180


@dataclass
class Bevinding:
    niveau: str
    regel: str
    bericht: str
    regelnummer: int | None = None

    def __str__(self) -> str:
        plek = f" (regel {self.regelnummer})" if self.regelnummer else ""
        return f"[{self.niveau}] {self.regel}{plek}: {self.bericht}"


def _regelnummer(tekst: str, index: int) -> int:
    return tekst.count("\n", 0, index) + 1


def controleer(review: Review, *, streng: bool = False) -> list[Bevinding]:
    """Alle huisstijlbevindingen. `streng` maakt van elke waarschuwing een fout."""
    bevindingen: list[Bevinding] = []
    tekst = review.tekst
    alles = f"{review.naam}\n{tekst}"

    for match in EM_STREEPJE.finditer(alles):
        bevindingen.append(
            Bevinding(
                FOUT,
                "em-streepje",
                "Liggend streepje (—) gevonden. Gebruik een komma, een punt of haakjes.",
                _regelnummer(alles, match.start()),
            )
        )

    for match in EN_STREEPJE.finditer(alles):
        bevindingen.append(
            Bevinding(
                WAARSCHUWING,
                "kort-streepje",
                "Halflang streepje (–) gevonden. Bedoelde je een gewoon koppelteken?",
                _regelnummer(alles, match.start()),
            )
        )

    gezien: set[str] = set()
    for match in EMOJI.finditer(alles):
        teken = match.group()
        if teken in TOEGESTANE_SYMBOLEN or teken in gezien:
            continue
        gezien.add(teken)
        bevindingen.append(
            Bevinding(
                FOUT,
                "emoji",
                f"Emoji {teken!r} gevonden. Alleen de sterren van de beoordeling mogen.",
                _regelnummer(alles, match.start()),
            )
        )

    for woord in ZOETE_WOORDEN:
        match = re.search(rf"\b{re.escape(woord)}\w*\b", tekst, re.IGNORECASE)
        if match:
            bevindingen.append(
                Bevinding(
                    WAARSCHUWING,
                    "zoet",
                    f'"{match.group()}" klinkt zoet. Snackspert doet hartig; controleer of dit klopt.',
                    _regelnummer(tekst, match.start()),
                )
            )

    match = LOSSE_FRIET.search(tekst)
    if match:
        bevindingen.append(
            Bevinding(
                WAARSCHUWING,
                "frietpatat",
                f'"{match.group()}" staat er los. De huisterm is "frietpatat".',
                _regelnummer(tekst, match.start()),
            )
        )

    aantal_citaten = len(CITAAT.findall(tekst))
    if aantal_citaten:
        bevindingen.append(
            Bevinding(
                WAARSCHUWING,
                "citaat",
                f"{aantal_citaten} citaat(en) tussen aanhalingstekens. Controleer of dit echt gezegd is.",
            )
        )

    if len(tekst.strip()) < MIN_TEKENS:
        bevindingen.append(
            Bevinding(
                WAARSCHUWING,
                "kort",
                f"De review is {len(tekst.strip())} tekens; onder de {MIN_TEKENS} leest het als een bijschrift.",
            )
        )

    if not review.main_category:
        bevindingen.append(
            Bevinding(WAARSCHUWING, "hoofdcategorie", "Geen hoofdcategorie: geen gerelateerde zaken op de detailpagina.")
        )
    elif review.category and review.main_category not in review.category:
        bevindingen.append(
            Bevinding(
                WAARSCHUWING,
                "hoofdcategorie",
                f'Hoofdcategorie "{review.main_category}" staat niet in de categorielijst van dit item.',
            )
        )

    if not review.plaats:
        bevindingen.append(Bevinding(WAARSCHUWING, "plaats", "Geen plaats: het item hangt aan geen enkele plaatspagina."))
    if not review.foto and not review.foto_url:
        bevindingen.append(Bevinding(WAARSCHUWING, "foto", "Geen foto: het item komt zonder hoofdfoto online."))
    if review.lat is None or review.lng is None:
        bevindingen.append(Bevinding(WAARSCHUWING, "kaart", "Geen lat/lng: het item verschijnt niet op de kaart."))
    if review.sterren is None:
        bevindingen.append(Bevinding(WAARSCHUWING, "sterren", "Geen beoordeling opgegeven."))

    if streng:
        bevindingen = [
            Bevinding(FOUT, b.regel, b.bericht, b.regelnummer) if b.niveau == WAARSCHUWING else b
            for b in bevindingen
        ]
    return bevindingen


def fouten(bevindingen: list[Bevinding]) -> list[Bevinding]:
    return [b for b in bevindingen if b.niveau == FOUT]
