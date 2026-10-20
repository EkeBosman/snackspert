"""Start de Trendradar:  python -m trendradar  (en open http://localhost:8050)."""
from __future__ import annotations

import argparse
import logging
import threading
import time
import webbrowser

from . import collector, config, db

log = logging.getLogger("trendradar")


def scheduler_loop(stop: threading.Event) -> None:
    """Kijkt elke minuut of er een ronde moet draaien.

    Stond de computer uit of sliep de Chromebook, dan haalt hij de gemiste
    ronde direct in bij het opstarten.
    """
    while not stop.is_set():
        try:
            with db.session() as conn:
                settings = db.get_settings(conn)
                is_due = collector.due(conn, settings)
            if is_due and not collector.is_running():
                collector.run_once("schema")
        except Exception:  # noqa: BLE001 - de planner mag nooit stoppen
            log.exception("Fout in de planner")
        stop.wait(60)


def main() -> None:
    parser = argparse.ArgumentParser(description="Snackspert Trendradar")
    parser.add_argument("--port", type=int, default=8050)
    parser.add_argument("--geen-browser", action="store_true", help="browser niet automatisch openen")
    parser.add_argument("--geen-planner", action="store_true", help="niet automatisch ophalen")
    parser.add_argument("--eenmalig", action="store_true", help="één ophaalronde draaien en stoppen")
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s",
                        datefmt="%H:%M:%S")
    config.load_env()
    db.init()
    with db.session() as conn:
        # Een ronde die 'bezig' bleef staan is door afsluiten onderbroken.
        conn.execute("UPDATE runs SET status = 'fout', finished_at = started_at "
                     "WHERE status = 'bezig'")

    if args.eenmalig:
        print(collector.run_once("handmatig", force_supermarkets=True))
        return

    stop = threading.Event()
    if not args.geen_planner:
        threading.Thread(target=scheduler_loop, args=(stop,), daemon=True).start()

    url = f"http://localhost:{args.port}"
    print(f"\n  Snackspert Trendradar draait op {url}\n  Stoppen: Ctrl+C\n")
    if not args.geen_browser:
        threading.Timer(1.5, lambda: webbrowser.open(url)).start()

    from .web import app
    try:
        app.run(host="127.0.0.1", port=args.port, debug=False, use_reloader=False, threaded=True)
    finally:
        stop.set()
        time.sleep(0.1)


if __name__ == "__main__":
    main()
