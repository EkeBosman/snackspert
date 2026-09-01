"""Opdrachtregel voor het dagelijkse publiceren.

    python -m publisher nieuw "De Kroketterij"
    python -m publisher controleer reviews/2026-09-01-de-kroketterij.md
    python -m publisher publiceer reviews/2026-09-01-de-kroketterij.md
    python -m publisher doctor
"""

from __future__ import annotations

import argparse
import datetime as dt
import re
import sys
from pathlib import Path

from . import reviewfile
from .doctor import diagnose
from .editorial import controleer as huisstijl, fouten as alleen_fouten
from .model import Review, ReviewFout
from .wpclient import Instellingen, WPClient, WPFout, als_base64

REVIEWMAP = Path("reviews")


def _client(args) -> WPClient:
    return WPClient(Instellingen.uit_omgeving(args.env))


def _slug(naam: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", naam.lower().strip()).strip("-")
    return slug or "review"


# ------------------------------------------------------------------- nieuw

def cmd_nieuw(args) -> int:
    datum = args.datum or dt.date.today().isoformat()
    map_ = Path(args.map)
    map_.mkdir(parents=True, exist_ok=True)
    pad = map_ / f"{datum}-{_slug(args.naam)}.md"
    if pad.exists() and not args.overschrijf:
        print(f"{pad} bestaat al. Gebruik --overschrijf als je hem opnieuw wilt aanmaken.", file=sys.stderr)
        return 1
    pad.write_text(reviewfile.sjabloon(args.naam), encoding="utf-8")
    print(f"Aangemaakt: {pad}")
    print("Vul de kop in, schrijf de review eronder, en controleer daarna met:")
    print(f"  python -m publisher controleer {pad}")
    return 0


# -------------------------------------------------------------- controleer

def _lees_en_controleer(pad: Path, *, streng: bool) -> tuple[Review | None, int]:
    """Leest een reviewbestand en meldt alles wat er mis mee is."""
    try:
        review = reviewfile.lees(pad)
    except ReviewFout as exc:
        print(f"{pad}: {exc}", file=sys.stderr)
        return None, 1

    harde = review.controleer()
    stijl = huisstijl(review, streng=streng)

    print(f"{pad}")
    for melding in harde:
        print(f"  [fout] {melding}")
    for bevinding in stijl:
        print(f"  {bevinding}")
    if not harde and not stijl:
        print("  niets aan te merken")

    blokkerend = len(harde) + len(alleen_fouten(stijl))
    return review, (1 if blokkerend else 0)


def cmd_controleer(args) -> int:
    code = 0
    for pad in args.bestanden:
        _, resultaat = _lees_en_controleer(Path(pad), streng=args.streng)
        code |= resultaat
    return code


# ---------------------------------------------------------------- publiceer

def cmd_publiceer(args) -> int:
    code = 0
    client = None
    for pad in args.bestanden:
        review, resultaat = _lees_en_controleer(Path(pad), streng=False)
        if resultaat and not args.negeer_huisstijl:
            print("  niet gepubliceerd: los eerst de fouten hierboven op.", file=sys.stderr)
            code = 1
            continue
        if review is None:
            code = 1
            continue
        if client is None:
            client = _client(args)
        try:
            code |= _publiceer_een(client, review, args)
        except WPFout as exc:
            print(f"  publiceren mislukt: {exc}", file=sys.stderr)
            code = 1
    return code


def _publiceer_een(client: WPClient, review: Review, args) -> int:
    payload = review.payload(bijwerken=args.bijwerken, dry_run=args.dry_run)

    via = args.via
    if via == "auto":
        via = "endpoint" if client.heeft_endpoint() else "rest"
        print(f"  route: {via}")

    attachment = None
    if not args.dry_run:
        attachment = _zet_foto_klaar(client, review, payload)

    if args.dry_run and via == "rest":
        # De standaard route kent geen proefdraaien; alles wat we hier posten gaat
        # meteen live. De controle hierboven is dan het enige wat een dry run doet.
        print("  proefdraai: de route rest kan niet proefdraaien, er is niets verstuurd.")
        return 0

    if via == "endpoint":
        antwoord = client.publiceer(payload)
    else:
        antwoord = _publiceer_via_rest(client, review, payload, attachment, args)

    if args.dry_run:
        print(f"  proefdraai: zou {antwoord.get('zou_doen', 'aanmaken')} als \"{antwoord.get('slug')}\"")
        for waarschuwing in antwoord.get("waarschuwingen") or []:
            print(f"  let op: {waarschuwing}")
        return 0

    print(f"  live: {antwoord.get('link')}")
    if antwoord.get("locatie"):
        locatie = antwoord["locatie"]
        nieuw = " (nieuw aangemaakt)" if locatie.get("aangemaakt") else ""
        print(f"  plaats: {locatie.get('naam')} #{locatie.get('id')}{nieuw}")
    for waarschuwing in antwoord.get("waarschuwingen") or []:
        print(f"  let op: {waarschuwing}")
    return 0


def _zet_foto_klaar(client: WPClient, review: Review, payload: dict):
    """Foto naar de mediabibliotheek; het ACF image-veld wil een attachment-ID.

    Lukt uploaden niet doordat /wp/v2/media dichtstaat, dan gaat het bestand als
    base64 mee met het eigen endpoint, dat de upload dan server-side doet.
    """
    pad = review.foto_pad()
    if pad is None:
        return None
    try:
        attachment = client.upload_media(pad, titel=review.naam, alt=review.foto_alt or review.naam)
    except WPFout as exc:
        if exc.status not in (401, 403, 404, 405):
            raise
        print(f"  /wp/v2/media weigerde de upload ({exc.status}); foto gaat mee met het verzoek zelf.")
        payload["image_base64"] = als_base64(pad)
        payload["image_filename"] = pad.name
        return None
    payload["image_id"] = attachment["id"]
    print(f"  foto geupload: attachment #{attachment['id']}")
    return attachment


def _publiceer_via_rest(client: WPClient, review: Review, payload: dict, attachment, args) -> dict:
    """Terugvaloptie zonder mu-plugin. Vereist show_in_rest op de veldgroep."""
    if payload.get("image_base64"):
        raise WPFout("Zonder het eigen endpoint moet /wp/v2/media beschikbaar zijn om de foto te kunnen plaatsen.")

    velden: dict = {
        "text": payload["tekst"],
        "category": review.category,
        "main_category": review.main_category,
        "diet": review.diet,
    }
    if review.adres:
        velden["address"] = review.adres.strip()
    if payload.get("image_id"):
        velden["image"] = payload["image_id"]
    if review.lat is not None and review.lng is not None:
        velden["map"] = {
            "address": re.sub(r"\s+", " ", review.adres).strip(),
            "lat": review.lat,
            "lng": review.lng,
            "zoom": review.zoom,
        }
    if review.plaats:
        locatie_id = client.zoek_locatie(review.plaats)
        if locatie_id:
            velden["location"] = locatie_id
        else:
            print(f'  let op: geen locatie-pagina gevonden voor "{review.plaats}"; koppeling overgeslagen.')

    antwoord = client.publiceer_via_wp_v2(payload, velden)
    if not (antwoord.get("acf") or {}).get("text"):
        print(
            "  let op: WordPress gaf geen gevulde acf-velden terug. Zet "
            '"Show in REST API" aan op de veldgroep, of installeer het eigen endpoint, '
            "en controleer de pagina.",
            file=sys.stderr,
        )
    return antwoord


# ------------------------------------------------------------------ overig

def cmd_doctor(args) -> int:
    rapport = diagnose(_client(args))
    print(rapport)
    return 1 if rapport.problemen else 0


def cmd_locaties(args) -> int:
    client = _client(args)
    for locatie in client.locaties(args.zoek):
        print(f"{locatie['id']:>6}  {locatie['naam']}")
    return 0


def bouw_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="publisher", description="Zaakjes-reviews live zetten op snackspert.nl.")
    parser.add_argument("--env", default=".env", help="bestand met de inloggegevens (standaard: .env)")
    sub = parser.add_subparsers(dest="commando", required=True)

    p = sub.add_parser("nieuw", help="maak een leeg reviewbestand aan")
    p.add_argument("naam", help="de zaaknaam")
    p.add_argument("--datum", help="YYYY-MM-DD, standaard vandaag")
    p.add_argument("--map", default=str(REVIEWMAP), help="waar het bestand komt te staan")
    p.add_argument("--overschrijf", action="store_true")
    p.set_defaults(func=cmd_nieuw)

    p = sub.add_parser("controleer", help="controleer zonder te publiceren")
    p.add_argument("bestanden", nargs="+")
    p.add_argument("--streng", action="store_true", help="behandel waarschuwingen als fouten")
    p.set_defaults(func=cmd_controleer)

    p = sub.add_parser("publiceer", help="zet de review direct live")
    p.add_argument("bestanden", nargs="+")
    p.add_argument("--dry-run", action="store_true", help="alles controleren, niets wegschrijven")
    p.add_argument("--bijwerken", action="store_true", help="een bestaande pagina met dezelfde slug overschrijven")
    p.add_argument("--negeer-huisstijl", action="store_true", help="publiceer ondanks huisstijlfouten")
    p.add_argument("--via", choices=["auto", "endpoint", "rest"], default="auto")
    p.set_defaults(func=cmd_publiceer)

    p = sub.add_parser("doctor", help="controleer de site en beantwoord de openstaande punten")
    p.set_defaults(func=cmd_doctor)

    p = sub.add_parser("locaties", help="toon de bestaande plaatspagina's")
    p.add_argument("zoek", nargs="?", default="")
    p.set_defaults(func=cmd_locaties)

    return parser


def main(argv: list[str] | None = None) -> int:
    args = bouw_parser().parse_args(argv)
    try:
        return args.func(args)
    except WPFout as exc:
        print(f"Fout: {exc}", file=sys.stderr)
        return 1
    except ReviewFout as exc:
        print(f"Fout: {exc}", file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        return 130


if __name__ == "__main__":
    raise SystemExit(main())
