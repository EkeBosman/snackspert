# Snackspert - Recensies naar Google Docs

Verzamelt alle recensies van [snackspert.nl/restaurant](https://snackspert.nl/restaurant) en slaat elke recensie op als een apart Google Docs-bestand in een Google Drive-map. Inclusief het aantal sterren.

## Wat het doet

- Haalt alle restaurants op via de WordPress REST API van snackspert.nl
- Scrapet elke restaurantpagina voor de recensietekst en sterrenbeoordeling
- Maakt per recensie een apart Google Docs-bestand aan met:
  - Restaurantnaam
  - Sterrenbeoordeling (bijv. 4.5/5)
  - Adres
  - Volledige recensietekst
  - Link naar de afbeelding
  - Link naar de originele pagina
- Slaat alle documenten op in een Google Drive-map

## Gebruik (Chromebook / Google Colab)

1. Ga naar [colab.research.google.com](https://colab.research.google.com)
2. Klik op **Bestand > Uploaden** en upload `snackspert_recensies.ipynb`
3. Voer de stappen uit door steeds op het **play-knopje** te klikken:
   - **Stap 1**: Installeert automatisch de packages
   - **Stap 2**: Log in met je Google-account (pop-up)
   - **Stap 3**: Pas eventueel de instellingen aan
   - **Stap 4**: Haalt alle recensies op van snackspert.nl (~700 restaurants)
   - **Stap 5**: Maakt de Google Docs-bestanden aan
   - **Stap 6**: Toont een overzicht met scores

4. De documenten verschijnen automatisch in een map **"Snackspert Recensies"** op je Google Drive

### Let op
- Stap 4 kan 10-30 minuten duren (er zijn ~700 restaurants)
- Je kunt `MAX_RECENSIES` instellen op bijv. `10` om eerst te testen

## Projectstructuur

```
snackspert/
├── snackspert_recensies.ipynb  # Google Colab notebook
├── requirements.txt            # Python dependencies
├── README.md                   # Dit bestand
└── .gitignore                  # Git ignore regels
```
