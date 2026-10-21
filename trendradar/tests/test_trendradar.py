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
    assert "#bitterbalijs" in names
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
