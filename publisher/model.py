"""Het datamodel van een review plus de omzetting naar een API-payload."""

from __future__ import annotations

import html
import math
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .vocab import CATEGORIEEN, DIETEN

# Waarde voor "foto" als je de foto zelf in wp-admin toevoegt.
HANDMATIG = "zelf"


class ReviewFout(Exception):
    """Aanlevering klopt niet; de boodschap is bedoeld voor Eke, niet voor een log."""


@dataclass
class Review:
    naam: str = ""
    tekst: str = ""
    sterren: float | None = None
    sterren_positie: str = "onder"  # "onder", "boven" of "geen"
    category: list[str] = field(default_factory=list)
    main_category: str = ""
    diet: list[str] = field(default_factory=list)
    adres: str = ""
    plaats: str = ""
    lat: float | None = None
    lng: float | None = None
    zoom: int = 15
    foto: str = ""          # lokaal pad, of "zelf" als je hem handmatig toevoegt
    foto_url: str = ""      # of een URL die de server zelf ophaalt
    foto_alt: str = ""
    slug: str = ""
    maak_locatie_aan: bool = False
    ook_post_content: bool = False
    bron: Path | None = None  # het bestand waar dit uit komt, voor foutmeldingen

    # ---------------------------------------------------------------- controle

    def controleer(self) -> list[str]:
        """Harde fouten die publiceren blokkeren. Huisstijl zit in editorial.py."""
        fouten: list[str] = []

        if not self.naam.strip():
            fouten.append('"naam" ontbreekt (dit wordt de titel van de pagina).')
        if not self.tekst.strip():
            fouten.append("De reviewtekst is leeg (alles onder de tweede --- regel).")

        if self.sterren is not None:
            if not 0.5 <= self.sterren <= 5:
                fouten.append(f"sterren moet tussen 0.5 en 5 liggen, niet {self.sterren}.")
            elif (self.sterren * 2) % 1 != 0:
                fouten.append(f"sterren gaat per halve ster; {self.sterren} kan niet.")

        if self.sterren_positie not in ("onder", "boven", "geen"):
            fouten.append('sterren_positie moet "onder", "boven" of "geen" zijn.')

        for waarde in self.category:
            if waarde not in CATEGORIEEN:
                fouten.append(f'"{waarde}" staat niet in de categorielijst: {", ".join(CATEGORIEEN)}.')
        if self.main_category and self.main_category not in CATEGORIEEN:
            fouten.append(
                f'main_category "{self.main_category}" staat niet in de categorielijst: {", ".join(CATEGORIEEN)}.'
            )
        for waarde in self.diet:
            if waarde not in DIETEN:
                fouten.append(f'"{waarde}" is geen geldig dieet. Kies uit: {", ".join(DIETEN)}.')

        if (self.lat is None) != (self.lng is None):
            fouten.append("Geef lat en lng samen op, of geen van beide.")
        if self.lat is not None and not -90 <= self.lat <= 90:
            fouten.append(f"lat {self.lat} ligt buiten -90..90.")
        if self.lng is not None and not -180 <= self.lng <= 180:
            fouten.append(f"lng {self.lng} ligt buiten -180..180.")

        if self.foto and self.foto_url:
            fouten.append('Geef "foto" of "foto_url", niet allebei.')
        if self.foto and not self.foto_handmatig:
            pad = self.foto_pad()
            if pad is None or not pad.is_file():
                fouten.append(f'Foto "{self.foto}" bestaat niet.')

        return fouten

    @property
    def foto_handmatig(self) -> bool:
        """Voeg jij de foto zelf toe in wp-admin? Dan uploadt de publisher niets."""
        return self.foto.strip().lower() == HANDMATIG

    def foto_pad(self) -> Path | None:
        """Fotopad, relatief opgelost vanaf het reviewbestand zelf."""
        if not self.foto or self.foto_handmatig:
            return None
        pad = Path(self.foto).expanduser()
        if not pad.is_absolute() and self.bron is not None:
            pad = (self.bron.parent / pad).resolve()
        return pad

    # ----------------------------------------------------------------- tekst

    @property
    def sterren_tekst(self) -> str:
        """4.5 wordt sterrensterrensterrensterren + een half teken."""
        if self.sterren is None:
            return ""
        vol = math.floor(self.sterren)
        half = self.sterren - vol >= 0.5
        return "⭐" * vol + ("½" if half else "")

    def volledige_tekst(self) -> str:
        """De reviewtekst met de sterrenregel erbij, zoals hij live komt te staan.

        Staan er al sterren in de tekst, dan blijft die staan: de website leest de
        beoordeling uit de tekst, en twee sterrenregels zou het gemiddelde
        vertekenen.
        """
        tekst = self.tekst.strip()
        if self.sterren is None or self.sterren_positie == "geen":
            return tekst
        if re.search(r"[⭐★]", tekst):
            return tekst
        if self.sterren_positie == "boven":
            return f"{self.sterren_tekst}\n\n{tekst}"
        return f"{tekst}\n\n{self.sterren_tekst}"

    def als_html(self) -> str:
        """Alinea's naar HTML; het ACF-veld "text" is een wysiwyg-veld.

        Een lege regel begint een nieuwe alinea; een enkele regelovergang telt
        als spatie, zodat je je tekst in de editor mag afbreken waar je wilt.
        De review is platte tekst, dus < en & worden ge-escaped. Wie een link of
        vetgedrukt woord wil, zet dat achteraf in de wysiwyg-editor.
        """
        blokken = [b.strip() for b in re.split(r"\n\s*\n", self.volledige_tekst()) if b.strip()]
        return "\n".join(
            "<p>" + html.escape(" ".join(b.split()), quote=False) + "</p>" for b in blokken
        )

    # --------------------------------------------------------------- payload

    def payload(self, *, bijwerken: bool = False, dry_run: bool = False) -> dict[str, Any]:
        """Body voor POST /wp-json/snackspert/v1/reviews.

        De foto zit er nog niet in: die wordt eerst geupload en als image_id
        toegevoegd, of als image_base64 achteraf ingevoegd.
        """
        body: dict[str, Any] = {
            "naam": self.naam.strip(),
            "tekst": self.als_html(),
            "tekst_formaat": "html",
            "category": self.category,
            "main_category": self.main_category,
            "diet": self.diet,
            "maak_locatie_aan": self.maak_locatie_aan,
            "ook_post_content": self.ook_post_content,
        }
        if self.slug:
            body["slug"] = self.slug
        if self.adres:
            body["adres"] = self.adres.strip()
        if self.plaats:
            body["plaats"] = self.plaats.strip()
        if self.lat is not None and self.lng is not None:
            body["lat"] = self.lat
            body["lng"] = self.lng
            body["zoom"] = self.zoom
        if self.foto_url:
            body["image_url"] = self.foto_url
        if self.foto_alt:
            body["image_alt"] = self.foto_alt
        if bijwerken:
            body["bijwerken"] = True
        if dry_run:
            body["dry_run"] = True
        return body
