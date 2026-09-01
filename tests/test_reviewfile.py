import textwrap

import pytest

from publisher import reviewfile
from publisher.model import ReviewFout

KOP = """\
---
naam: Cafetaria De Hoek
sterren: 4.5
hoofdcategorie: kroket
categorie: [kroket, snackbar]
plaats: Neede
lat: 52.1401
lng: 6.6152
---

De kroket kraakt.
"""


def schrijf(tmp_path, inhoud, naam="review.md"):
    pad = tmp_path / naam
    pad.write_text(textwrap.dedent(inhoud), encoding="utf-8")
    return pad


def test_leest_kop_en_tekst(tmp_path):
    review = reviewfile.lees(schrijf(tmp_path, KOP))
    assert review.naam == "Cafetaria De Hoek"
    assert review.sterren == 4.5
    assert review.main_category == "kroket"
    assert review.category == ["kroket", "snackbar"]
    assert review.plaats == "Neede"
    assert review.lat == 52.1401
    assert review.tekst == "De kroket kraakt."
    assert review.controleer() == []


def test_engelse_sleutels_mogen_ook(tmp_path):
    review = reviewfile.lees(
        schrijf(tmp_path, """\
        ---
        naam: Test
        main_category: pizza
        category: pizza, italiaans
        address: Straat 1
        ---
        Tekst.
        """)
    )
    assert review.main_category == "pizza"
    assert review.category == ["pizza", "italiaans"]
    assert review.adres == "Straat 1"


def test_streepjes_in_de_tekst_blijven_staan(tmp_path):
    """De --- scheiding geldt alleen voor de kop, niet voor de tekst eronder."""
    review = reviewfile.lees(
        schrijf(tmp_path, """\
        ---
        naam: Test
        ---
        Eerste alinea.

        ---

        Tweede alinea.
        """)
    )
    assert "Tweede alinea." in review.tekst


def test_onbekende_sleutel_wordt_gemeld(tmp_path):
    with pytest.raises(ReviewFout, match="stad"):
        reviewfile.lees(schrijf(tmp_path, "---\nnaam: Test\nstad: Neede\n---\nTekst.\n"))


def test_ontbrekende_afsluiting(tmp_path):
    with pytest.raises(ReviewFout, match="afsluitende"):
        reviewfile.lees(schrijf(tmp_path, "---\nnaam: Test\nTekst zonder afsluiting.\n"))


def test_geen_kop(tmp_path):
    with pytest.raises(ReviewFout, match="--- regel"):
        reviewfile.lees(schrijf(tmp_path, "Zomaar een tekst.\n"))


def test_kapotte_yaml(tmp_path):
    with pytest.raises(ReviewFout, match="klopt niet"):
        reviewfile.lees(schrijf(tmp_path, "---\nnaam: [onafgemaakt\n---\nTekst.\n"))


def test_getalveld_met_tekst(tmp_path):
    with pytest.raises(ReviewFout, match="moet een getal zijn"):
        reviewfile.lees(schrijf(tmp_path, "---\nnaam: Test\nsterren: vier\n---\nTekst.\n"))


def test_sjabloon_is_leesbaar(tmp_path):
    pad = tmp_path / "nieuw.md"
    pad.write_text(reviewfile.sjabloon("De Kroketterij"), encoding="utf-8")
    review = reviewfile.lees(pad)
    assert review.naam == "De Kroketterij"
    assert review.sterren is None
    assert review.category == []
