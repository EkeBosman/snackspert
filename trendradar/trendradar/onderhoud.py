"""Onderhoud: een wekelijkse back-up en het opruimen van oude posts.

Back-up: je lijst, tips, routes, notities en ♥/👎 staan alleen in de database op
je Chromebook. Eens per week maakt de tool een kopie. Het liefst in de map
'Snackspert Trendradar' in je Google Drive: die map moet je één keer delen met
Linux (rechtsklik in Bestanden > 'Delen met Linux'). Kan dat niet, dan komt de
kopie in de map data/backups naast de database.

Opruimen: posts ouder dan een half jaar (instelbaar) zeggen niets meer over
trends en maken de tool trager. Wat je bewaard of beoordeeld hebt, blijft staan.
"""
from __future__ import annotations

import sqlite3
from datetime import timedelta
from pathlib import Path

from . import config, db

DRIVE_FOLDER = "Snackspert Trendradar"
# Zo heet je Google Drive in Linux op een Chromebook, na 'Delen met Linux'.
DRIVE_CANDIDATES = [Path("/mnt/chromeos/GoogleDrive/MyDrive") / DRIVE_FOLDER,
                    Path("/mnt/chromeos/GoogleDrive/MijnDrive") / DRIVE_FOLDER]
KEEP_BACKUPS = 8


def backup_dir(settings: dict) -> tuple[Path, bool]:
    """(map, is_drive). Een zelf ingestelde map gaat voor, dan Google Drive, dan lokaal."""
    own = (settings.get("backup_map") or "").strip()
    if own:
        return Path(own).expanduser(), "GoogleDrive" in own
    for p in DRIVE_CANDIDATES:
        if p.is_dir():
            return p, True
    return config.DATA_DIR / "backups", False


def backup_due(conn, settings: dict) -> bool:
    last = db.get_state(conn, "backup_laatst")
    days = max(1, int(settings.get("backup_dagen", 7) or 7))
    return not last or db.now() - db.parse_iso(last["at"]) >= timedelta(days=days) - timedelta(hours=1)


def make_backup(settings: dict) -> dict:
    """Kopie van de hele database (ook terwijl de tool draait), de oudste weg na 8 stuks."""
    folder, drive = backup_dir(settings)
    folder.mkdir(parents=True, exist_ok=True)
    target = folder / f"trendradar-{db.now().strftime('%Y-%m-%d-%H%M')}.db"
    tmp = target.with_suffix(".db.deel")
    src = sqlite3.connect(config.DB_PATH)
    try:
        dst = sqlite3.connect(tmp)
        with dst:
            src.backup(dst)
        dst.close()
    finally:
        src.close()
    tmp.replace(target)  # pas als hij compleet is, krijgt hij zijn echte naam
    old = sorted(folder.glob("trendradar-*.db"))[:-KEEP_BACKUPS]
    for p in old:
        p.unlink(missing_ok=True)
    info = {"at": db.iso(db.now()), "path": str(target), "drive": drive,
            "mb": round(target.stat().st_size / 1e6, 1)}
    with db.session() as conn:
        db.set_state(conn, "backup_laatst", info)
    return info


def status(conn, settings: dict) -> dict:
    folder, drive = backup_dir(settings)
    return {"last": db.get_state(conn, "backup_laatst"), "folder": str(folder), "drive": drive,
            "drive_folder": DRIVE_FOLDER}


def cleanup(conn, settings: dict) -> dict:
    """Verwijder oude posts, metingen, nieuws en rondes. Bewaarde en beoordeelde posts blijven."""
    months = int(settings.get("bewaar_maanden", 6) or 0)
    if months <= 0:
        return {"posts": 0}
    cutoff = db.iso(db.now() - timedelta(days=30 * months))
    keep = ("id NOT IN (SELECT ref FROM watchlist WHERE kind = 'post') "
            "AND id NOT IN (SELECT post_id FROM feedback)")
    n_posts = conn.execute(f"DELETE FROM posts WHERE posted_at < ? AND {keep}", (cutoff,)).rowcount
    conn.execute("DELETE FROM metric_snapshots WHERE post_id NOT IN (SELECT id FROM posts)")
    n_news = conn.execute("DELETE FROM news WHERE published_at < ?", (cutoff,)).rowcount
    n_runs = conn.execute("DELETE FROM runs WHERE started_at < ? AND status != 'bezig'", (cutoff,)).rowcount
    db.set_state(conn, "opruimen_laatst", {"at": db.iso(db.now()), "posts": n_posts, "news": n_news,
                                           "runs": n_runs})
    return {"posts": n_posts, "news": n_news, "runs": n_runs}


def cleanup_due(conn) -> bool:
    last = db.get_state(conn, "opruimen_laatst")
    return not last or db.now() - db.parse_iso(last["at"]) >= timedelta(days=7)
