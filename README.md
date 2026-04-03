# Snackspert - Instagram Recensies naar Google Docs

Verzamelt alle geplaatste recensies van [instagram.com/snackspert](https://instagram.com/snackspert) en slaat elke recensie op als een apart Google Docs-bestand in een Google Drive-map.

## Wat het doet

- Haalt alle posts (recensies) op van het @snackspert Instagram-profiel
- Maakt per recensie een apart Google Docs-bestand aan met:
  - Titel (eerste regel van de caption)
  - Datum, likes, reacties, locatie
  - Volledige recensietekst
  - Hashtags
  - Link naar de originele post en afbeelding
- Slaat alle documenten op in een gedeelde Google Drive-map

## Vereisten

- Python 3.11+
- Een Google Cloud project met de **Google Docs API** en **Google Drive API** ingeschakeld
- Een **service account** met een JSON-sleutelbestand
- De Google Drive-map moet gedeeld zijn met het e-mailadres van het service account

## Installatie

```bash
# Clone de repository
git clone https://github.com/EkeBosman/snackspert.git
cd snackspert

# Maak een virtuele omgeving aan
python -m venv venv
source venv/bin/activate  # Linux/Mac
# of: venv\Scripts\activate  # Windows

# Installeer dependencies
pip install -r requirements.txt
```

## Configuratie

1. **Kopieer het voorbeeld-configuratiebestand:**
   ```bash
   cp .env.example .env
   ```

2. **Google Cloud instellen:**
   - Ga naar [Google Cloud Console](https://console.cloud.google.com/)
   - Maak een nieuw project aan (of gebruik een bestaand project)
   - Schakel de **Google Docs API** en **Google Drive API** in
   - Maak een **service account** aan en download het JSON-sleutelbestand
   - Plaats het bestand in `credentials/service_account.json`

3. **Google Drive-map aanmaken:**
   - Maak een nieuwe map aan in Google Drive (bijv. "Snackspert Recensies")
   - Deel de map met het e-mailadres van het service account (te vinden in het JSON-bestand onder `client_email`)
   - Kopieer het map-ID uit de URL (het deel na `/folders/`)
   - Vul dit ID in bij `GOOGLE_DRIVE_FOLDER_ID` in het `.env`-bestand

4. **Vul het `.env`-bestand in** met de juiste waarden.

## Gebruik

```bash
# Alle recensies ophalen en naar Google Docs schrijven
python main.py

# Maximaal 10 recensies ophalen
python main.py --max-posts 10

# Alleen ophalen zonder naar Google Docs te schrijven (dry-run)
python main.py --dry-run

# Resultaten ook als JSON opslaan
python main.py --output-json recensies.json
```

## Projectstructuur

```
snackspert/
├── main.py                  # Hoofdscript - start hier
├── instagram_scraper.py     # Haalt recensies op van Instagram
├── google_docs_writer.py    # Schrijft recensies naar Google Docs
├── requirements.txt         # Python dependencies
├── .env.example             # Voorbeeld configuratie
├── .gitignore               # Git ignore regels
└── credentials/             # Service account sleutelbestanden (niet in git)
```
