"""SQLite-opslag. Eén bestand in data/, geen server nodig."""
from __future__ import annotations

import json
import sqlite3
import threading
from contextlib import contextmanager
from datetime import datetime, timezone

from . import config

SCHEMA = """
CREATE TABLE IF NOT EXISTS posts (
    id            TEXT PRIMARY KEY,          -- platform:eigen_id
    platform      TEXT NOT NULL,             -- instagram | tiktok | facebook | nieuws
    source_id     INTEGER,
    author        TEXT,
    author_name   TEXT,
    author_followers INTEGER,
    text          TEXT,
    url           TEXT,
    thumbnail     TEXT,
    location      TEXT,
    posted_at     TEXT NOT NULL,             -- ISO, UTC
    fetched_at    TEXT NOT NULL,
    first_fetched TEXT,
    remeasured_at TEXT,                      -- laatste herhaalmeting van een snelle post
    likes         INTEGER DEFAULT 0,
    comments      INTEGER DEFAULT 0,
    shares        INTEGER DEFAULT 0,
    views         INTEGER DEFAULT 0,
    hashtags      TEXT DEFAULT '[]',
    mentions      TEXT DEFAULT '[]',
    relevance     REAL DEFAULT 0,
    nl_score      REAL DEFAULT 0,
    categories    TEXT DEFAULT '[]',
    brands        TEXT DEFAULT '[]',
    products      TEXT DEFAULT '[]',
    places        TEXT DEFAULT '[]',
    phrases       TEXT DEFAULT '[]',
    city          TEXT,
    sentiment     TEXT,
    summary       TEXT,
    ai_done       INTEGER DEFAULT 0,
    demo          INTEGER DEFAULT 0
);
CREATE INDEX IF NOT EXISTS idx_posts_posted ON posts(posted_at);
CREATE INDEX IF NOT EXISTS idx_posts_platform ON posts(platform);

CREATE TABLE IF NOT EXISTS metric_snapshots (
    post_id    TEXT NOT NULL,
    taken_at   TEXT NOT NULL,
    likes      INTEGER, comments INTEGER, shares INTEGER, views INTEGER,
    PRIMARY KEY (post_id, taken_at)
);

CREATE TABLE IF NOT EXISTS sources (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    platform    TEXT NOT NULL,               -- instagram | tiktok | facebook
    kind        TEXT NOT NULL,               -- hashtag | account | zoekterm
    value       TEXT NOT NULL,
    status      TEXT NOT NULL DEFAULT 'actief',  -- actief | kandidaat | gepauzeerd | afgewezen | ongeldig
    origin      TEXT NOT NULL DEFAULT 'start',   -- start | ontdekt | handmatig
    reason      TEXT,
    priority    REAL DEFAULT 1.0,
    added_at    TEXT NOT NULL,
    last_fetched TEXT,
    fetch_count INTEGER DEFAULT 0,
    last_results INTEGER DEFAULT 0,
    last_relevant INTEGER DEFAULT 0,
    yield_score REAL,                        -- aandeel relevante posts, voortschrijdend
    empty_streak INTEGER DEFAULT 0,          -- opeenvolgende rondes zonder resultaat
    last_error  TEXT,
    next_due    TEXT,                        -- eerder ophalen heeft geen zin (spaart geld)
    last_new    INTEGER DEFAULT 0,           -- nieuwe posts in de laatste ronde
    cost_usd    REAL DEFAULT 0,              -- totaal uitgegeven aan deze bron
    useful_total INTEGER DEFAULT 0,          -- totaal nieuwe relevante posts
    demo        INTEGER DEFAULT 0,
    UNIQUE (platform, kind, value)
);

CREATE TABLE IF NOT EXISTS runs (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    started_at  TEXT NOT NULL,
    finished_at TEXT,
    status      TEXT NOT NULL DEFAULT 'bezig',   -- bezig | klaar | fout | deels
    trigger     TEXT,
    results     INTEGER DEFAULT 0,
    new_posts   INTEGER DEFAULT 0,
    cost_usd    REAL DEFAULT 0,
    ai_cost_usd REAL DEFAULT 0,
    log         TEXT DEFAULT '[]'
);

CREATE TABLE IF NOT EXISTS spend (
    id        INTEGER PRIMARY KEY AUTOINCREMENT,
    at        TEXT NOT NULL,
    kind      TEXT NOT NULL,      -- apify | ai
    platform  TEXT,
    usd       REAL NOT NULL,
    detail    TEXT
);

CREATE TABLE IF NOT EXISTS graph_hashtags (
    hashtag     TEXT PRIMARY KEY,
    hashtag_id  TEXT,
    first_used  TEXT NOT NULL      -- Meta telt 30 unieke hashtags per 7 dagen
);

CREATE TABLE IF NOT EXISTS products (
    id          TEXT PRIMARY KEY,  -- winkel:eigen_id
    store       TEXT NOT NULL,
    name        TEXT NOT NULL,
    brand       TEXT,
    category    TEXT,
    size        TEXT,
    price       REAL,
    url         TEXT,
    image       TEXT,
    first_seen  TEXT NOT NULL,
    last_seen   TEXT NOT NULL,
    is_new      INTEGER DEFAULT 0,  -- 1 = na de nulmeting verschenen
    relevant    INTEGER DEFAULT 1,  -- 1 = snack/streetfood-relevant volgens de woordenlijsten
    demo        INTEGER DEFAULT 0
);

CREATE TABLE IF NOT EXISTS news (
    id           TEXT PRIMARY KEY,
    title        TEXT NOT NULL,
    url          TEXT,
    outlet       TEXT,
    published_at TEXT NOT NULL,
    query        TEXT,
    fetched_at   TEXT NOT NULL,
    demo         INTEGER DEFAULT 0
);

CREATE TABLE IF NOT EXISTS reviewed (
    slug  TEXT PRIMARY KEY,
    name  TEXT NOT NULL,
    url   TEXT,
    norm  TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS settings (
    key   TEXT PRIMARY KEY,
    value TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS state (
    key   TEXT PRIMARY KEY,
    value TEXT NOT NULL
);
"""

_lock = threading.RLock()
_local = threading.local()


def now() -> datetime:
    return datetime.now(timezone.utc)


def iso(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def parse_iso(value: str) -> datetime:
    return datetime.strptime(value, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)


def connect() -> sqlite3.Connection:
    config.DATA_DIR.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(config.DB_PATH, timeout=30, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


@contextmanager
def session():
    """Eén verbinding per blok; de lock voorkomt dat de ophaal-thread en de
    webserver tegelijk schrijven.

    Een session binnen een session (in dezelfde thread) gebruikt dezelfde
    verbinding. Een tweede verbinding zou wachten op de schrijfrechten van de
    eerste en na 30 seconden opgeven met 'database is locked'.
    """
    with _lock:
        outer = getattr(_local, "conn", None)
        if outer is not None:
            yield outer
            return
        conn = connect()
        _local.conn = conn
        try:
            yield conn
            conn.commit()
        finally:
            _local.conn = None
            conn.close()


# Kolommen die later zijn bijgekomen. Bestaande databases krijgen ze erbij.
MIGRATIONS = [
    ("posts", "first_fetched", "TEXT"),
    ("posts", "remeasured_at", "TEXT"),
    ("products", "relevant", "INTEGER DEFAULT 1"),
    ("products", "size", "TEXT"),
    ("sources", "next_due", "TEXT"),
    ("sources", "last_new", "INTEGER DEFAULT 0"),
    ("sources", "cost_usd", "REAL DEFAULT 0"),
    ("sources", "useful_total", "INTEGER DEFAULT 0"),
]


def init() -> None:
    with session() as conn:
        conn.executescript(SCHEMA)
        for table, column, kind in MIGRATIONS:
            cols = {r["name"] for r in conn.execute(f"PRAGMA table_info({table})")}
            if column not in cols:
                conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {kind}")


# --- instellingen ---------------------------------------------------------

def get_settings(conn) -> dict:
    values = dict(config.DEFAULTS)
    for row in conn.execute("SELECT key, value FROM settings"):
        values[row["key"]] = json.loads(row["value"])
    return values


def set_settings(conn, updates: dict) -> None:
    for key, value in updates.items():
        if key not in config.DEFAULTS:
            continue
        conn.execute(
            "INSERT INTO settings(key, value) VALUES(?, ?) "
            "ON CONFLICT(key) DO UPDATE SET value = excluded.value",
            (key, config.dumps(value)),
        )


def get_state(conn, key: str, default=None):
    row = conn.execute("SELECT value FROM state WHERE key = ?", (key,)).fetchone()
    return json.loads(row["value"]) if row else default


def set_state(conn, key: str, value) -> None:
    conn.execute(
        "INSERT INTO state(key, value) VALUES(?, ?) "
        "ON CONFLICT(key) DO UPDATE SET value = excluded.value",
        (key, config.dumps(value)),
    )


def row_to_dict(row: sqlite3.Row) -> dict:
    out = dict(row)
    for key in ("hashtags", "mentions", "categories", "brands", "products",
                "places", "phrases", "log"):
        if key in out and isinstance(out[key], str):
            try:
                out[key] = json.loads(out[key])
            except ValueError:
                out[key] = []
    return out
