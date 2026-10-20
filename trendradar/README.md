# Snackspert Trendradar

Een tool die je lokaal draait en die Nederlandse posts over snacks, streetfood en nieuwe supermarktproducten volgt op Instagram, TikTok en Facebook. Hij laat zien wat er stijgt in de periodes **nu (6 uur), 24 uur, 3 dagen en 7 dagen**.

Zonder sleutels start hij in **demomodus**, met verzonnen voorbeelddata. Zo kun je de interface meteen bekijken.

## Wat zit erin

| Tabblad | Wat je ziet |
|---|---|
| **Trends** | De stijgers: hashtags, gerechten, producten, merken, zaken, steden en woordcombinaties, met groei ten opzichte van de periodes ervoor. Daarnaast nieuw opgedoken onderwerpen, posts die nu hard gaan, het volume per platform en de verdeling over categorieën. Klik op een onderwerp voor het verloop en de populairste posts. |
| **Posts** | Alle relevante posts, met zoeken, filteren en sorteren. |
| **Supermarkt** | Nieuwe producten in het schap (AH en Jumbo), de producten waar het meest over gepost wordt, en nieuws over nieuwe producten. |
| **Zaken & steden** | Eetzaken en foodtrucks die genoemd worden, met een **reviewkandidaat**-label als ze nog niet op snackspert.nl staan. Plus een kaart met steden. |
| **Bronnen** | De gevolgde hashtags, accounts en zoektermen. De tool **voegt zelf bronnen toe** die in meerdere relevante posts opduiken, en pauzeert bronnen die weinig opleveren. |
| **Budget & instellingen** | De kosten deze maand, een prognose, alle instellingen, de status van de koppelingen en een logboek per ophaalronde. |

Je kunt de trends en de posts exporteren als CSV, bijvoorbeeld voor Google Sheets.

## Starten op een Chromebook

1. Zet Linux aan als dat nog niet gebeurd is: **Instellingen → Geavanceerd → Ontwikkelaars → Linux-ontwikkelomgeving**.
2. Open de Terminal-app en installeer Python (eenmalig):
   ```bash
   sudo apt update && sudo apt install -y python3 python3-venv git
   ```
3. Haal de code op en start de tool:
   ```bash
   git clone https://github.com/EkeBosman/snackspert.git
   cd snackspert/trendradar
   ./start.sh
   ```
4. Open **http://localhost:8050** in Chrome.

Het startscript installeert de eerste keer alles wat nodig is en maakt een leeg `.env`-bestand aan.

Stoppen doe je met **Ctrl+C** in de terminal. Starten doe je daarna steeds met `./start.sh` vanuit de map `trendradar`.

> **Let op:** de tool haalt alleen nieuwe posts op zolang hij draait. Was hij uit, dan haalt hij de gemiste ronde in zodra je hem weer start.

Op een Mac of onder Linux werkt het precies zo. Op Windows gebruik je in plaats van `./start.sh`:

```
python -m venv .venv
.venv\Scripts\pip install -r requirements.txt
.venv\Scripts\python -m trendradar
```

## Sleutels instellen (in `.env`)

Open het bestand `trendradar/.env` in een teksteditor. Op de Chromebook kan dat met de app Text, of met `nano .env` in de terminal. Alle sleutels zijn optioneel. Herstart de tool nadat je iets hebt gewijzigd.

### 1. Apify: TikTok, Facebook en extra Instagram (betaald)

1. Maak een account op [apify.com](https://apify.com).
2. Kopieer je token via **Settings → API & Integrations** en zet het achter `APIFY_TOKEN=`.
3. Controleer bij de actors die de tool gebruikt de **Pricing**-tab, en neem de prijzen over onder **Budget & instellingen** als ze afwijken:
   - [`apify/instagram-hashtag-scraper`](https://apify.com/apify/instagram-hashtag-scraper) en `apify/instagram-scraper`
   - [`clockworks/tiktok-scraper`](https://apify.com/clockworks/tiktok-scraper)
   - [`apify/facebook-posts-scraper`](https://apify.com/apify/facebook-posts-scraper)

Wil je een andere of goedkopere actor gebruiken? Dat pas je aan in `trendradar/sources/apify.py`, bovenaan in `ACTORS`.

### 2. Meta Graph API: gratis Instagram (aanrader, bespaart kosten)

Met je Meta Business-account kan de tool Instagram-hashtags en openbare zakelijke en creator-accounts **gratis** ophalen. Wat via Meta lukt, hoeft niet meer via Apify.

1. Koppel je Instagram-account als **zakelijk of creator-account** aan een Facebook-pagina.
2. Maak een app op [developers.facebook.com](https://developers.facebook.com): **Mijn apps → App maken → type Business**. Voeg het product **Instagram** toe (*API setup with Facebook login*).
3. Vraag in de [Graph API Explorer](https://developers.facebook.com/tools/explorer/) een User Token aan met deze rechten: `instagram_basic`, `pages_show_list`, `pages_read_engagement` en `business_management`.
4. Zoek je Instagram-ID op met de Explorer-aanroep `me/accounts?fields=instagram_business_account`. Het getal bij `instagram_business_account.id` zet je achter `META_IG_USER_ID=`.
5. Maak er een token van dat 60 dagen geldig is. Klik daarvoor in de [Access Token Debugger](https://developers.facebook.com/tools/debug/accesstoken/) op **Extend Access Token**. Dat token zet je achter `META_ACCESS_TOKEN=`.

Goed om te weten:
- **Vernieuwen.** Het token verloopt na 60 dagen. Herhaal dan stap 5. Werkt het token niet meer, dan zie je dat in het logboek van de ophaalrondes.
- **Hashtags.** Meta staat **30 verschillende hashtags per 7 dagen** toe. De tool houdt dat bij en stuurt de rest naar Apify.
- **Mogelijke review.** Voor hashtag-zoeken kan Meta de functie *Instagram Public Content Access* via App Review laten goedkeuren. Lukt hashtag-zoeken niet, dan gaan die hashtags vanzelf via Apify. De accounts blijven gewoon via Meta werken.

### 3. Claude: slimmere herkenning (optioneel)

Zonder AI herkent de tool posts aan de hand van woordenlijsten (`trendradar/lexicon.py`). Met een sleutel van [console.anthropic.com](https://console.anthropic.com) leest Claude de posts. Dan herkent hij concrete **productnamen** (bijvoorbeeld "Paprika chips met limoen"), **zaaknamen** en **steden**, en filtert hij beter op Nederlandse en relevante posts. Zet de sleutel achter `ANTHROPIC_API_KEY=`.

Alleen posts die de woordenlijsten al als mogelijk relevant zien, gaan naar Claude. Het AI-budget heeft een eigen maandplafond.

## Kosten en budget

De tool rekent zo:

```
budget per ronde = (resterend maandbudget) ÷ (resterende rondes deze maand)
```

Dat budget wordt per ronde verdeeld over Instagram, TikTok en Facebook. Elke Apify-run krijgt een **hard plafond** mee voor het aantal resultaten (`maxItems`) en het bedrag (`maxTotalChargeUsd`), dus Apify stopt zelf voordat het budget op is. Na elke run leest de tool de **werkelijke** kosten uit Apify en stuurt bij.

Indicatie bij de standaardinstellingen (€ 60 voor data, elke 6 uur ophalen):

| | Per ronde | Per maand |
|---|---|---|
| Instagram (via Apify) | ± 180 posts | ± 8.500 posts, plus wat gratis via Meta komt |
| TikTok | ± 370 posts | ± 17.000 posts |
| Facebook | ± 115 posts | ± 5.500 posts |

**Apify-abonnement.** Bij Apify heb je voor dit verbruik waarschijnlijk een betaald abonnement nodig. Het gratis plan heeft maar een klein maandtegoed. Kijk op [apify.com/pricing](https://apify.com/pricing) en zet het maandbudget in de tool op het tegoed dat je abonnement geeft.

**AI-kosten.** De standaard is het model `claude-opus-5-5` op denkniveau `low`, met een plafond van € 10 per maand. Met deze hoeveelheden posts (ongeveer € 2 per 1.000 ingedeelde posts) is dat plafond naar schatting na ongeveer een week bereikt. Daarna werkt de tool verder met alleen de woordenlijsten. Wil je alle posts met AI laten indelen, dan kun je onder **Instellingen** kiezen voor `claude-haiku-5-5`. Dat kost ongeveer een veertigste en blijft binnen een paar euro per maand, maar is wat minder precies.

## Hoe de trendscore werkt

Een onderwerp is trending als het in de gekozen periode vaker voorkomt dan gemiddeld in de periodes ervoor:

| Periode | Vergeleken met |
|---|---|
| Nu (6 uur) | gemiddelde van de 4 blokken van 6 uur ervoor |
| 24 uur | gemiddelde van de 6 dagen ervoor |
| 3 dagen | de 2 blokken van 3 dagen ervoor |
| 7 dagen | de week ervoor |

```
score = log2(groei) × √(aantal verschillende makers) + klein gewicht voor interactie
```

Door het aantal makers mee te wegen telt één account dat tien keer hetzelfde post niet als trend. Merk op dat "Nu" in de praktijk betekent: sinds de laatste ophaalronde. De tool haalt elke 6 uur op, en dat interval is instelbaar.

**Opbouwfase.** In de eerste dagen is er nog weinig historie. De interface meldt dat zolang de vergelijking nog niet betrouwbaar is.

## Bronnen ontdekken

Na elke ronde zoekt de tool in de relevante Nederlandse posts van de afgelopen 7 dagen naar nieuwe bronnen:

- **Hashtags** die bij minstens 3 verschillende makers voorkomen.
- **Accounts** die minstens 2 relevante posts plaatsten.
- **Accounts** die door meerdere makers genoemd worden.

Standaard worden per ronde maximaal 6 ontdekte bronnen direct geactiveerd. De rest komt als **kandidaat** in de lijst, zodat jij kunt kiezen. Omgekeerd ruimt de tool ook op:

- **Gepauzeerd:** bronnen die na 3 rondes minder dan 15% relevante posts opleveren.
- **Ongeldig:** accounts die twee keer niets teruggeven.

Bronnen die je **zelf** toevoegt, worden nooit automatisch gepauzeerd. Wat de tool ontdekt, hoe streng hij is en hoeveel bronnen er maximaal actief zijn, stel je in onder **Budget & instellingen**.

## Supermarkten

AH en Jumbo hebben geen officiële open API. De tool gebruikt daarom de onofficiële API's die hun eigen apps ook gebruiken, en controleert die één keer per dag:

- **Nulmeting.** De eerste keer legt de tool alleen vast wat er in de snackcategorieën ligt.
- **Nieuw.** Alles wat daarna voor het eerst opduikt, telt als nieuw. Producten die de winkel zelf als "nieuw" markeert, tellen meteen mee.
- **Storingen.** Deze API's kunnen zonder waarschuwing veranderen of geblokkeerd worden. De status per winkel staat bovenaan het tabblad, en bij een storing draait de rest gewoon door.

Daarnaast haalt de tool nieuws over nieuwe producten op via Google News. Onder Instellingen kun je eigen RSS-feeds toevoegen, bijvoorbeeld van vakbladen.

## Mappen en bestanden

```
trendradar/
├── start.sh               # starten (installeert de eerste keer alles)
├── .env.example           # voorbeeld voor je sleutels
├── data/                  # database (wordt aangemaakt, staat niet in git)
├── trendradar/
│   ├── __main__.py        # opstarten + planner (elke X uur)
│   ├── collector.py       # één ophaalronde
│   ├── sources/           # Apify, Meta, nieuws, supermarkten
│   ├── classify.py        # relevantie en indeling (woordenlijsten + Claude)
│   ├── lexicon.py         # woordenlijsten: gerechten, merken, steden
│   ├── seeds.py           # startlijst met hashtags, accounts en zoektermen
│   ├── discovery.py       # zelf bronnen toevoegen en opruimen
│   ├── trends.py          # trendberekening
│   ├── budget.py          # budgetbewaking
│   ├── snackspert.py      # koppeling met de recensies op snackspert.nl
│   ├── demo.py            # verzonnen voorbeelddata
│   ├── web.py             # API voor de interface
│   └── static/            # de interface (HTML/CSS/JS)
└── tests/
```

**Tests draaien:**

```bash
.venv/bin/pip install -r requirements-dev.txt
.venv/bin/python -m pytest
```

## Een kanttekening

De Apify-scrapers halen openbare posts op, maar de platforms staan dat in hun gebruiksvoorwaarden niet toe. Apify voert het scrapen uit. Gebruik de data voor je eigen analyse, en neem geen posts of foto's van anderen over zonder toestemming.
