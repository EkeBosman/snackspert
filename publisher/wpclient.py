"""HTTP-client voor snackspert.nl.

Authenticatie gaat via een WordPress Application Password (Basic auth over
HTTPS). Het wachtwoord staat nooit in de code of in een reviewbestand; het komt
uit de omgeving of uit een .env die niet in git zit.
"""

from __future__ import annotations

import base64
import mimetypes
import os
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import requests
from requests.auth import HTTPBasicAuth

NAMESPACE = "snackspert/v1"
NETWERKFOUTEN = (requests.ConnectionError, requests.Timeout)


class WPFout(Exception):
    """Een antwoord van WordPress dat we niet als succes kunnen tellen."""

    def __init__(self, bericht: str, *, status: int | None = None, code: str = "", data: Any = None):
        super().__init__(bericht)
        self.status = status
        self.code = code
        self.data = data


@dataclass
class Instellingen:
    basis_url: str
    gebruiker: str
    wachtwoord: str
    timeout: int = 60

    @classmethod
    def uit_omgeving(cls, env_bestand: str | Path = ".env") -> "Instellingen":
        _laad_env(Path(env_bestand))
        url = os.environ.get("SNACKSPERT_URL", "https://snackspert.nl").rstrip("/")
        gebruiker = os.environ.get("SNACKSPERT_USER", "")
        wachtwoord = os.environ.get("SNACKSPERT_APP_PASSWORD", "")
        ontbreekt = [
            naam
            for naam, waarde in (("SNACKSPERT_USER", gebruiker), ("SNACKSPERT_APP_PASSWORD", wachtwoord))
            if not waarde
        ]
        if ontbreekt:
            raise WPFout(
                f"{' en '.join(ontbreekt)} niet ingesteld. Zet ze in .env of in je omgeving; "
                "zie docs/PUBLICEREN.md."
            )
        return cls(basis_url=url, gebruiker=gebruiker, wachtwoord=wachtwoord)


def _laad_env(pad: Path) -> None:
    """Minimale .env-lezer. Bestaande omgevingsvariabelen winnen."""
    if not pad.is_file():
        return
    for regel in pad.read_text(encoding="utf-8").splitlines():
        regel = regel.strip()
        if not regel or regel.startswith("#") or "=" not in regel:
            continue
        sleutel, _, waarde = regel.partition("=")
        sleutel = sleutel.strip()
        waarde = waarde.strip().strip("'\"")
        os.environ.setdefault(sleutel, waarde)


class WPClient:
    def __init__(self, instellingen: Instellingen, *, pogingen: int = 4):
        self.i = instellingen
        self.pogingen = pogingen
        self.sessie = requests.Session()
        self.sessie.auth = HTTPBasicAuth(instellingen.gebruiker, instellingen.wachtwoord)
        self.sessie.headers.update({"User-Agent": "snackspert-publisher/1.0", "Accept": "application/json"})

    # ------------------------------------------------------------- basis

    @property
    def basis_url(self) -> str:
        return self.i.basis_url

    def _url(self, pad: str) -> str:
        return f"{self.i.basis_url}/wp-json/{pad.lstrip('/')}"

    def _verzoek(self, methode: str, pad: str, **kwargs) -> Any:
        """Doet het verzoek en probeert netwerkfouten opnieuw met oplopende wachttijd.

        Een HTTP-foutstatus wordt niet herhaald: die komt niet vanzelf goed, en
        bij POST zou een herhaling een dubbele publicatie kunnen opleveren.
        """
        kwargs.setdefault("timeout", self.i.timeout)
        laatste: Exception | None = None

        for poging in range(self.pogingen):
            try:
                resp = self.sessie.request(methode, self._url(pad), **kwargs)
                break
            except NETWERKFOUTEN as exc:
                laatste = exc
                if poging == self.pogingen - 1:
                    raise WPFout(f"Geen verbinding met {self.i.basis_url}: {exc}") from exc
                time.sleep(2 ** (poging + 1))
        else:  # pragma: no cover - onbereikbaar, de lus breekt of gooit
            raise WPFout(str(laatste))

        if resp.status_code >= 400:
            raise _fout_uit_respons(resp)
        if not resp.content:
            return None
        try:
            return resp.json()
        except ValueError:
            raise WPFout(
                f"Onverwacht antwoord van {pad} (status {resp.status_code}, geen JSON). "
                "Staat er een beveiligingsplugin voor?",
                status=resp.status_code,
            ) from None

    # ---------------------------------------------------------- endpoints

    def wie_ben_ik(self) -> dict:
        return self._verzoek("GET", "wp/v2/users/me?context=edit")

    def schema(self) -> dict:
        return self._verzoek("GET", f"{NAMESPACE}/schema")

    def locaties(self, zoek: str = "") -> list[dict]:
        pad = f"{NAMESPACE}/locaties"
        if zoek:
            pad += f"?zoek={requests.utils.quote(zoek)}"
        return self._verzoek("GET", pad)

    def heeft_endpoint(self) -> bool:
        """Staat de eigen plugin geinstalleerd?"""
        routes = self._verzoek("GET", "") or {}
        return any(str(r).startswith(f"/{NAMESPACE}") for r in (routes.get("routes") or {}))

    def upload_media(self, pad: Path, *, titel: str = "", alt: str = "") -> dict:
        """Zet een foto in de mediabibliotheek en geeft het attachment terug.

        Het ACF image-veld bewaart een attachment-ID, geen URL; daarom moet de
        foto altijd eerst hier langs.
        """
        mime = mimetypes.guess_type(pad.name)[0] or "application/octet-stream"
        if not mime.startswith("image/"):
            raise WPFout(f"{pad.name} is geen afbeelding (gedetecteerd type: {mime}).")

        headers = {
            "Content-Disposition": f'attachment; filename="{pad.name}"',
            "Content-Type": mime,
        }
        attachment = self._verzoek("POST", "wp/v2/media", data=pad.read_bytes(), headers=headers)

        velden = {}
        if titel:
            velden["title"] = titel
        if alt:
            velden["alt_text"] = alt
        if velden:
            attachment = self._verzoek("POST", f"wp/v2/media/{attachment['id']}", json=velden)
        return attachment

    def publiceer(self, payload: dict) -> dict:
        return self._verzoek("POST", f"{NAMESPACE}/reviews", json=payload)

    def publiceer_via_wp_v2(self, payload: dict, velden: dict[str, Any]) -> dict:
        """Terugvaloptie zonder de eigen plugin, via de standaard route.

        Werkt alleen als de ACF-veldgroep "Show in REST API" aan heeft staan;
        anders slikt WordPress de acf-sleutel zonder er iets mee te doen.
        """
        body = {
            "title": payload["naam"],
            "status": "publish",
            "content": payload["tekst"] if payload.get("ook_post_content") else "",
            "acf": velden,
        }
        if payload.get("slug"):
            body["slug"] = payload["slug"]
        if velden.get("image"):
            body["featured_media"] = velden["image"]
        return self._verzoek("POST", "wp/v2/restaurant", json=body)

    def zoek_locatie(self, plaats: str) -> int | None:
        """Post-ID van een plaatspagina via de standaard route, op exacte titel."""
        items = self._verzoek("GET", f"wp/v2/locatie?search={requests.utils.quote(plaats)}&per_page=20")
        for item in items or []:
            titel = (item.get("title") or {}).get("rendered", "")
            if titel.strip().lower() == plaats.strip().lower():
                return item["id"]
        return None

    def lees_restaurant(self, post_id: int) -> dict:
        return self._verzoek("GET", f"wp/v2/restaurant/{post_id}?context=edit")

    def eerste_restaurant(self) -> dict | None:
        items = self._verzoek("GET", "wp/v2/restaurant?per_page=1&orderby=date&order=desc")
        return items[0] if items else None


def _fout_uit_respons(resp: requests.Response) -> WPFout:
    code, bericht, data = "", resp.reason or "", None
    try:
        payload = resp.json()
        code = payload.get("code", "") or ""
        bericht = payload.get("message", bericht) or bericht
        data = payload.get("data")
    except ValueError:
        fragment = resp.text.strip()[:200]
        if fragment:
            bericht = f"{bericht}: {fragment}"

    hint = _hint(resp.status_code, code)
    if hint:
        bericht = f"{bericht} {hint}"
    return WPFout(bericht, status=resp.status_code, code=code, data=data)


def _hint(status: int, code: str) -> str:
    if status == 401:
        return (
            "Controleer SNACKSPERT_USER en SNACKSPERT_APP_PASSWORD. Staat "
            '"Disable WordPress application passwords" in Wordfence weer aan?'
        )
    if status == 403:
        return "Het account mag dit niet, of Wordfence blokkeert het verzoek."
    if status == 404 and code == "rest_no_route":
        return "Het endpoint bestaat niet; is snackspert-review-api.zip geinstalleerd en geactiveerd?"
    if status == 409:
        return "Gebruik --bijwerken om de bestaande pagina te overschrijven."
    if status >= 500:
        return "Serverfout; probeer het zo nog eens en kijk anders in de foutlog van de host."
    return ""


def als_base64(pad: Path) -> str:
    return base64.b64encode(pad.read_bytes()).decode("ascii")
