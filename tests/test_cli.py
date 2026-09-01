import textwrap

import pytest

from publisher import cli
from publisher.wpclient import WPFout

REVIEW = """\
---
naam: Cafetaria De Hoek
sterren: 4
hoofdcategorie: kroket
categorie: [kroket, snackbar]
plaats: Neede
adres: |
  Marktstraat 12
  7161 CT Neede
lat: 52.1401
lng: 6.6152
---

De kroket kraakt zoals een dun laagje rijp op een plas in november. De ragout
blijft binnen de korst, wat bij deze prijs eerder uitzondering dan regel is.
De mayonaise komt uit een emmer en niet uit een zakje.
"""


class StubClient:
    """Vervangt de HTTP-client; legt vast wat er verstuurd zou worden."""

    def __init__(self, *, endpoint=True, media_fout=None):
        self.endpoint = endpoint
        self.media_fout = media_fout
        self.payload = None
        self.velden = None
        self.uploads = []

    basis_url = "https://snackspert.nl"

    def heeft_endpoint(self):
        return self.endpoint

    def upload_media(self, pad, **kwargs):
        if self.media_fout:
            raise WPFout("geweigerd", status=self.media_fout)
        self.uploads.append(pad)
        return {"id": 4242, "source_url": "https://snackspert.nl/foto.jpg"}

    def publiceer(self, payload):
        self.payload = payload
        if payload.get("dry_run"):
            return {"dry_run": True, "zou_doen": "aanmaken", "slug": "cafetaria-de-hoek"}
        return {
            "id": 1,
            "slug": "cafetaria-de-hoek",
            "link": "https://snackspert.nl/restaurant/cafetaria-de-hoek/",
            "locatie": {"id": 7, "naam": "Neede", "aangemaakt": False},
            "waarschuwingen": [],
        }

    def publiceer_via_wp_v2(self, payload, velden):
        self.payload, self.velden = payload, velden
        return {"id": 2, "link": "https://snackspert.nl/restaurant/x/", "acf": {"text": velden["text"]}}

    def zoek_locatie(self, plaats):
        return 7 if plaats == "Neede" else None


@pytest.fixture
def bestand(tmp_path):
    pad = tmp_path / "review.md"
    pad.write_text(REVIEW, encoding="utf-8")
    return pad


@pytest.fixture
def stub(monkeypatch):
    houder = {}

    def maak(**kwargs):
        client = StubClient(**kwargs)
        houder["client"] = client
        monkeypatch.setattr(cli, "_client", lambda args: client)
        return client

    return maak


def test_publiceert_via_het_eigen_endpoint(bestand, stub, capsys):
    client = stub()
    assert cli.main(["publiceer", str(bestand)]) == 0
    assert client.payload["naam"] == "Cafetaria De Hoek"
    assert client.payload["main_category"] == "kroket"
    assert client.payload["category"] == ["kroket", "snackbar"]
    assert (client.payload["lat"], client.payload["lng"]) == (52.1401, 6.6152)
    assert client.payload["tekst"].startswith("<p>")
    assert client.payload["tekst"].rstrip().endswith("<p>⭐⭐⭐⭐</p>")
    assert "restaurant/cafetaria-de-hoek" in capsys.readouterr().out


def test_huisstijlfout_blokkeert_publiceren(tmp_path, stub, capsys):
    pad = tmp_path / "review.md"
    pad.write_text(REVIEW + "\nEcht waar — heel lekker.\n", encoding="utf-8")
    client = stub()
    assert cli.main(["publiceer", str(pad)]) == 1
    assert client.payload is None
    assert "em-streepje" in capsys.readouterr().out


def test_huisstijl_kan_overruled_worden(tmp_path, stub):
    pad = tmp_path / "review.md"
    pad.write_text(REVIEW + "\nEcht waar — heel lekker.\n", encoding="utf-8")
    client = stub()
    assert cli.main(["publiceer", str(pad), "--negeer-huisstijl"]) == 0
    assert client.payload is not None


def test_foto_gaat_eerst_naar_de_mediabibliotheek(tmp_path, stub):
    (tmp_path / "a.jpg").write_bytes(b"\xff\xd8\xff")
    pad = tmp_path / "review.md"
    pad.write_text(REVIEW.replace("lat: 52.1401", "foto: a.jpg\nlat: 52.1401"), encoding="utf-8")
    client = stub()
    assert cli.main(["publiceer", str(pad)]) == 0
    assert client.uploads and client.payload["image_id"] == 4242
    assert "image_base64" not in client.payload


def test_geblokkeerde_media_route_valt_terug_op_base64(tmp_path, stub):
    (tmp_path / "a.jpg").write_bytes(b"\xff\xd8\xff")
    pad = tmp_path / "review.md"
    pad.write_text(REVIEW.replace("lat: 52.1401", "foto: a.jpg\nlat: 52.1401"), encoding="utf-8")
    client = stub(media_fout=403)
    assert cli.main(["publiceer", str(pad)]) == 0
    assert client.payload["image_base64"] and client.payload["image_filename"] == "a.jpg"
    assert "image_id" not in client.payload


def test_onverwachte_uploadfout_wordt_niet_weggemoffeld(tmp_path, stub, capsys):
    (tmp_path / "a.jpg").write_bytes(b"\xff\xd8\xff")
    pad = tmp_path / "review.md"
    pad.write_text(REVIEW.replace("lat: 52.1401", "foto: a.jpg\nlat: 52.1401"), encoding="utf-8")
    stub(media_fout=500)
    assert cli.main(["publiceer", str(pad)]) == 1
    assert "mislukt" in capsys.readouterr().err


def test_dry_run_uploadt_niets(bestand, stub):
    client = stub()
    assert cli.main(["publiceer", str(bestand), "--dry-run"]) == 0
    assert client.payload["dry_run"] is True
    assert not client.uploads


def test_terugval_op_de_standaard_rest_route(bestand, stub):
    client = stub(endpoint=False)
    assert cli.main(["publiceer", str(bestand)]) == 0
    assert client.velden["main_category"] == "kroket"
    assert client.velden["location"] == 7
    assert client.velden["map"]["lat"] == 52.1401
    assert client.velden["map"]["address"] == "Marktstraat 12 7161 CT Neede"


def test_rest_route_kan_geen_base64_foto_plaatsen(tmp_path, stub, capsys):
    (tmp_path / "a.jpg").write_bytes(b"\xff\xd8\xff")
    pad = tmp_path / "review.md"
    pad.write_text(REVIEW.replace("lat: 52.1401", "foto: a.jpg\nlat: 52.1401"), encoding="utf-8")
    stub(endpoint=False, media_fout=403)
    assert cli.main(["publiceer", str(pad)]) == 1
    assert "media" in capsys.readouterr().err


def test_nieuw_maakt_een_leesbaar_bestand(tmp_path, capsys):
    assert cli.main(["nieuw", "De Kroketterij", "--map", str(tmp_path), "--datum", "2026-09-01"]) == 0
    pad = tmp_path / "2026-09-01-de-kroketterij.md"
    assert pad.is_file()
    assert cli.main(["controleer", str(pad)]) == 0


def test_nieuw_overschrijft_niet_zomaar(tmp_path, capsys):
    argumenten = ["nieuw", "De Kroketterij", "--map", str(tmp_path), "--datum", "2026-09-01"]
    assert cli.main(argumenten) == 0
    assert cli.main(argumenten) == 1
    assert cli.main(argumenten + ["--overschrijf"]) == 0


def test_controleer_meldt_een_kapot_bestand(tmp_path, capsys):
    pad = tmp_path / "kapot.md"
    pad.write_text("geen kop\n", encoding="utf-8")
    assert cli.main(["controleer", str(pad)]) == 1


def test_dry_run_op_de_rest_route_verstuurt_niets(bestand, stub, capsys):
    """De standaard route kent geen proefdraaien, dus dan posten we helemaal niet."""
    client = stub(endpoint=False)
    assert cli.main(["publiceer", str(bestand), "--dry-run"]) == 0
    assert client.payload is None and client.velden is None
    assert "niets verstuurd" in capsys.readouterr().out


def test_zonder_foto_wijst_hij_de_weg_naar_wp_admin(bestand, stub, capsys):
    stub()
    assert cli.main(["publiceer", str(bestand)]) == 0
    uit = capsys.readouterr().out
    assert "wp-admin/post.php?post=1&action=edit" in uit
    assert "uitgelichte afbeelding" in uit


def test_foto_zelf_uploadt_niets(tmp_path, stub, capsys):
    """foto: zelf betekent dat Eke hem handmatig toevoegt; geen upload, geen waarschuwing."""
    pad = tmp_path / "review.md"
    pad.write_text(REVIEW.replace("lat: 52.1401", "foto: zelf\nlat: 52.1401"), encoding="utf-8")
    client = stub()
    assert cli.main(["publiceer", str(pad)]) == 0
    assert not client.uploads
    assert "image_id" not in client.payload and "image_base64" not in client.payload
    uit = capsys.readouterr().out
    assert "Geen foto" not in uit
    assert "foto nog toevoegen" in uit
