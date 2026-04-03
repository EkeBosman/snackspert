"""
Google Docs Writer voor Snackspert recensies.

Maakt per recensie een apart Google Docs-bestand aan in een
opgegeven Google Drive-map.
"""

from google.oauth2 import service_account
from googleapiclient.discovery import build

from instagram_scraper import Review

SCOPES = [
    "https://www.googleapis.com/auth/documents",
    "https://www.googleapis.com/auth/drive.file",
]


class GoogleDocsWriter:
    """Schrijft recensies naar individuele Google Docs in een Drive-map."""

    def __init__(self, service_account_file: str, folder_id: str):
        """
        Args:
            service_account_file: Pad naar het service account JSON-bestand.
            folder_id: Google Drive map-ID voor de recensie-documenten.
        """
        credentials = service_account.Credentials.from_service_account_file(
            service_account_file, scopes=SCOPES
        )
        self.docs_service = build("docs", "v1", credentials=credentials)
        self.drive_service = build("drive", "v3", credentials=credentials)
        self.folder_id = folder_id

    def create_review_doc(self, review: Review) -> str:
        """
        Maak een Google Docs-bestand aan voor één recensie.

        Args:
            review: Het Review-object om als document op te slaan.

        Returns:
            De URL van het aangemaakte Google Docs-document.
        """
        doc_title = f"Snackspert - {review.title}"

        # Stap 1: Maak een leeg document aan
        doc = self.docs_service.documents().create(
            body={"title": doc_title}
        ).execute()
        doc_id = doc["documentId"]

        # Stap 2: Verplaats naar de juiste Drive-map
        self.drive_service.files().update(
            fileId=doc_id,
            addParents=self.folder_id,
            removeParents="root",
            fields="id, parents",
        ).execute()

        # Stap 3: Vul het document met de recensie-inhoud
        requests = self._build_document_body(review)
        if requests:
            self.docs_service.documents().batchUpdate(
                documentId=doc_id, body={"requests": requests}
            ).execute()

        doc_url = f"https://docs.google.com/document/d/{doc_id}/edit"
        return doc_url

    def _build_document_body(self, review: Review) -> list[dict]:
        """Bouw de Google Docs API-requests om het document te vullen."""
        requests = []
        # We bouwen het document van achteren naar voren op (insertText
        # werkt met index 1 = begin van document). Door omgekeerd in te
        # voegen hoeven we geen running index bij te houden.
        sections = []

        # --- Sectie: Header ---
        sections.append({
            "text": f"{review.title}\n",
            "style": "HEADING_1",
        })

        # --- Sectie: Metadata ---
        meta_lines = [
            f"Datum: {review.date.strftime('%d %B %Y')}",
            f"Likes: {review.likes}",
            f"Reacties: {review.comments_count}",
        ]
        if review.location:
            meta_lines.append(f"Locatie: {review.location}")
        meta_lines.append(f"Instagram: {review.permalink}")
        sections.append({
            "text": "\n".join(meta_lines) + "\n\n",
            "style": "NORMAL_TEXT",
        })

        # --- Sectie: Recensie tekst ---
        sections.append({
            "text": "Recensie\n",
            "style": "HEADING_2",
        })
        sections.append({
            "text": (review.caption or "(Geen tekst)") + "\n\n",
            "style": "NORMAL_TEXT",
        })

        # --- Sectie: Hashtags ---
        if review.hashtags:
            sections.append({
                "text": "Hashtags\n",
                "style": "HEADING_2",
            })
            sections.append({
                "text": " ".join(f"#{tag}" for tag in review.hashtags) + "\n",
                "style": "NORMAL_TEXT",
            })

        # --- Sectie: Afbeelding link ---
        sections.append({
            "text": "\nAfbeelding\n",
            "style": "HEADING_2",
        })
        sections.append({
            "text": review.image_url + "\n",
            "style": "NORMAL_TEXT",
        })

        # Bouw de requests op
        index = 1  # Start na de impliciete newline
        for section in sections:
            text = section["text"]
            requests.append({
                "insertText": {
                    "location": {"index": index},
                    "text": text,
                }
            })
            # Pas styling toe
            style_name = section["style"]
            if style_name != "NORMAL_TEXT":
                requests.append({
                    "updateParagraphStyle": {
                        "range": {
                            "startIndex": index,
                            "endIndex": index + len(text),
                        },
                        "paragraphStyle": {
                            "namedStyleType": style_name,
                        },
                        "fields": "namedStyleType",
                    }
                })
            index += len(text)

        return requests

    def write_all_reviews(self, reviews: list[Review]) -> list[dict]:
        """
        Schrijf alle recensies naar individuele Google Docs-bestanden.

        Args:
            reviews: Lijst van Review-objecten.

        Returns:
            Lijst van dicts met {title, url} per aangemaakt document.
        """
        results = []
        total = len(reviews)

        for i, review in enumerate(reviews, 1):
            print(f"  [{i}/{total}] Aanmaken: {review.title[:50]}...")
            try:
                url = self.create_review_doc(review)
                results.append({"title": review.title, "url": url})
                print(f"           ✓ {url}")
            except Exception as e:
                print(f"           ✗ Fout: {e}")
                results.append({"title": review.title, "url": None, "error": str(e)})

        succeeded = sum(1 for r in results if r.get("url"))
        print(f"\n✓ {succeeded}/{total} documenten aangemaakt")
        return results
