import json

import pytest
import requests

from publisher import wpclient
from publisher.wpclient import Instellingen, WPFout, _fout_uit_respons


def test_env_wordt_gelezen(tmp_path, monkeypatch):
    for sleutel in ("SNACKSPERT_URL", "SNACKSPERT_USER", "SNACKSPERT_APP_PASSWORD"):
        monkeypatch.delenv(sleutel, raising=False)
    env = tmp_path / ".env"
    env.write_text(
        '# commentaar\nSNACKSPERT_URL=https://snackspert.nl/\n'
        'SNACKSPERT_USER=Admin_Eke\nSNACKSPERT_APP_PASSWORD="abcd efgh ijkl"\n',
        encoding="utf-8",
    )
    instellingen = Instellingen.uit_omgeving(env)
    assert instellingen.basis_url == "https://snackspert.nl"
    assert instellingen.gebruiker == "Admin_Eke"
    assert instellingen.wachtwoord == "abcd efgh ijkl"


def test_omgeving_wint_van_env_bestand(tmp_path, monkeypatch):
    env = tmp_path / ".env"
    env.write_text("SNACKSPERT_USER=uit_bestand\nSNACKSPERT_APP_PASSWORD=x\n", encoding="utf-8")
    monkeypatch.setenv("SNACKSPERT_USER", "uit_omgeving")
    assert Instellingen.uit_omgeving(env).gebruiker == "uit_omgeving"


def test_ontbrekende_gegevens_melden_welke(tmp_path, monkeypatch):
    for sleutel in ("SNACKSPERT_USER", "SNACKSPERT_APP_PASSWORD"):
        monkeypatch.delenv(sleutel, raising=False)
    with pytest.raises(WPFout, match="SNACKSPERT_USER en SNACKSPERT_APP_PASSWORD"):
        Instellingen.uit_omgeving(tmp_path / "bestaat-niet")


def _respons(status, payload=None, tekst=""):
    resp = requests.Response()
    resp.status_code = status
    resp.reason = "Fout"
    resp._content = (json.dumps(payload) if payload is not None else tekst).encode()
    resp.headers["Content-Type"] = "application/json" if payload is not None else "text/html"
    return resp


def test_401_wijst_naar_wordfence():
    fout = _fout_uit_respons(_respons(401, {"code": "incorrect_password", "message": "Onjuist."}))
    assert fout.status == 401
    assert "Wordfence" in str(fout)


def test_404_zonder_route_wijst_naar_de_plugin():
    fout = _fout_uit_respons(_respons(404, {"code": "rest_no_route", "message": "Geen route."}))
    assert "snackspert-review-api.zip" in str(fout)


def test_409_wijst_naar_bijwerken():
    fout = _fout_uit_respons(_respons(409, {"code": "snackspert_bestaat_al", "message": "Bestaat al."}))
    assert "--bijwerken" in str(fout)


def test_html_antwoord_wordt_afgekapt_meegegeven():
    fout = _fout_uit_respons(_respons(503, tekst="<html>Service Unavailable</html>"))
    assert "Service Unavailable" in str(fout)


def test_upload_weigert_niet_afbeeldingen(tmp_path, monkeypatch):
    client = wpclient.WPClient(Instellingen("https://x", "u", "w"))
    pad = tmp_path / "review.txt"
    pad.write_text("geen foto", encoding="utf-8")
    with pytest.raises(WPFout, match="geen afbeelding"):
        client.upload_media(pad)


def test_netwerkfout_wordt_opnieuw_geprobeerd(monkeypatch):
    client = wpclient.WPClient(Instellingen("https://x", "u", "w"), pogingen=3)
    pogingen = {"n": 0}

    def mislukt(*args, **kwargs):
        pogingen["n"] += 1
        raise requests.ConnectionError("time-out")

    monkeypatch.setattr(client.sessie, "request", mislukt)
    monkeypatch.setattr(wpclient.time, "sleep", lambda _: None)
    with pytest.raises(WPFout, match="Geen verbinding"):
        client.wie_ben_ik()
    assert pogingen["n"] == 3


def test_foutstatus_wordt_niet_herhaald(monkeypatch):
    """Een 400 komt niet vanzelf goed, en een herhaalde POST zou dubbel publiceren."""
    client = wpclient.WPClient(Instellingen("https://x", "u", "w"), pogingen=3)
    pogingen = {"n": 0}

    def antwoord(*args, **kwargs):
        pogingen["n"] += 1
        return _respons(400, {"code": "x", "message": "Ongeldig."})

    monkeypatch.setattr(client.sessie, "request", antwoord)
    with pytest.raises(WPFout):
        client.publiceer({})
    assert pogingen["n"] == 1


def test_zoek_locatie_matcht_alleen_exact(monkeypatch):
    """Bijna goed is fout: liever geen koppeling dan de verkeerde plaats."""
    client = wpclient.WPClient(Instellingen("https://x", "u", "w"))
    treffers = [
        {"id": 1, "title": {"rendered": "Neederhorst den Berg"}},
        {"id": 7, "title": {"rendered": "Neede"}},
    ]
    monkeypatch.setattr(client, "_verzoek", lambda *a, **k: treffers)
    assert client.zoek_locatie("neede") == 7
    assert client.zoek_locatie("Need") is None
