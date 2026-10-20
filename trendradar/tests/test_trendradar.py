"""Tests: draai met  python -m pytest  in de map trendradar/."""
from __future__ import annotations

import os
import tempfile
from datetime import timedelta

import pytest

os.environ["TRENDRADAR_DATA"] = tempfile.mkdtemp()

from trendradar import budget, classify, config, db, discovery, snackspert, trends  # noqa: E402
from trendradar.collector import store_posts  # noqa: E402
from trendradar.sources import apify, news  # noqa: E402


@pytest.fixture()
def conn(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "DATA_DIR", tmp_path)
    monkeypatch.setattr(config, "DB_PATH", tmp_path / "t.db")
    db.init()
    c = db.connect()
    yield c
    c.close()


def post(i, text, hours_ago=1, platform="instagram", author=None, **kw):
    return {"id": f"{platform}:{i}", "platform": platform, "author": author or f"maker{i}",
            "text": text, "posted_at": db.iso(db.now() - timedelta(hours=hours_ago)),
            "likes": kw.get("likes", 10), "comments": 1, "shares": 0, "views": 0, **kw}


# --- indelen ---------------------------------------------------------------

def test_relevant_dutch_snack_post():
    c = classify.classify_rules({"text": "Beste frikandel speciaal van Rotterdam, echt lekker! #snackbar #eten010",
                                 "platform": "instagram"})
    assert c["relevance"] > 0.6
    assert c["nl_score"] >= 0.5
    assert "Friet & frituur" in c["categories"]
    assert c["city"] == "Rotterdam"


def test_irrelevant_post_scores_low():
    c = classify.classify_rules({"text": "Great sunset today, love this city #instagood", "platform": "instagram"})
    assert c["relevance"] < 0.2
    assert c["nl_score"] < 0.4


def test_new_supermarket_product():
    c = classify.classify_rules({"text": "Nieuw bij Albert Heijn: chips met kapsalonsmaak, smaaktest!",
                                 "platform": "tiktok"})
    assert "Albert Heijn" in c["brands"]
    assert "Supermarkt & nieuwe producten" in c["categories"]
    assert c["relevance"] >= 0.8


def test_brand_matching_is_strict():
    c = classify.classify_rules({"text": "Dubai chocolade reep #dubaichocolade", "platform": "instagram"})
    assert "Ola" not in c["brands"]
    c = classify.classify_rules({"text": "De nieuwe Lays paprika is top", "platform": "instagram"})
    assert "Lay's" in c["brands"]


def test_compound_words_and_snackbar_not_chips():
    c = classify.classify_rules({"text": "Kipburger bij de snackbar", "platform": "instagram"})
    assert "Burgers" in c["categories"]
    assert "Chips & snacks" not in c["categories"]


def test_phrases_need_a_food_word():
    phrases = classify.key_phrases("Iedereen praat over de pistache kroket. Klinkt raar maar lekker")
    assert "pistache kroket" in phrases
    assert "iedereen praat" not in phrases


def test_city_from_area_code_hashtag():
    c = classify.classify_rules({"text": "Lekker gegeten #eten020", "platform": "instagram"})
    assert c["city"] == "Amsterdam"


def test_merge_ai_overrides_relevance():
    rule = classify.classify_rules({"text": "Frikandel!", "platform": "instagram"})
    merged = classify.merge_ai(rule, {"relevant": False, "relevantie": 0.9, "nederlands": True,
                                      "categorieen": [], "producten": [], "zaak": "", "stad": "",
                                      "sentiment": "neutraal", "samenvatting": ""})
    assert merged["relevance"] < rule["relevance"]
    merged = classify.merge_ai(rule, {"relevant": True, "relevantie": 1, "nederlands": True,
                                      "categorieen": ["Friet & frituur"],
                                      "producten": [{"naam": "Frikandel XXL", "merk": "Mora",
                                                     "winkel": "", "nieuw": True}],
                                      "zaak": "Snackbar Test", "stad": "Utrecht",
                                      "sentiment": "positief", "samenvatting": "x"})
    assert merged["products"][0]["naam"] == "Frikandel XXL"
    assert "Snackbar Test" in merged["places"]
    assert merged["city"] == "Utrecht"


# --- databronnen omzetten ----------------------------------------------------

def test_normalize_instagram_item():
    p = apify.normalize("instagram", {
        "id": "123", "shortCode": "abc", "caption": "Kapsalon! #kapsalon @snackbar_x",
        "ownerUsername": "Foodie", "timestamp": "2026-10-19T10:00:00.000Z", "likesCount": 50,
        "commentsCount": 4, "hashtags": ["kapsalon"], "mentions": ["snackbar_x"],
        "url": "https://www.instagram.com/p/abc/", "locationName": "Snackbar X"})
    assert p["id"] == "instagram:123"
    assert p["author"] == "foodie"
    assert p["posted_at"] == "2026-10-19T10:00:00Z"
    assert p["likes"] == 50 and p["location"] == "Snackbar X"


def test_normalize_tiktok_item():
    p = apify.normalize("tiktok", {
        "id": "999", "text": "Nieuw bij AH", "createTime": 1760868000,
        "authorMeta": {"name": "snacktok", "fans": 1000}, "diggCount": 5, "shareCount": 2,
        "playCount": 100, "commentCount": 1, "hashtags": [{"name": "NieuwBijAH"}],
        "webVideoUrl": "https://tiktok.com/x"})
    assert p["id"] == "tiktok:999"
    assert p["hashtags"] == ["nieuwbijah"]
    assert p["views"] == 100 and p["author_followers"] == 1000


def test_normalize_facebook_item_without_date_is_skipped():
    assert apify.normalize("facebook", {"postId": "1", "text": "x"}) is None
    p = apify.normalize("facebook", {"postId": "1", "text": "Nieuw!", "time": "2026-10-19T10:00:00Z",
                                     "pageName": "AlbertHeijn", "likes": 3})
    assert p["id"] == "facebook:1" and p["author"] == "albertheijn"


def test_parse_google_news_feed():
    xml = """<rss><channel><item><title>Nieuwe chips bij Jumbo - Distrifood</title>
    <link>https://example.com/a</link><pubDate>Mon, 19 Oct 2026 08:00:00 GMT</pubDate>
    <source url="https://distrifood.nl">Distrifood</source></item></channel></rss>"""
    items = news.parse_feed(xml, "nieuw bij Jumbo")
    assert items[0]["outlet"] == "Distrifood"
    assert items[0]["published_at"] == "2026-10-19T08:00:00Z"


# --- budget --------------------------------------------------------------------

def test_budget_plan_spreads_over_remaining_runs(conn):
    settings = dict(config.DEFAULTS, maandbudget_eur=46.0, eur_per_usd=0.92)
    p = budget.plan(conn, settings)
    assert p["budget_usd"] == 50.0
    total_results = sum(v["results"] for v in p["platforms"].values())
    assert total_results > 0
    assert p["per_run_usd"] * p["runs_left"] == pytest.approx(50.0, rel=0.01)
    budget.record(conn, "apify", 60.0, "tiktok")
    p = budget.plan(conn, settings)
    assert p["left_usd"] == 0 and all(v["results"] == 0 for v in p["platforms"].values())


def test_allocate_prefers_productive_and_stale_sources():
    now = db.now()
    src = [
        {"id": 1, "yield_score": 0.9, "priority": 1, "last_fetched": db.iso(now - timedelta(hours=30))},
        {"id": 2, "yield_score": 0.1, "priority": 1, "last_fetched": db.iso(now)},
        {"id": 3, "yield_score": None, "priority": 1, "last_fetched": None},
    ]
    chosen = budget.allocate(src, 40, 10, 40, now)
    ids = [s["id"] for s, _ in chosen]
    assert ids[0] in (1, 3) and 2 not in ids[:2]
    assert sum(n for _, n in chosen) <= 40
    assert budget.allocate(src, 5, 10, 40, now) == []


# --- trends & ontdekken ------------------------------------------------------

def test_trend_detects_rising_topic(conn):
    posts = []
    # Basislijn: 'kroket' elke dag een beetje.
    for d in range(1, 7):
        posts.append(post(f"b{d}", "Lekkere kroket bij de snackbar #kroket", hours_ago=24 * d + 3))
    # Vandaag: veel makers over #pistachekroket.
    for i in range(6):
        posts.append(post(f"n{i}", "Pistache kroket bij de snackbar in Rotterdam! #pistachekroket #kroket",
                          hours_ago=2 + i))
    store_posts(conn, posts, None)
    conn.execute("INSERT INTO runs(started_at, status) VALUES (?, 'klaar')",
                 (db.iso(db.now() - timedelta(days=10)),))
    r = trends.compute(conn, "24u")
    names = [t["name"] for t in r["topics"]]
    assert "#pistachekroket" in names
    top = next(t for t in r["topics"] if t["name"] == "#pistachekroket")
    assert top["new"] is True and top["authors"] == 6
    assert names.index("#pistachekroket") < names.index("#kroket")
    assert r["history_ok"]
    assert not any(t["type"] == "zin" and t["name"] == "pistache kroket" for t in r["topics"])


def test_single_author_spam_is_not_a_trend(conn):
    store_posts(conn, [post(f"s{i}", "Koop mijn frikandel #spamfrikandel", author="spammer",
                            hours_ago=1 + i) for i in range(10)], None)
    r = trends.compute(conn, "24u")
    assert "#spamfrikandel" not in [t["name"] for t in r["topics"]]


def test_discovery_adds_hashtag_and_pauses_bad_source(conn):
    store_posts(conn, [post(f"d{i}", f"Birria tacos bij de foodtruck, lekker! #birriatacos #foodtruck",
                            hours_ago=3 + i) for i in range(4)], None)
    settings = dict(config.DEFAULTS)
    added = discovery.run(conn, settings)
    values = {(a["kind"], a["value"]) for a in added}
    assert ("hashtag", "birriatacos") in values
    row = conn.execute("SELECT status, origin FROM sources WHERE value = 'birriatacos'").fetchone()
    assert row["status"] == "actief" and row["origin"] == "ontdekt"

    conn.execute("INSERT INTO sources(platform, kind, value, origin, added_at) "
                 "VALUES ('tiktok', 'hashtag', 'saai', 'ontdekt', ?)", (db.iso(db.now()),))
    sid = conn.execute("SELECT id FROM sources WHERE value = 'saai'").fetchone()["id"]
    for _ in range(3):
        discovery.update_source_stats(conn, sid, 30, 1)
    assert conn.execute("SELECT status FROM sources WHERE id = ?", (sid,)).fetchone()["status"] == "gepauzeerd"


def test_empty_account_becomes_invalid_but_manual_stays(conn):
    now = db.iso(db.now())
    conn.execute("INSERT INTO sources(platform, kind, value, origin, added_at) VALUES "
                 "('instagram', 'account', 'bestaatniet', 'start', ?), "
                 "('instagram', 'account', 'mijnfavoriet', 'handmatig', ?)", (now, now))
    for value in ("bestaatniet", "mijnfavoriet"):
        sid = conn.execute("SELECT id FROM sources WHERE value = ?", (value,)).fetchone()["id"]
        discovery.update_source_stats(conn, sid, 0, 0)
        discovery.update_source_stats(conn, sid, 0, 0)
    status = dict(conn.execute("SELECT value, status FROM sources").fetchall())
    assert status["bestaatniet"] == "ongeldig"
    assert status["mijnfavoriet"] == "actief"


def test_snackspert_name_matching():
    reviewed = [{"name": "Snackbar De Gouden Hoek", "url": "u", "norm": snackspert.core_name("Snackbar De Gouden Hoek")}]
    assert snackspert.match("@degoudenhoek_snackbar", reviewed)
    assert snackspert.match("Cafetaria De Gouden Hoek", reviewed)
    assert snackspert.match("Frituur Bakkie Patat", reviewed) is None


def test_demo_round_and_api(conn, monkeypatch):
    from trendradar import demo
    from trendradar.web import app

    n = demo.simulate_round(conn)
    conn.commit()
    assert n > 500
    client = app.test_client()
    for url in ("/api/status", "/api/trends?window=nu", "/api/trends?window=7d&platform=tiktok",
                "/api/posts?q=kroket", "/api/supermarkt", "/api/zaken", "/api/sources",
                "/api/budget", "/api/runs", "/api/export/trends.csv",
                "/api/topic?type=product&name=x", "/api/topic?type=stad&name=Rotterdam"):
        assert client.get(url).status_code == 200, url
    assert client.get("/api/trends?window=1j").status_code == 400
    assert client.post("/api/settings", json={"interval_uren": 0}).status_code == 400
    r = client.post("/api/sources", json={"platform": "tiktok", "kind": "hashtag", "value": "#Kroket"})
    assert r.status_code == 200
    with db.session() as c2:
        assert c2.execute("SELECT 1 FROM sources WHERE value='kroket' AND origin='handmatig'").fetchone()
    demo.clear(conn)
    conn.commit()
    assert conn.execute("SELECT COUNT(*) FROM posts WHERE demo = 1").fetchone()[0] == 0


def test_ai_classification_request_and_parsing(monkeypatch):
    import json as _json
    import types

    import anthropic

    calls = {}

    class FakeMessages:
        def create(self, **kw):
            calls.update(kw)
            body = {"posts": [{"id": "instagram:1", "relevant": True, "relevantie": 0.9,
                               "nederlands": True, "categorieen": ["Chips & snacks"],
                               "producten": [{"naam": "Kapsalon Chips", "merk": "Lay's",
                                              "winkel": "Albert Heijn", "nieuw": True}],
                               "zaak": "", "stad": "", "sentiment": "positief",
                               "samenvatting": "Nieuwe chips getest"}]}
            return types.SimpleNamespace(
                stop_reason="end_turn",
                usage=types.SimpleNamespace(input_tokens=1000, output_tokens=500),
                content=[types.SimpleNamespace(type="text", text=_json.dumps(body))])

    class FakeClient:
        def __init__(self, **kw):
            self.messages = FakeMessages()
            self.beta = types.SimpleNamespace(messages=FakeMessages())

    monkeypatch.setattr(anthropic, "Anthropic", FakeClient)
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test")
    settings = dict(config.DEFAULTS)
    results, cost = classify.classify_ai([{"id": "instagram:1", "platform": "instagram",
                                           "text": "Nieuwe chips!"}], settings)
    assert results["instagram:1"]["producten"][0]["naam"] == "Kapsalon Chips"
    assert cost == pytest.approx((1000 * 4 + 500 * 20) / 1_000_000)
    assert calls["model"] == "claude-opus-5-5"
    assert calls["fallbacks"] == "default"
    assert calls["output_config"]["format"]["type"] == "json_schema"
    # Het echte SDK moet deze parameters accepteren.
    import inspect
    sig = inspect.signature(anthropic.resources.beta.messages.Messages.create)
    for name in ("betas", "fallbacks", "output_config", "system", "model", "max_tokens", "messages"):
        assert name in sig.parameters


def test_secrets_are_redacted(monkeypatch):
    monkeypatch.setenv("APIFY_TOKEN", "apify_api_geheim123")
    assert "geheim" not in config.redact("fout bij ...?token=apify_api_geheim123&x=1")
