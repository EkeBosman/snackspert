# Snackspert App

iPhone-app voor Snackspert.nl - vind alle snackbar-recensies op de kaart, filter op categorie, en lees reviews.

## Functies

- **Kaartweergave**: Alle ~700 restaurants op een interactieve kaart met markers
- **Lijstweergave**: Zoek en blader door alle restaurants
- **Categoriefilter**: Filter op eetcategorie (Pizza, Shoarma, Frietpatat, etc.)
- **Restaurant detail**: Bekijk recensie, sterren, adres, mini-kaart, en navigeer erheen
- **Live data**: Haalt alles op van snackspert.nl via de WordPress REST API

## Installatie & Starten

### Vereisten

- Node.js 18+ (installeer via [nodejs.org](https://nodejs.org))
- Expo Go app op je iPhone (download uit de App Store)
- Een Google Maps API key (voor de kaart op iOS)

### Stappen

```bash
# 1. Ga naar de app-map
cd snackspert-app

# 2. Installeer dependencies
npm install

# 3. Start de development server
npx expo start
```

Er verschijnt een QR-code in je terminal. Scan deze met de **Camera-app** op je iPhone - de app opent automatisch in Expo Go.

### Google Maps API Key

Voor de kaart heb je een Google Maps API key nodig:

1. Ga naar [console.cloud.google.com](https://console.cloud.google.com)
2. Maak een nieuw project aan (of gebruik een bestaand project)
3. Activeer de **Maps SDK for iOS** API
4. Maak een API key aan onder **Credentials**
5. Vul de key in bij `app.json` → `expo.ios.config.googleMapsApiKey`

### Chromebook

Op een Chromebook kun je de app ontwikkelen via Linux:

```bash
# Linux terminal openen op Chromebook
# Node.js installeren
sudo apt update && sudo apt install nodejs npm

# Daarna bovenstaande stappen volgen
```

Of gebruik [Expo Snack](https://snack.expo.dev) in de browser.

## Projectstructuur

```
snackspert-app/
├── app/                    # Schermen (expo-router file-based routing)
│   ├── _layout.tsx         # Root navigatie
│   ├── (tabs)/             # Tab-navigatie
│   │   ├── _layout.tsx     # Tab bar configuratie
│   │   ├── index.tsx       # Kaart-scherm
│   │   └── lijst.tsx       # Lijst-scherm
│   └── restaurant/
│       └── [id].tsx        # Restaurant detail-scherm
├── components/             # Herbruikbare componenten
│   ├── CategoryFilter.tsx  # Horizontale categorie-chips
│   ├── RestaurantCard.tsx  # Restaurant kaart voor de lijst
│   └── StarRating.tsx      # Sterren-weergave
├── services/
│   └── api.ts              # WordPress REST API communicatie
├── hooks/
│   └── useRestaurants.ts   # Data management hook
├── types/
│   └── index.ts            # TypeScript types
├── constants/
│   └── theme.ts            # Kleuren, spacing, categorieën
├── app.json                # Expo configuratie
└── package.json            # Dependencies
```

## Bouwen voor de App Store

Om een echte iOS app te bouwen (zonder Expo Go):

```bash
# EAS CLI installeren
npm install -g eas-cli

# Inloggen bij Expo
eas login

# iOS build starten (in de cloud, geen Mac nodig!)
eas build --platform ios

# Submitten naar de App Store
eas submit --platform ios
```

Hiervoor heb je een Apple Developer Account nodig ($99/jaar).

## Data

De app haalt live data op van:
- **REST API**: `snackspert.nl/wp-json/wp/v2/restaurant` (restaurant-lijst)
- **Pagina scraping**: Individuele restaurantpagina's voor reviews, sterren, coördinaten

~700 restaurants in heel Nederland met categorieën zoals:
Aziatisch, Bakker, Broodjes, Frietpatat, Grieks, Hamburger, Hotdogs, Italiaans, Kroket, Mexicaans, Midden-Oosters, Pizza, Shoarma/döner, Snackbar, Spaans, Spareribs, Wraps
