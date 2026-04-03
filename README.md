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
- Slaat alle documenten op in een Google Drive-map

---

## Chromebook / Google Colab (aanbevolen)

De makkelijkste manier om dit te gebruiken is via **Google Colab** - werkt direct in je browser, geen installatie nodig.

### Stappen

1. Open het bestand `snackspert_recensies.ipynb` in Google Colab:
   - Ga naar [colab.research.google.com](https://colab.research.google.com)
   - Klik op **Bestand > Uploaden** en upload `snackspert_recensies.ipynb`
   - Of open het direct vanuit GitHub via **Bestand > Openen vanuit GitHub**

2. Voer de cellen stap voor stap uit (klik op het play-knopje of druk `Shift+Enter`):
   - **Stap 1**: Installeert automatisch de benodigde packages
   - **Stap 2**: Log in met je Google-account (pop-up)
   - **Stap 3**: Pas eventueel de instellingen aan
   - **Stap 4**: Haalt de recensies op van Instagram
   - **Stap 5**: Maakt de Google Docs-bestanden aan
   - **Stap 6**: Toont een overzicht van alle documenten

3. De documenten verschijnen automatisch in een map **"Snackspert Recensies"** op je Google Drive

### Voordelen van Colab
- Geen Python-installatie nodig
- Geen service account nodig (je logt in met je eigen Google-account)
- Werkt op elk apparaat met een browser (Chromebook, tablet, etc.)
- Google Drive-map wordt automatisch aangemaakt

---

## Lokale installatie (geavanceerd)

Voor wie het liever lokaal draait (Linux, Mac, Windows).

### Vereisten

- Python 3.11+
- Een Google Cloud project met de **Google Docs API** en **Google Drive API** ingeschakeld
- Een **service account** met een JSON-sleutelbestand

### Installatie

```bash
git clone https://github.com/EkeBosman/snackspert.git
cd snackspert
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### Configuratie

1. `cp .env.example .env`
2. Google Cloud instellen:
   - Schakel de **Google Docs API** en **Google Drive API** in via [Google Cloud Console](https://console.cloud.google.com/)
   - Maak een **service account** aan en download het JSON-sleutelbestand
   - Plaats het in `credentials/service_account.json`
3. Maak een Google Drive-map aan en deel deze met het service account e-mailadres
4. Vul `GOOGLE_DRIVE_FOLDER_ID` in het `.env`-bestand in

### Gebruik

```bash
python main.py                  # Alle recensies
python main.py --max-posts 10   # Maximaal 10
python main.py --dry-run        # Test zonder Google Docs
python main.py --output-json recensies.json  # Export als JSON
```

---

## Projectstructuur

```
snackspert/
├── snackspert_recensies.ipynb  # Google Colab notebook (aanbevolen)
├── main.py                     # Lokaal hoofdscript
├── instagram_scraper.py        # Instagram scraper module
├── google_docs_writer.py       # Google Docs writer module
├── requirements.txt            # Python dependencies
├── .env.example                # Voorbeeld configuratie (lokaal)
└── .gitignore                  # Git ignore regels
```
