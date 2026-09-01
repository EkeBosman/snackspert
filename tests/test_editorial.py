from publisher.editorial import FOUT, WAARSCHUWING, controleer, fouten
from publisher.model import Review

LANG = (
    "De kroket kraakt zoals een dun laagje rijp op een plas in november. "
    "De ragout blijft binnen de korst, wat bij deze prijs eerder uitzondering "
    "dan regel is. De mayonaise komt uit een emmer en niet uit een zakje, "
    "en daar koop ik veel voor."
)


def review(tekst=LANG, **kwargs):
    gegevens = dict(
        naam="Test",
        tekst=tekst,
        main_category="kroket",
        category=["kroket"],
        plaats="Neede",
        foto_url="https://voorbeeld.nl/a.jpg",
        lat=52.1,
        lng=6.6,
        sterren=4,
    )
    gegevens.update(kwargs)
    return Review(**gegevens)


def regels(bevindingen):
    return {b.regel for b in bevindingen}


def test_volledige_review_is_schoon():
    assert controleer(review()) == []


def test_em_streepje_is_fout():
    bevindingen = controleer(review(LANG + " Echt waar — heel lekker."))
    assert "em-streepje" in regels(bevindingen)
    assert fouten(bevindingen)


def test_kort_streepje_is_waarschuwing():
    bevindingen = [b for b in controleer(review(LANG + " Open 12–14 uur.")) if b.regel == "kort-streepje"]
    assert bevindingen and bevindingen[0].niveau == WAARSCHUWING


def test_emoji_is_fout():
    bevindingen = [b for b in controleer(review(LANG + " Zeker weten 🔥")) if b.regel == "emoji"]
    assert bevindingen and bevindingen[0].niveau == FOUT


def test_sterren_zijn_geen_emoji():
    assert "emoji" not in regels(controleer(review(LANG + "\n\n⭐⭐⭐⭐")))


def test_emoji_wordt_een_keer_per_teken_gemeld():
    bevindingen = [b for b in controleer(review(LANG + " 🔥🔥🔥")) if b.regel == "emoji"]
    assert len(bevindingen) == 1


def test_emoji_in_de_naam():
    assert "emoji" in regels(controleer(review(naam="De Hoek 🍟")))


def test_zoet_woord_waarschuwt():
    assert "zoet" in regels(controleer(review(LANG + " Daarna een stuk taart.")))


def test_zoet_geen_valse_treffer_op_prijs():
    """"prijs" bevat "ijs" maar is geen dessert."""
    assert "zoet" not in regels(controleer(review()))


def test_losse_patat_waarschuwt():
    assert "frietpatat" in regels(controleer(review(LANG + " De patat was zacht.")))


def test_frietpatat_zelf_niet():
    assert "frietpatat" not in regels(controleer(review(LANG + " De frietpatat was zacht.")))


def test_citaat_waarschuwt():
    tekst = LANG + ' De baas zei "wij bakken hier al veertig jaar hetzelfde".'
    assert "citaat" in regels(controleer(review(tekst)))


def test_te_korte_review():
    assert "kort" in regels(controleer(review("Prima kroket.")))


def test_ontbrekende_gegevens_waarschuwen():
    kaal = Review(naam="Test", tekst=LANG)
    assert {"hoofdcategorie", "plaats", "foto", "kaart", "sterren"} <= regels(controleer(kaal))


def test_hoofdcategorie_buiten_de_categorielijst():
    bevindingen = controleer(review(main_category="pizza", category=["kroket"]))
    assert "hoofdcategorie" in regels(bevindingen)


def test_streng_maakt_van_alles_een_fout():
    bevindingen = controleer(review(LANG + " Daarna een stuk taart."), streng=True)
    assert all(b.niveau == FOUT for b in bevindingen)
