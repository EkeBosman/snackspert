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
    assert "pistache kroket" in names
    top = next(t for t in r["topics"] if t["name"] == "pistache kroket")
    assert top["new"] is True and top["authors"] == 6
    # Hashtags zijn hulpmiddel om te zoeken, geen onderwerp.
    assert not any(t["name"].startswith("#") for t in r["topics"])
    assert r["history_ok"]


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


# --- signalen, virale makers, supermarkt, kosten ------------------------------

def _p(i, views, followers, hours_ago, platform="tiktok", **kw):
    return post(f"s{i}", kw.pop("text", "Lekkere frikandel bij de snackbar #frikandel"),
                hours_ago=hours_ago, platform=platform, views=views, author_followers=followers,
                snapshot_at=db.iso(db.now()), **kw)


def test_signals_compare_with_posts_of_same_age(conn):
    from trendradar import signals
    # Oude posts hebben veel views (ze staan er al lang), nieuwe weinig: dat is normaal.
    store_posts(conn, [_p(i, 50_000, 5000, 60) for i in range(20)]
                + [_p(100 + i, 1_000, 5000, 2) for i in range(20)], None)
    base = signals.baselines(conn)
    fresh_normal = signals.of_post(_p(900, 1_000, 5000, 2) | {"fetched_at": db.iso(db.now())}, base)
    assert fresh_normal["views_x"] == 1.0 and not fresh_normal["breakout"]
    viral = signals.of_post(_p(901, 40_000, 900, 2) | {"fetched_at": db.iso(db.now())}, base)
    assert viral["breakout"] and viral["small_creator"] and viral["views_x"] >= 30
    assert "doorbraak" in signals.labels(viral)


def test_breakout_from_unknown_creator_becomes_source_first(conn):
    store_posts(conn, [_p(i, 1_000, 5000, 2 + i % 3) for i in range(20)], None)
    store_posts(conn, [_p(500, 80_000, 700, 3, text="Frikandelijs?! Moet je proberen #frikandelijs #snackbar",
                         author="kleine_maker")], None)
    added = discovery.run(conn, dict(config.DEFAULTS, max_nieuwe_bronnen_per_run=2))
    first = [(a["kind"], a["value"]) for a in added if a["status"] == "actief"]
    assert ("hashtag", "frikandelijs") in first or ("account", "kleine_maker") in first
    assert any("viraal" in a["reason"] for a in added)


def test_trends_show_single_viral_creator(conn):
    store_posts(conn, [_p(i, 1_000, 5000, 1 + i % 4) for i in range(20)], None)
    store_posts(conn, [_p(600, 90_000, 800, 2, text="Bitterbal softijs gespot! #bitterbalijs",
                         author="eenling")], None)
    r = trends.compute(conn, "24u")
    names = [t["name"] for t in r["topics"]]
    assert "bitterbal softijs" in names or "bitterbalijs" in names
    assert r["totals"]["breakouts"] >= 1 and r["breakouts"][0]["signals"]["followers"] == 800


def test_product_names_and_early_signals(conn):
    from trendradar import products
    assert products.same("Kapsalon Chips", "Smaakmakers Kapsalon Chips 150g")
    assert not products.same("Paprika Chips", "Naturel Chips")
    c = classify.classify_rules({"text": "Nieuw bij AH: Paprika Chips Limoen! #ahnieuw", "platform": "tiktok"})
    assert c["products"][0]["naam"] == "Paprika Chips Limoen" and c["products"][0]["winkel"] == "Albert Heijn"
    assert classify.classify_rules({"text": "Nieuw bij AH: mijn collega Jan", "platform": "tiktok"})["products"] == []

    now = db.iso(db.now())
    conn.execute("INSERT INTO products(id, store, name, first_seen, last_seen, is_new) "
                 "VALUES ('ah:1', 'Albert Heijn', 'AH Paprika Chips Limoen', ?, ?, 1)", (now, now))
    store_posts(conn, [post(f"pr{i}", "Nieuw bij AH: Paprika Chips Limoen! Echt lekker", hours_ago=3)
                       for i in range(3)]
                + [post(f"bj{i}", "Gespot bij Jumbo: Bitterbal Chips! Nieuwe smaak", hours_ago=2)
                   for i in range(2)], None)
    o = products.overview(conn)
    assert o["products"][0]["confirmed_by"] == ["winkel", "social"]
    assert o["products"][0]["social_makers"] == 3
    early = {m["name"]: m for m in o["early"]}
    assert "Bitterbal Chips" in early and early["Bitterbal Chips"]["store_tracked"]
    assert "Paprika Chips Limoen" not in early


def test_apify_round_saves_money(conn, monkeypatch):
    """Datumfilter, kosten per bron, en bronnen met weinig nieuws later opnieuw."""
    from trendradar import collector
    from trendradar.sources import apify as ap

    conn.execute("INSERT INTO sources(platform, kind, value, added_at) VALUES "
                 "('tiktok', 'hashtag', 'frikandel', ?), ('tiktok', 'hashtag', 'kroket', ?)",
                 (db.iso(db.now()), db.iso(db.now())))
    conn.commit()
    calls = []

    def fake_run(platform, kind, values, per_value, max_usd, since=None, **kw):
        calls.append({"kind": kind, "values": values, "since": since, "max_usd": max_usd})
        items = [{"id": f"{v}{i}", "text": f"Lekkere {v} bij de snackbar #{v}", "createTime": 1760868000,
                  "authorMeta": {"name": f"m{i}", "fans": 100}, "playCount": 10,
                  "hashtags": [{"name": v}]} for v in values for i in range(per_value)]
        return items, 0.50

    monkeypatch.setattr(ap, "available", lambda: True)
    monkeypatch.setattr(ap, "run_actor", fake_run)
    settings = dict(config.DEFAULTS, maandbudget_eur=600.0)
    run = collector.Run("test")
    collector.step_apify(run, settings, set())
    assert calls and calls[0]["since"]  # datumfilter meegestuurd
    assert all(c["max_usd"] > 0 for c in calls)
    rows = {r["value"]: dict(r) for r in conn.execute("SELECT * FROM sources")}
    assert sum(r["cost_usd"] for r in rows.values()) == pytest.approx(0.5 * len(calls))
    assert all(r["useful_total"] > 0 and r["next_due"] for r in rows.values())

    # Tweede ronde direct erna: bronnen zijn nog niet aan de beurt.
    calls.clear()
    collector.step_apify(run, settings, set())
    assert calls == []

    # Na de wachttijd: zelfde posts terug = 0% nieuw -> volgende keer pas na 4 rondes.
    conn.execute("UPDATE sources SET next_due = ?", (db.iso(db.now() - timedelta(minutes=1)),))
    conn.commit()
    collector.step_apify(run, settings, set())
    r = conn.execute("SELECT next_due, last_new FROM sources WHERE value = 'frikandel'").fetchone()
    assert r["last_new"] == 0
    assert db.parse_iso(r["next_due"]) > db.now() + timedelta(hours=20)


def test_migration_adds_new_columns(tmp_path, monkeypatch):
    import sqlite3
    monkeypatch.setattr(config, "DATA_DIR", tmp_path)
    monkeypatch.setattr(config, "DB_PATH", tmp_path / "oud.db")
    old = sqlite3.connect(tmp_path / "oud.db")
    old.execute("CREATE TABLE sources (id INTEGER PRIMARY KEY, platform TEXT, kind TEXT, value TEXT, "
                "status TEXT, origin TEXT, added_at TEXT)")
    old.commit()
    old.close()
    db.init()
    with db.session() as c:
        cols = {r["name"] for r in c.execute("PRAGMA table_info(sources)")}
    assert {"next_due", "cost_usd", "useful_total", "last_new"} <= cols


def test_first_real_round_after_demo_does_not_lock(conn, monkeypatch):
    """Eerste echte ronde na de demo: demodata wissen en loggen mag niet vastlopen."""
    from trendradar import collector, demo
    from trendradar.sources import apify as ap

    demo.simulate_round(conn)
    conn.commit()
    monkeypatch.setattr(db, "connect", _fast_connect(db.connect))
    monkeypatch.setattr(ap, "available", lambda: True)
    monkeypatch.setattr(ap, "run_actor", lambda *a, **k: ([], 0.0))
    for step in ("step_news", "step_supermarkets", "step_snackspert", "step_remeasure", "step_ai"):
        monkeypatch.setattr(collector, step, lambda *a, **k: None)
    collector.run_once("test")
    with db.session() as c:
        run = collector.last_run(c)
        demo_left = c.execute("SELECT COUNT(*) FROM posts WHERE demo = 1").fetchone()[0]
    assert run["status"] != "fout", run["log"]
    assert demo_left == 0


def _fast_connect(original):
    # Kortere wachttijd, zodat een vastlopende database de test niet 30 s ophoudt.
    def connect():
        c = original()
        c.execute("PRAGMA busy_timeout = 1000")
        return c
    return connect


def test_supermarket_new_products_via_checkjebon(conn, monkeypatch):
    from trendradar import collector
    from trendradar.sources import supermarket

    raw = [{"n": "ah", "u": "https://www.ah.nl/producten/product/", "d": [
               {"n": "AH Naturel chips", "l": "wi1/chips", "p": 1.29, "s": "200 g"}]},
           {"n": "lidl", "u": "https://x/", "d": [{"n": "Kip gyros", "l": "77", "p": 6.19, "s": "750 g"}]},
           {"n": "aldi", "u": "https://y/", "d": []}]
    first = supermarket.parse(raw)
    assert first["Albert Heijn"][0]["url"] == "https://www.ah.nl/producten/product/wi1/chips"
    second = supermarket.parse(raw)
    second["Albert Heijn"] += [
        {"id": "ah:wi2/kapsalon", "store": "Albert Heijn", "name": "AH Kapsalon chips", "size": "150 g",
         "price": 1.99, "url": None},
        {"id": "ah:wi3/shampoo", "store": "Albert Heijn", "name": "AH Shampoo kokos", "size": "300 ml",
         "price": 2.49, "url": None}]
    responses = iter([(first, '"a"'), (None, '"a"'), (second, '"b"')])
    monkeypatch.setattr(supermarket, "fetch", lambda etag=None: next(responses))
    settings = dict(config.DEFAULTS)

    run = collector.Run("test")
    collector.step_supermarkets(run, settings, force=True)   # nulmeting: niets nieuw
    assert conn.execute("SELECT COUNT(*) FROM products WHERE is_new = 1").fetchone()[0] == 0
    collector.step_supermarkets(run, settings, force=True)   # 304: niets veranderd
    assert "geen nieuwe" in run.lines[-1]["tekst"]
    collector.step_supermarkets(run, settings, force=True)
    new = {r["name"]: r["relevant"] for r in conn.execute("SELECT * FROM products WHERE is_new = 1")}
    assert new == {"AH Kapsalon chips": 1, "AH Shampoo kokos": 0}

    from trendradar import products
    o = products.overview(conn)
    assert [p["name"] for p in o["products"]] == ["AH Kapsalon chips"]
    assert len(products.overview(conn, only_relevant=False)["products"]) == 2
    with db.session() as c:
        status = db.get_state(c, "supermarkt_status")
    assert status["Albert Heijn"]["ok"] and not status["Aldi"]["ok"]


def test_apify_minimum_charge_and_cost_estimate(monkeypatch):
    from trendradar.sources import apify as ap

    sent = {}

    class Resp:
        def __init__(self, data, status=200):
            self._d, self.status_code, self.ok = data, status, status < 400
            self.text = ""

        def json(self):
            return self._d

        def raise_for_status(self):
            pass

    def post(url, params=None, headers=None, json=None, timeout=None):
        sent.update(params or {})
        sent["auth"] = headers.get("Authorization")
        return Resp({"data": {"id": "r1", "status": "SUCCEEDED", "defaultDatasetId": "d1"}})

    def get(url, params=None, headers=None, timeout=None):
        if "/datasets/" in url:
            return Resp([{"id": i} for i in range(40)])
        return Resp({"data": {"id": "r1", "status": "SUCCEEDED", "usageTotalUsd": 0}})

    monkeypatch.setenv("APIFY_TOKEN", "tok")
    monkeypatch.setattr(ap.requests, "post", post)
    monkeypatch.setattr(ap.requests, "get", get)
    items, cost = ap.run_actor("tiktok", "hashtag", ["kroket"], 40, 0.05, price_per_1000=1.70)
    assert sent["maxTotalChargeUsd"] == "0.50" and sent["maxItems"] == 40
    assert "token" not in sent and sent["auth"] == "Bearer tok"
    assert cost == pytest.approx(40 * 1.70 / 1000)


def test_only_dutch_posts_count():
    def nl(text):
        return classify.classify_rules({"text": text, "platform": "instagram"})["nl_score"]
    # Spaans, Portugees en Engels met #snackbar: niet Nederlands.
    assert nl("XV años Estefanía Muchas Gracias a Elena por permitirnos ser parte de este día #snackbar") < 0.4
    assert nl("Crocante por fora, irresistível por dentro! As nossas coxinhas são uma tentação #snackbar") < 0.4
    assert nl("A colorful snapshot in the middle of Dirkshorn. The tree now matches the snack bar.") < 0.4
    assert nl("Patatas bravas con salsa de la casa #snackbar #tapas") < 0.4
    # Nederlands, ook kort of gemengd met een Engelse zin.
    assert nl("Honger tijdens Hardenberg Swingt? Sevens has got you covered! Deel dit bericht met je vrienden!") >= 0.4
    assert nl("Bitterbal softijs gespot! #bitterbalijs") >= 0.4
    assert nl("Even iets fris! Niet iedere lunch hoeft een broodje te zijn.") >= 0.4


def test_existing_posts_are_rescored_on_start(conn):
    from trendradar import collector
    store_posts(conn, [post("es1", "Muchas gracias por este día con la familia #snackbar")], None)
    conn.execute("UPDATE posts SET nl_score = 0.9")  # zoals de oude regels het zagen
    db.set_state(conn, "classify_version", 1)
    conn.commit()
    assert collector.reclassify_if_needed() == 1
    assert conn.execute("SELECT nl_score FROM posts").fetchone()[0] < 0.4
    assert collector.reclassify_if_needed() == 0


def test_news_list_only_shows_relevant_news(conn):
    from trendradar import products
    now = db.iso(db.now())
    for nid, title in (("nieuws:a", "Nieuwe chips met kapsalonsmaak bij Albert Heijn"),
                       ("nieuws:b", "Drie doden door stormweer in Frankrijk")):
        conn.execute("INSERT INTO news(id, title, published_at, fetched_at) VALUES (?, ?, ?, ?)",
                     (nid, title, now, now))
        store_posts(conn, [{"id": nid, "platform": "nieuws", "text": title, "posted_at": now}], None)
    titles = [n["title"] for n in products.overview(conn)["news"]]
    assert titles == ["Nieuwe chips met kapsalonsmaak bij Albert Heijn"]


def test_kapsalon_at_the_hairdresser_is_not_a_snack():
    hair = classify.classify_rules({"text": "Nieuwe coupe gezet bij onze kapsalon! #kapper #kapsalon",
                                    "platform": "instagram"})
    snack = classify.classify_rules({"text": "Beste kapsalon van Rotterdam, extra knoflooksaus #kapsalon",
                                     "platform": "instagram"})
    assert hair["relevance"] < 0.35 and snack["relevance"] > 0.7


def test_discovery_only_adds_food_hashtags(conn):
    from trendradar.discovery import acceptable_hashtag
    for bad in ("kapper", "deals", "herfst", "groningen", "albertheijn", "snackbar"):
        assert not acceptable_hashtag(bad), bad
    for good in ("birriatacos", "frikandelijs", "pistachekroket", "foodtruckfestival"):
        assert acceptable_hashtag(good), good
    assert acceptable_hashtag("tanghulu", viral=True)  # nieuwe snack uit een virale post

    store_posts(conn, [post(f"h{i}", "Lekkere frikandel bij de snackbar! #herfst #deals #birriatacos",
                            hours_ago=2 + i) for i in range(4)], None)
    added = {a["value"] for a in discovery.run(conn, dict(config.DEFAULTS)) if a["kind"] == "hashtag"}
    assert "birriatacos" in added and not {"herfst", "deals"} & added


def test_bad_discovered_sources_are_cleaned_up(conn):
    from trendradar import collector
    now = db.iso(db.now())
    for value, reason in (("kapper", "in 5 relevante posts"), ("birriatacos", "in 5 relevante posts"),
                          ("tanghulu", "uit virale post van @x (12× views)")):
        conn.execute("INSERT INTO sources(platform, kind, value, status, origin, reason, added_at) "
                     "VALUES ('instagram', 'hashtag', ?, 'actief', 'ontdekt', ?, ?)", (value, reason, now))
    db.set_state(conn, "classify_version", 2)
    conn.commit()
    collector.reclassify_if_needed()
    status = dict(conn.execute("SELECT value, status FROM sources").fetchall())
    assert status == {"kapper": "afgewezen", "birriatacos": "actief", "tanghulu": "actief"}


def test_indonesian_and_turkish_posts_are_not_dutch():
    def nl(text):
        return classify.classify_rules({"text": text, "platform": "instagram"})["nl_score"]
    assert nl("Enak banget kroket ini, harga murah dan rasa mantap! #snackbar") < 0.4
    assert nl("Çok lezzetli döner, afiyet olsun! #kapsalon") < 0.4
    # Nederlandse post over Indisch eten blijft Nederlands.
    assert nl("Heerlijke nasi en saté gehaald bij de toko, echt een aanrader") >= 0.4


def test_new_compound_snack_words_are_topics(conn):
    assert classify.new_compounds(["frikandelijs", "frikandel", "snackbarlucy", "foodspotsamsterdam",
                                   "kapsalonchips", "lekker"]) == ["frikandelijs", "kapsalonchips"]
    store_posts(conn, [post(f"fi{i}", "Moet je proberen! #frikandelijs", hours_ago=1 + i)
                       for i in range(3)], None)
    r = trends.compute(conn, "24u")
    word = next(t for t in r["topics"] if t["name"] == "frikandelijs")
    assert word["type"] == "woord" and word["type_label"] == "Nieuw woord"


def test_new_word_that_is_part_of_a_product_is_not_repeated(conn):
    store_posts(conn, [post(f"kc{i}", "Nieuw bij AH: Kapsalon Chips! #kapsalonchips", hours_ago=1 + i,
                            products=[{"naam": "Smaakmakers Kapsalon Chips", "merk": "", "winkel": "Albert Heijn",
                                       "nieuw": True}]) for i in range(3)], None)
    names = [t["name"] for t in trends.compute(conn, "24u")["topics"]]
    assert "Smaakmakers Kapsalon Chips" in names and "kapsalonchips" not in names


# --- vóór de hype: nieuw op de kaart, combinaties, fase, Amsterdam, Mijn lijst ---

def test_new_on_the_menu_and_unexpected_combination():
    c = classify.classify_rules({"text": "Nieuw op de kaart: broodje met döner en kaassoufflé! #snackbar",
                                 "platform": "tiktok"})
    assert "nieuw_op_kaart" in c["flags"]
    assert "combinatie:kaassoufflé + döner" in c["flags"]
    gewoon = classify.classify_rules({"text": "Frietje met frikandel bij de snackbar, lekker!",
                                      "platform": "tiktok"})
    assert not any(f.startswith("combinatie:") for f in gewoon["flags"])


def test_amsterdam_neighbourhood_counts_as_amsterdam():
    c = classify.classify_rules({"text": "Weekspecial bij onze zaak in De Pijp: soufflé tosti met kaassoufflé",
                                 "platform": "instagram"})
    assert c["city"] == "Amsterdam"
    assert "nieuw_op_kaart" in c["flags"]


def test_phase_of_the_hype():
    assert trends.phase({"growth_pct": -40, "authors": 3, "news": 0}) == "over"
    assert trends.phase({"growth_pct": 50, "authors": 2, "news": 0}) == "vroeg"
    assert trends.phase({"growth_pct": 50, "authors": 8, "news": 0}) == "groeit"
    assert trends.phase({"growth_pct": 50, "authors": 8, "news": 2}) == "piek"


def test_candidates_and_amsterdam_filter(conn):
    store_posts(conn, [
        post("ams", "Nieuw op de kaart in de Jordaan: tosti met kaassoufflé! #amsterdamfood", platform="tiktok"),
        post("rdam", "Nieuw bij ons: broodje döner met kaassoufflé #eten010", platform="tiktok"),
        post("saai", "Lekker frietje gehaald bij de snackbar", platform="tiktok"),
    ], None)
    ids = [c["id"] for c in trends.candidates(conn, include_demo=False)]
    assert "tiktok:ams" in ids and "tiktok:rdam" in ids and "tiktok:saai" not in ids
    ams = [c["id"] for c in trends.candidates(conn, city="Amsterdam", include_demo=False)]
    assert ams == ["tiktok:ams"]
    assert all(p["city"] == "Amsterdam" for p in trends.load_posts(conn, db.now() - timedelta(days=1),
                                                                   db.now(), city="Amsterdam"))


def test_watchlist_api(conn):
    from trendradar.web import app

    client = app.test_client()
    r = client.post("/api/lijst", json={"kind": "zaak", "ref": "Broodjesbar Stoep", "title": "Broodjesbar Stoep",
                                        "city": "Amsterdam"})
    assert r.status_code == 200
    item = client.get("/api/lijst").get_json()["items"][0]
    assert item["status"] == "te proberen"
    assert client.patch(f"/api/lijst/{item['id']}", json={"status": "gepland", "note": "zaterdag"}).status_code == 200
    assert client.patch(f"/api/lijst/{item['id']}", json={"status": "onzin"}).status_code == 400
    item = client.get("/api/lijst").get_json()["items"][0]
    assert (item["status"], item["note"]) == ("gepland", "zaterdag")
    assert "Broodjesbar Stoep" in client.get("/api/export/lijst.csv").get_data(as_text=True)
    for url in ("/api/vandaag", "/api/kandidaten?city=Amsterdam", "/api/nieuws?soort=amsterdam",
                "/api/trends?city=Amsterdam"):
        assert client.get(url).status_code == 200, url
    assert client.delete(f"/api/lijst/{item['id']}").status_code == 200
    assert client.get("/api/lijst").get_json()["items"] == []


def test_seed_upgrade_adds_new_searches_once(conn):
    from trendradar import seeds

    now = db.iso(db.now())
    seeds.install(conn, now)
    conn.execute("DELETE FROM sources WHERE value = 'nieuw op de kaart snackbar'")
    conn.execute("UPDATE sources SET status = 'gepauzeerd' WHERE value = 'snackbar' AND platform = 'tiktok'")
    db.set_state(conn, "seeds_version", 1)
    assert seeds.upgrade(conn, now) == 1
    assert seeds.upgrade(conn, now) == 0
    row = conn.execute("SELECT status, priority FROM sources WHERE value = 'snackbar' AND platform = 'tiktok'"
                       " AND kind = 'hashtag'").fetchone()
    assert row["status"] == "gepauzeerd" and row["priority"] == 0.5


def test_apify_retries_without_optional_fields(monkeypatch):
    from trendradar.sources import apify as ap

    bodies = []

    class Resp:
        def __init__(self, data, status=200):
            self._d, self.status_code, self.ok, self.text = data, status, status < 400, "invalid input"

        def json(self):
            return self._d

        def raise_for_status(self):
            pass

    def post(url, params=None, headers=None, json=None, timeout=None):
        bodies.append(json)
        if len(bodies) == 1:
            return Resp({}, 400)
        return Resp({"data": {"id": "r1", "status": "SUCCEEDED", "defaultDatasetId": "d1"}})

    def get(url, params=None, headers=None, timeout=None):
        if "/datasets/" in url:
            return Resp([])
        return Resp({"data": {"id": "r1", "status": "SUCCEEDED", "usageTotalUsd": 0.01}})

    monkeypatch.setenv("APIFY_TOKEN", "tok")
    monkeypatch.setattr(ap.requests, "post", post)
    monkeypatch.setattr(ap.requests, "get", get)
    ap.run_actor("tiktok", "zoekterm", ["broodje kaassoufflé"], 10, 0.5)
    assert len(bodies) == 2
    assert ap.OPTIONAL_KEYS & bodies[0].keys() and not ap.OPTIONAL_KEYS & bodies[1].keys()


# --- leren van Mijn lijst --------------------------------------------------------

def test_twist_on_a_known_snack():
    for text in ("Loaded kipcorn gehaald bij de snackbar 🔥", "Mijn eerste #loadedkipcorn bij de cafetaria"):
        assert "twist:loaded kipcorn" in classify.classify_rules({"text": text, "platform": "tiktok"})["flags"]
    gewoon = classify.classify_rules({"text": "Loaded friet bij de snackbar", "platform": "tiktok"})
    assert not any(f.startswith("twist:") for f in gewoon["flags"])


def _save(conn, kind, ref, title, status="te proberen"):
    now = db.iso(db.now())
    conn.execute("INSERT INTO watchlist(kind, ref, title, status, added_at, updated_at) VALUES (?,?,?,?,?,?)",
                 (kind, ref, title, status, now, now))


def test_saved_items_teach_vandaag(conn):
    from trendradar import taste

    # Een gewone kipcorn-post zonder bijzondere signalen: eerst geen kandidaat.
    store_posts(conn, [post("oud", "Loaded kipcorn bij de snackbar, echt lekker", hours_ago=30,
                            platform="tiktok", author="eerste"),
                       post("nieuw", "Vandaag loaded kipcorn gehaald bij de cafetaria #snackbar", hours_ago=2,
                            platform="tiktok", author="tweede")], None)
    before = {c["id"]: c for c in trends.candidates(conn, include_demo=False)}
    assert "Past bij jou" not in " ".join(before.get("tiktok:nieuw", {}).get("reasons", []))

    _save(conn, "post", "tiktok:oud", "Loaded kipcorn")
    prof = taste.profile(conn)
    assert prof["twist:loaded kipcorn"] > 0 and prof["snack:kipcorn"] > 0
    after = {c["id"]: c for c in trends.candidates(conn, include_demo=False)}
    assert "tiktok:oud" not in after  # al bewaard
    assert any(r.startswith("Past bij jou") for r in after["tiktok:nieuw"]["reasons"])
    assert after["tiktok:nieuw"]["score"] > before.get("tiktok:nieuw", {"score": 0})["score"]
    learned = taste.summary(prof)
    assert learned[0]["kenmerk"] == "loaded kipcorn" and learned[0]["soort"] == "twist"
    assert [item["kenmerk"] for item in learned].count("loaded kipcorn") == 1


def test_rejected_items_count_against(conn):
    from trendradar import taste

    _save(conn, "onderwerp", "zin|loaded kipcorn", "loaded kipcorn", status="afgevallen")
    assert taste.profile(conn)["zin:loaded kipcorn"] < 0
    bonus, _, _ = taste.match(taste.profile(conn), {"zin:loaded kipcorn"})
    assert bonus < 0


def test_saved_items_become_sources(conn):
    _save(conn, "onderwerp", "zin|loaded kipcorn", "loaded kipcorn")
    store_posts(conn, [post("km", "Loaded kipcorn bij de snackbar", platform="tiktok", author="kleinemaker")], None)
    _save(conn, "post", "tiktok:km", "Loaded kipcorn")
    found = discovery.list_searches(conn, discovery._known(conn), limit=5)
    values = {(f["platform"], f["kind"], f["value"]) for f in found}
    assert ("tiktok", "zoekterm", "loaded kipcorn") in values
    assert ("tiktok", "account", "kleinemaker") in values
    assert all(f["reason"].startswith("uit Mijn lijst") for f in found)
    # Tips alleen (gewicht 0,5) worden geen bron.
    conn.execute("INSERT INTO spots(name, place, specialty, added_at, updated_at) "
                 "VALUES ('Snackbar de Poppe', 'Coevorden', 'broodje lammert', 'x', 'x')")
    later = discovery.list_searches(conn, discovery._known(conn), limit=10)
    assert not any("poppe" in f["value"] for f in later)


# --- ♥/👎, mijn posts, tips & routes ------------------------------------------------

def _workbook() -> bytes:
    import io as _io

    import openpyxl

    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Posts"
    ws.append(["Maand", "Jaar", "Datum", "Type", "Caption (begin)", "Link", "Weergaven", "Bereik", "Likes",
               "Reacties", "Gedeeld", "Opgeslagen", "Volgers", "Format", "Kanaal", "Locatie", "Herkenbaarheid",
               "Indeling", "Volgers telt mee"])
    rows = [
        ("2026-01", "De grote frikandel uit de supermarkt test is hierrrr! Met friet. 1. AH", 400000, "Supermarkttest", "Ja"),
        ("2026-01", "Friet bij Snackbar de Poppe in Coevorden, broodje lammert!", 300000, "Snackbar review", "Ja"),
        ("2026-02", "Friet special in Utrecht", 250000, "Snackbar review", "Ja"),
        ("2026-02", "Friet met mayo bij @frietboer", 220000, "Snackbar review", "Ja"),
        ("2026-02", "Frietje in Den Haag", 210000, "Snackbar review", "Ja"),
        ("2026-03", "Friet in Leiden, krokant", 205000, "Snackbar review", "Ja"),
        ("2026-03", "Pizza in Amsterdam", 100000, "Streetfood review", "Ja"),
        ("2026-03", "ad | Pizza samenwerking #samenwerking", 90000, "Samenwerking", "Nee"),
    ]
    for i, (month, caption, views, fmt, counts) in enumerate(rows):
        ws.append([month, 2026, f"{month}-1{i}", "IG-reel", caption, "open post", views, views // 2, 100, 10,
                   50 + i, 5, 30 + i, fmt, "Snackbar", "Buiten Amsterdam", "Mainstream", "Gecontroleerd", counts])
        ws.cell(ws.max_row, 6).hyperlink = f"https://www.instagram.com/reel/test{i}/"
    # Een afgeleid tabblad met dezelfde post (ingekorte caption): mag geen dubbele post opleveren.
    dup = wb.create_sheet("Samenwerkingen")
    dup.append(["Maand", "Datum", "Caption (begin)", "Weergaven", "Volgers", "Gedeeld", "Link"])
    dup.append(["2026-03", "2026-03-17", "ad | Pizza samenwerking", 90000, 37, 57, "open post"])
    dup.cell(2, 7).hyperlink = "https://www.instagram.com/reel/test7/"
    spots = wb.create_sheet("Alle Spots (buiten A'dam)")
    spots.append(["Naam", "Locatie", "Specialiteit", "Regio"])
    spots.append(["Snackbar de Poppe", "Coevorden", "broodje lammert (hamburger met kaassoufflé)", "Drenthe"])
    spots.append(["Frietboerderij", "ONBEKEND", None, "Utrecht"])
    ams = wb.create_sheet("Amsterdam")
    ams.append(["Naam", "Specialiteit"])
    ams.append(["Döner Father", "croissant döner"])
    routes = wb.create_sheet("Routes")
    routes.append(["#", "Route", "Regio", "Stop 1", "Stop 2", "Stop 3", "KM Retour", "Rijtijd", "Opmerkingen"])
    routes.append([1, "Drenthe kort", "Drenthe", "Snackbar de Poppe (Coevorden) - broodje lammert",
                   "Snackbar City (Hoogeveen) - gehaktbal", "Pizza Pazza (Norg)", "~400 km", "5u", "test"])
    summary = wb.create_sheet("Samenvatting")
    summary.append([None, None])
    summary.append(["TOTAAL", 3])
    buf = _io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


def test_import_own_posts_tips_and_routes(conn):
    import io as _io

    from trendradar import ownposts, spots
    from trendradar.web import app

    client = app.test_client()
    r = client.post("/api/import", data={"bestand": (_io.BytesIO(_workbook()), "overzicht.xlsx")},
                    content_type="multipart/form-data")
    assert r.status_code == 200, r.get_json()
    res = r.get_json()
    assert (res["posts"], res["spots"], res["routes"]) == (8, 3, 1)
    bad = client.post("/api/import", data={"bestand": (_io.BytesIO(b"geen excel"), "x.xlsx")},
                      content_type="multipart/form-data")
    assert bad.status_code == 400

    o = ownposts.overview(conn, "2026")
    assert o["kpis"]["posts"] == 8
    assert o["kpis"]["followers"] == sum(30 + i for i in range(7))  # collab telt niet mee
    assert o["supermarket_tests"][0]["product"] == "frikandel"
    assert o["groups"]["format"][0]["name"] == "Supermarkttest"  # gesorteerd op mediaan views
    assert any("Snackbar review" in i for i in o["insights"])
    assert ownposts.lifts(conn)["friet"]["lift"] > 1
    assert "frietboer" in ownposts.posted_handles(conn)

    listing = spots.listing(conn)
    poppe = next(s for s in listing["spots"] if s["name"] == "Snackbar de Poppe")
    assert poppe["posted"]["date"] == "2026-01-11"  # genoemd in een eigen caption
    assert next(s for s in listing["spots"] if s["name"] == "Frietboerderij")["place"] == ""
    assert next(s for s in listing["spots"] if s["name"] == "Döner Father")["place"] == "Amsterdam"
    route = spots.routes(conn)[0]
    assert route["stops"][0] == {"name": "Snackbar de Poppe", "place": "Coevorden", "specialty": "broodje lammert",
                                 "text": "Snackbar de Poppe (Coevorden) - broodje lammert", "status": "te proberen"}
    assert route["maps"].startswith("https://www.google.com/maps/dir/") and "Pizza%20Pazza%20Norg" in route["maps"]

    # Opnieuw importeren: geen dubbele posts of tips, en je status blijft staan.
    assert client.patch(f"/api/tips/{poppe['id']}", json={"status": "gepland", "note": "zaterdag"}).status_code == 200
    client.post("/api/import", data={"bestand": (_io.BytesIO(_workbook()), "overzicht.xlsx")},
                content_type="multipart/form-data")
    assert conn.execute("SELECT COUNT(*) FROM own_posts").fetchone()[0] == 8
    again = conn.execute("SELECT status, note FROM spots WHERE name = 'Snackbar de Poppe'").fetchone()
    assert (again["status"], again["note"]) == ("gepland", "zaterdag")
    assert conn.execute("SELECT COUNT(*) FROM routes").fetchone()[0] == 1
    for url in ("/api/mijnposts", "/api/mijnposts?jaar=2026", "/api/tips", "/api/routes", "/api/export/tips.csv",
                "/api/vandaag", "/api/zaken"):
        assert client.get(url).status_code == 200, url
    assert client.post("/api/tips", json={"name": "Nieuwe Zaak", "place": "Gouda"}).status_code == 200
    assert client.post("/api/tips", json={}).status_code == 400


def test_tip_in_radar_and_in_candidates(conn):
    from trendradar import spots

    conn.execute("INSERT INTO spots(name, place, specialty, added_at, updated_at) "
                 "VALUES ('Snackbar de Poppe', 'Coevorden', 'broodje lammert', 'x', 'x')")
    store_posts(conn, [post("pop", "Nieuw op de kaart bij Snackbar De Poppe: broodje met kroket en pizza",
                            platform="tiktok", author="poppefan")], None)
    hits = spots.radar_hits(conn, include_demo=False)
    assert list(hits.values())[0]["posts"] == 1
    cand = {c["id"]: c for c in trends.candidates(conn, include_demo=False)}["tiktok:pop"]
    assert any(r == "Past bij jou: Snackbar de Poppe" for r in cand["reasons"])


def test_feedback_teaches_and_hides(conn):
    from trendradar import taste
    from trendradar.web import app

    store_posts(conn, [post("a", "Nieuw op de kaart: broodje kroket met kaassoufflé", platform="tiktok", author="fan"),
                       post("b", "Nieuw op de kaart: friet met frikandel en kipcorn speciaal", platform="tiktok",
                            author="fan"),
                       post("c", "Nieuw op de kaart bij ons: kroket met pindasaus", platform="tiktok", author="ander")],
                None)
    conn.commit()
    client = app.test_client()
    assert client.post("/api/feedback", json={"post_id": "tiktok:a", "value": 1}).status_code == 200
    assert client.post("/api/feedback", json={"post_id": "tiktok:b", "value": -1}).status_code == 200
    assert client.post("/api/feedback", json={"post_id": "tiktok:b", "value": 5}).status_code == 400
    assert client.get("/api/feedback").get_json() == {"tiktok:a": 1, "tiktok:b": -1}
    prof = taste.profile(conn)
    assert prof.sources["likes"] == 1 and prof.sources["dislikes"] == 1
    assert "maker:tiktok:fan" not in prof  # ♥ en 👎 voor dezelfde maker heffen elkaar op
    assert prof["snack:kroket"] > 0 and prof["snack:frikandel"] < 0
    ids = [c["id"] for c in trends.candidates(conn, include_demo=False)]
    assert "tiktok:a" not in ids and "tiktok:b" not in ids  # al beoordeeld
    cand = next(c for c in trends.candidates(conn, include_demo=False) if c["id"] == "tiktok:c")
    assert "Past bij jou: kroket" in cand["reasons"]
    client.post("/api/feedback", json={"post_id": "tiktok:a", "value": 0})
    assert client.get("/api/feedback").get_json() == {"tiktok:b": -1}
