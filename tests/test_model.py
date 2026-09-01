from pathlib import Path

from publisher.model import Review


def basis(**kwargs) -> Review:
    gegevens = dict(naam="Test", tekst="Een tekst.", main_category="kroket")
    gegevens.update(kwargs)
    return Review(**gegevens)


def test_lege_naam_en_tekst_zijn_fout():
    fouten = Review().controleer()
    assert any("naam" in f for f in fouten)
    assert any("leeg" in f for f in fouten)


def test_kwart_ster_mag_niet():
    assert any("halve ster" in f for f in basis(sterren=4.25).controleer())
    assert basis(sterren=4.5).controleer() == []


def test_sterren_buiten_bereik():
    assert any("tussen 0.5 en 5" in f for f in basis(sterren=6).controleer())


def test_onbekende_categorie():
    assert any("categorielijst" in f for f in basis(category=["sushi"]).controleer())


def test_onbekend_dieet():
    assert any("dieet" in f for f in basis(diet=["Halal"]).controleer())


def test_lat_zonder_lng():
    assert any("samen" in f for f in basis(lat=52.1).controleer())


def test_coordinaten_buiten_bereik():
    assert any("-90..90" in f for f in basis(lat=99.0, lng=6.0).controleer())


def test_foto_en_foto_url_samen():
    review = basis(foto="a.jpg", foto_url="https://voorbeeld.nl/a.jpg")
    assert any("niet allebei" in f for f in review.controleer())


def test_foto_pad_is_relatief_aan_het_bestand(tmp_path):
    (tmp_path / "fotos").mkdir()
    (tmp_path / "fotos" / "a.jpg").write_bytes(b"x")
    review = basis(foto="fotos/a.jpg", bron=tmp_path / "review.md")
    assert review.foto_pad() == (tmp_path / "fotos" / "a.jpg").resolve()
    assert review.controleer() == []


def test_ontbrekende_foto_is_fout(tmp_path):
    review = basis(foto="weg.jpg", bron=tmp_path / "review.md")
    assert any("bestaat niet" in f for f in review.controleer())


def test_sterrentekst():
    assert basis(sterren=4.5).sterren_tekst == "⭐⭐⭐⭐½"
    assert basis(sterren=3).sterren_tekst == "⭐⭐⭐"
    assert basis().sterren_tekst == ""


def test_sterren_onder_en_boven():
    assert basis(sterren=3, sterren_positie="onder").volledige_tekst().endswith("⭐⭐⭐")
    assert basis(sterren=3, sterren_positie="boven").volledige_tekst().startswith("⭐⭐⭐")
    assert "⭐" not in basis(sterren=3, sterren_positie="geen").volledige_tekst()


def test_bestaande_sterren_worden_niet_verdubbeld():
    """De site leest de score uit de tekst; twee sterrenregels vertekenen dat."""
    review = basis(tekst="Lekker. ⭐⭐⭐⭐", sterren=4)
    assert review.volledige_tekst().count("⭐") == 4


def test_html_maakt_alineas():
    html = basis(tekst="Eerste.\n\nTweede.").als_html()
    assert html == "<p>Eerste.</p>\n<p>Tweede.</p>"


def test_afbreken_binnen_een_alinea_wordt_een_spatie():
    """Zachte regelafbreking in de editor mag geen regelovergang op de site worden."""
    assert basis(tekst="Regel een\nRegel twee").als_html() == "<p>Regel een Regel twee</p>"


def test_payload_laat_lege_velden_weg():
    payload = basis().payload()
    assert "lat" not in payload and "slug" not in payload and "image_url" not in payload
    assert payload["tekst_formaat"] == "html"


def test_payload_neemt_kaartgegevens_mee():
    payload = basis(lat=52.1, lng=6.6, zoom=17, adres="Straat 1").payload()
    assert (payload["lat"], payload["lng"], payload["zoom"]) == (52.1, 6.6, 17)
    assert payload["adres"] == "Straat 1"


def test_payload_vlaggen():
    payload = basis().payload(bijwerken=True, dry_run=True)
    assert payload["bijwerken"] is True and payload["dry_run"] is True


def test_html_escapet_bijzondere_tekens():
    """De review is platte tekst; < en & mogen de wysiwyg niet in de war schoppen."""
    html = basis(tekst="Fish & Chips <het bakje>").als_html()
    assert html == "<p>Fish &amp; Chips &lt;het bakje&gt;</p>"
