"""Doorlichten van de live site.

Beantwoordt de openstaande vragen met wat er werkelijk in de database staat, in
plaats van met een aanname: staat show_in_rest aan, wat bewaart het image-veld,
welk post-ID zit er in location, en welke sleutels heeft het map-veld.
"""

from __future__ import annotations

import re

from .vocab import CATEGORIEEN, DIETEN
from .wpclient import WPClient, WPFout

GOED = "OK  "
LET_OP = "LET OP"
FOUT = "FOUT"


class Rapport:
    def __init__(self) -> None:
        self.regels: list[str] = []
        self.problemen = 0

    def kop(self, tekst: str) -> None:
        self.regels.append("")
        self.regels.append(tekst)
        self.regels.append("-" * len(tekst))

    def punt(self, status: str, tekst: str) -> None:
        self.regels.append(f"  {status:<6} {tekst}")
        if status == FOUT:
            self.problemen += 1

    def los(self, tekst: str = "") -> None:
        self.regels.append(f"         {tekst}" if tekst else "")

    def __str__(self) -> str:
        return "\n".join(self.regels)


def diagnose(client: WPClient) -> Rapport:
    r = Rapport()
    r.regels.append(f"Doorlichting van {client.i.basis_url}")

    r.kop("Verbinding en authenticatie")
    try:
        ik = client.wie_ben_ik()
    except WPFout as exc:
        r.punt(FOUT, f"Inloggen mislukt: {exc}")
        return r
    r.punt(GOED, f"Ingelogd als {ik.get('name')} ({ik.get('slug')}), rollen: {', '.join(ik.get('roles', []))}")
    if not ik.get("capabilities", {}).get("publish_posts"):
        r.punt(FOUT, "Dit account mag niet publiceren; kies een account met minstens de rol Auteur.")

    r.kop("Eigen endpoint")
    heeft_plugin = False
    try:
        heeft_plugin = client.heeft_endpoint()
    except WPFout as exc:
        r.punt(LET_OP, f"Kon de routelijst niet lezen: {exc}")
    if heeft_plugin:
        r.punt(GOED, "snackspert/v1 is geregistreerd; publiceren gaat via het eigen endpoint.")
    else:
        r.punt(LET_OP, "snackspert/v1 niet gevonden. Upload wp-plugin/snackspert-review-api.zip via wp-admin > Plugins.")

    _acf_via_rest(client, r)

    if heeft_plugin:
        _via_schema(client, r)
    else:
        r.kop("Openstaande punten")
        r.punt(
            LET_OP,
            "image, location en map zijn pas te controleren als het endpoint geinstalleerd is.",
        )

    r.kop("Uitkomst")
    r.punt(GOED if r.problemen == 0 else FOUT, f"{r.problemen} blokkerend(e) punt(en).")
    return r


def _acf_via_rest(client: WPClient, r: Rapport) -> None:
    """Openstaand punt 1: staat show_in_rest aan op de ACF-veldgroep?"""
    r.kop("ACF via de standaard REST API (show_in_rest)")
    try:
        item = client.eerste_restaurant()
    except WPFout as exc:
        r.punt(FOUT, f"/wp/v2/restaurant is niet leesbaar: {exc}")
        return
    if not item:
        r.punt(LET_OP, "Nog geen enkel restaurant gevonden om aan te toetsen.")
        return

    acf = item.get("acf")
    if isinstance(acf, dict) and acf:
        r.punt(GOED, f'show_in_rest staat AAN: /wp/v2/restaurant geeft een "acf"-blok met {len(acf)} veld(en).')
        r.los("De terugvaloptie --via=rest werkt dus ook.")
    else:
        r.punt(LET_OP, 'show_in_rest staat UIT: /wp/v2/restaurant geeft geen gevuld "acf"-blok.')
        r.los("Dat is geen blokkade zolang je via het eigen endpoint publiceert.")
        r.los("Wil je hem toch aan: ACF > Veldgroepen > Restaurant settings > Show in REST API.")


def _via_schema(client: WPClient, r: Rapport) -> None:
    try:
        schema = client.schema()
    except WPFout as exc:
        r.punt(FOUT, f"/snackspert/v1/schema gaf een fout: {exc}")
        return

    r.kop("Post types")
    for naam, gegevens in (schema.get("post_types") or {}).items():
        if gegevens.get("bestaat"):
            r.punt(GOED, f"{naam}: rest_base={gegevens.get('rest_base')}, {gegevens.get('aantal')} gepubliceerd")
        else:
            r.punt(FOUT, f"Post type {naam} bestaat niet op deze site.")

    r.kop("ACF-veldgroep")
    if not schema.get("acf_actief"):
        r.punt(FOUT, "ACF is niet actief; de reviewvelden kunnen niet geschreven worden.")
        return
    groep = schema.get("groep")
    if not groep:
        r.punt(FOUT, f"Veldgroep {schema.get('groep_key')} niet gevonden. Is de key veranderd?")
        return
    r.punt(GOED, f"\"{groep['titel']}\" gevonden (ACF {schema.get('acf_versie')}), show_in_rest={int(bool(groep['show_in_rest']))}")

    velden = schema.get("velden") or {}
    ontbrekend = [v for v in ("text", "category", "main_category", "image", "location", "map", "address") if v not in velden]
    if ontbrekend:
        r.punt(FOUT, f"Verwachte velden ontbreken: {', '.join(ontbrekend)}.")
    for naam, veld in velden.items():
        extra = f", return_format={veld['return_format']}" if veld.get("return_format") else ""
        meer = ", meervoudig" if veld.get("multiple") else ""
        r.punt(GOED, f"{naam}: {veld['type']} ({veld['key']}){extra}{meer}")

    _keuzelijsten(velden, r)
    _opslagvorm(schema, r)


def _keuzelijsten(velden: dict, r: Rapport) -> None:
    r.kop("Keuzelijsten")
    for veld, lokaal in (("category", CATEGORIEEN), ("main_category", CATEGORIEEN), ("diet", DIETEN)):
        keuzes = (velden.get(veld) or {}).get("choices")
        if not keuzes:
            r.punt(LET_OP, f"{veld}: geen keuzelijst gevonden in ACF.")
            continue
        alleen_site = [k for k in keuzes if k not in lokaal]
        alleen_lokaal = [k for k in lokaal if k not in keuzes]
        if not alleen_site and not alleen_lokaal:
            r.punt(GOED, f"{veld}: {len(keuzes)} waardes, gelijk aan publisher/vocab.py.")
        else:
            r.punt(LET_OP, f"{veld}: publisher/vocab.py loopt uit de pas.")
            if alleen_site:
                r.los(f"Alleen op de site: {', '.join(alleen_site)}")
            if alleen_lokaal:
                r.los(f"Alleen lokaal: {', '.join(alleen_lokaal)}")


def _opslagvorm(schema: dict, r: Rapport) -> None:
    """Openstaande punten 2, 3 en 4: hoe staan image, location en map er echt in?"""
    voorbeeld = schema.get("voorbeeld")
    r.kop("Opslagvorm volgens de nieuwste review")
    if not voorbeeld:
        r.punt(LET_OP, "Geen bestaande review gevonden om de opslagvorm aan af te lezen.")
        return
    r.los(f"Voorbeeld: {voorbeeld['titel']} ({voorbeeld['link']})")
    meta = voorbeeld.get("ruwe_meta") or {}

    beeld = meta.get("image")
    if isinstance(beeld, (int, str)) and str(beeld).isdigit():
        r.punt(GOED, f"image bevat attachment-ID {beeld}: eerst uploaden naar /wp/v2/media, dan dat ID wegschrijven.")
    elif beeld:
        r.punt(LET_OP, f"image bevat geen kaal ID maar {beeld!r}; controleer dit voordat je publiceert.")
    else:
        r.punt(LET_OP, "image is leeg bij dit voorbeeld.")

    locatie = meta.get("location")
    if isinstance(locatie, (int, str)) and str(locatie).isdigit():
        r.punt(GOED, f"location bevat post-ID {locatie} (aantal locatie-pagina's: {schema.get('aantal_locaties')}).")
    elif locatie:
        r.punt(LET_OP, f"location bevat {locatie!r}; verwacht was een enkel post-ID.")
    else:
        r.punt(LET_OP, "location is leeg bij dit voorbeeld; koppeling is dus niet verplicht.")

    kaart = meta.get("map")
    if isinstance(kaart, dict):
        r.punt(GOED, f"map is een array met sleutels: {', '.join(sorted(kaart))}.")
        ontbreekt = [s for s in ("lat", "lng", "address") if s not in kaart]
        if ontbreekt:
            r.los(f"Let op: {', '.join(ontbreekt)} ontbreekt in dit voorbeeld.")
    elif kaart:
        r.punt(LET_OP, f"map is opgeslagen als {type(kaart).__name__}: {str(kaart)[:120]}")
    else:
        r.punt(LET_OP, "map is leeg bij dit voorbeeld.")

    _sterrenpositie(str(meta.get("text") or ""), r)


def _sterrenpositie(tekst: str, r: Rapport) -> None:
    """Waar staat de beoordeling in de tekst: boven of onder?"""
    kaal = re.sub(r"<[^>]+>", " ", tekst).strip()
    if not kaal:
        return
    match = re.search(r"[⭐★]", kaal)
    if not match:
        r.punt(LET_OP, "In de nieuwste review staan geen sterren in de tekst; zet sterren_positie desnoods op geen.")
        return
    positie = "boven" if match.start() < len(kaal) / 2 else "onder"
    r.punt(GOED, f'De beoordeling staat in de nieuwste review {positie} in de tekst; zet sterren_positie op "{positie}".')
