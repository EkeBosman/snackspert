#!/usr/bin/env python3
"""
Snackspert Instagram Reviews → Google Docs

Verzamelt alle recensies van Instagram.com/snackspert en slaat elke
recensie op als een apart Google Docs-bestand in een gedeelde Drive-map.

Gebruik:
    python main.py                  # Alle recensies ophalen
    python main.py --max-posts 10   # Maximaal 10 recensies
    python main.py --dry-run        # Alleen ophalen, niet naar Google Docs
"""

import argparse
import json
import os
import sys
from pathlib import Path

from dotenv import load_dotenv

from instagram_scraper import scrape_reviews
from google_docs_writer import GoogleDocsWriter


def main():
    load_dotenv()

    parser = argparse.ArgumentParser(
        description="Verzamel Snackspert Instagram-recensies naar Google Docs"
    )
    parser.add_argument(
        "--max-posts",
        type=int,
        default=int(os.getenv("MAX_POSTS", "0")),
        help="Maximaal aantal posts om op te halen (0 = alles)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Alleen recensies ophalen, niet naar Google Docs schrijven",
    )
    parser.add_argument(
        "--output-json",
        type=str,
        default=None,
        help="Sla de resultaten op als JSON-bestand",
    )
    args = parser.parse_args()

    # --- Stap 1: Instagram recensies ophalen ---
    print("=" * 60)
    print("SNACKSPERT - Instagram Recensies → Google Docs")
    print("=" * 60)
    print("\n📸 Stap 1: Instagram recensies ophalen...\n")

    ig_username = os.getenv("INSTAGRAM_USERNAME", "snackspert")
    ig_login = os.getenv("INSTAGRAM_LOGIN_USERNAME")
    ig_password = os.getenv("INSTAGRAM_LOGIN_PASSWORD")

    reviews = scrape_reviews(
        username=ig_username,
        login_username=ig_login if ig_login else None,
        login_password=ig_password if ig_password else None,
        max_posts=args.max_posts,
    )

    if not reviews:
        print("\nGeen recensies gevonden. Script gestopt.")
        sys.exit(1)

    # --- Optioneel: JSON export ---
    if args.output_json:
        json_data = [
            {
                "post_id": r.post_id,
                "date": r.date.isoformat(),
                "title": r.title,
                "caption": r.caption,
                "likes": r.likes,
                "comments_count": r.comments_count,
                "image_url": r.image_url,
                "permalink": r.permalink,
                "hashtags": r.hashtags,
                "location": r.location,
            }
            for r in reviews
        ]
        Path(args.output_json).write_text(
            json.dumps(json_data, ensure_ascii=False, indent=2)
        )
        print(f"\n✓ JSON export opgeslagen: {args.output_json}")

    # --- Stap 2: Google Docs aanmaken ---
    if args.dry_run:
        print("\n🔍 Dry-run modus: geen Google Docs aangemaakt.")
        print(f"   {len(reviews)} recensies zouden worden verwerkt.")
        return

    print("\n📄 Stap 2: Google Docs-bestanden aanmaken...\n")

    sa_file = os.getenv("GOOGLE_SERVICE_ACCOUNT_FILE", "credentials/service_account.json")
    folder_id = os.getenv("GOOGLE_DRIVE_FOLDER_ID")

    if not folder_id:
        print("✗ GOOGLE_DRIVE_FOLDER_ID is niet ingesteld in .env")
        print("  Maak een map aan in Google Drive en kopieer het ID")
        print("  (het deel na /folders/ in de URL)")
        sys.exit(1)

    if not Path(sa_file).exists():
        print(f"✗ Service account bestand niet gevonden: {sa_file}")
        print("  Download het JSON-sleutelbestand van de Google Cloud Console")
        print("  en plaats het in de credentials/ map.")
        sys.exit(1)

    writer = GoogleDocsWriter(
        service_account_file=sa_file,
        folder_id=folder_id,
    )
    results = writer.write_all_reviews(reviews)

    # --- Samenvatting ---
    print("\n" + "=" * 60)
    print("SAMENVATTING")
    print("=" * 60)
    succeeded = [r for r in results if r.get("url")]
    failed = [r for r in results if not r.get("url")]
    print(f"  Totaal recensies:   {len(reviews)}")
    print(f"  Succesvol:          {len(succeeded)}")
    print(f"  Mislukt:            {len(failed)}")

    if succeeded:
        print(f"\n  Alle documenten staan in de Google Drive-map:")
        print(f"  https://drive.google.com/drive/folders/{folder_id}")


if __name__ == "__main__":
    main()
