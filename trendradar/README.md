# Snackspert Trendradar

Een tool die je lokaal draait en die Nederlandse posts over snacks, streetfood en nieuwe supermarktproducten volgt op Instagram, TikTok en Facebook. Hij laat zien wat er stijgt in de periodes **nu (6 uur), 24 uur, 3 dagen en 7 dagen**.

Zonder sleutels start hij in **demomodus**, met verzonnen voorbeelddata. Zo kun je de interface meteen bekijken.

## Wat zit erin

| Tabblad | Wat je ziet |
|---|---|
| **Vandaag** | Je dagelijkse briefing, het startscherm. **Kandidaten voor jou**: posts met een kleine viral of een nieuwe creatie, met de reden erbij. Daarnaast onderwerpen in de **vroege fase**, **Snackspert in het nieuws**, snacknieuws, nieuwe supermarktproducten en het beste uit Amsterdam. |
| **Trends** | De stijgers: producten, zaken, merken, woordcombinaties (zoals "pistache kroket"), gerechten en steden, met groei ten opzichte van de periodes ervoor, hoeveel verschillende makers het noemen en wat er opvalt (views, likes of doorsturen ver boven normaal). Daarnaast **doorbraken** (onbekende makers die viraal gaan), nieuw opgedoken onderwerpen, posts die nu hard gaan, het volume per platform en de verdeling over categorieën. Klik op een onderwerp voor het verloop en de populairste posts. |
| **Posts** | Alle relevante posts, met zoeken, filteren en sorteren. |
| **Amsterdam** | Alles uit Amsterdam, ook herkend aan wijken als De Pijp, Jordaan, Oud-West en Noord en aan plekken als de Foodhallen en de Albert Cuyp. Je ziet de kandidaten, waar Amsterdam het over heeft (met fase), de genoemde zaken, het Amsterdamse eetnieuws en de nieuwste posts. |
| **Supermarkt** | Nieuwe producten bij tien supermarkten (AH, Jumbo, Lidl, Plus, Dirk en meer), met welke bronnen het bevestigen. **Vroege signalen**: producten waar makers al over posten maar die nog niet in de winkeldata staan. Plus de meest besproken producten en het nieuws. |
| **Zaken & steden** | Eetzaken en foodtrucks die genoemd worden, met een **reviewkandidaat**-label als ze nog niet op snackspert.nl staan. Plus een kaart met steden. |
| **Tips & routes** | Je tiplijst en routes uit Excel, met status, notities, Google Maps-routes en 🔥 als een tip nu besproken wordt. |
| **Viral-potentie** | Een inschatting van de 10 (of 25) tips met de meeste kans om viraal te gaan, met de redenen erbij, plus de routes met de meeste potentie. |
| **Mijn posts** | Analyse van je eigen Instagram-posts uit Excel: per maand, per format, wat werkt, en welke snacks het bij jouw publiek goed doen. |
| **Mijn lijst** | Alles wat je met ☆ bewaart: posts, zaken, producten en onderwerpen. Geef elk item een status (*te proberen*, *gepland*, *bezocht*, *gereviewd*, *afgevallen*) en een notitie. Je kunt de lijst exporteren als CSV. |
| **Bronnen** | De gevolgde hashtags, accounts en zoektermen. De tool **voegt zelf bronnen toe**: uit virale posts en uit onderwerpen die meerdere makers noemen. Bronnen die weinig opleveren pauzeert hij. Per bron zie je wat een nuttige post kost. |
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

### 2. Meta Graph API: gratis Instagram (optioneel)

Niet nodig als Instagram via Apify loopt; in de tool staat hij dan als "niet gekoppeld, optioneel". Met je Meta Business-account kan de tool Instagram-hashtags en openbare zakelijke en creator-accounts **gratis** ophalen. Wat via Meta lukt, hoeft niet meer via Apify.

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

**Zo houdt de tool de kosten laag.** Apify rekent per opgehaalde post, ook als je die post al hebt. Daarom:

- **Alleen nieuwe posts.** Bij elke bron vraagt de tool alleen posts op vanaf de vorige keer (datumfilter). Per ronde staat in het logboek hoeveel procent toch al bekend was. Is dat bij een bron structureel hoog, dan negeert die actor het filter.
- **Ritme per bron.** Een bron die vooral bekende posts teruggeeft, komt pas na 2 of 4 rondes weer aan de beurt. Het geld gaat naar bronnen die wél nieuws opleveren.
- **Opbrengst telt nieuwe posts.** De opbrengst van een bron is het aandeel *nieuwe* relevante posts per betaald resultaat. Bronnen met een lage opbrengst gaan op pauze.
- **Kosten per nuttige post.** Per bron en voor de hele maand zie je wat één nieuwe, relevante Nederlandse post kost. Zo zie je direct welke bronnen hun geld waard zijn.
- **Gratis eerst.** Wat via de gratis Meta-API kan, gaat niet via Apify.
- **AI alleen waar nodig.** Duidelijk irrelevante en niet-Nederlandse posts gaan niet naar Claude.
- **Herhaalmeting.** Elke ronde worden de 15 snelste posts per platform opnieuw gemeten, om te zien of ze echt doorschieten. Dat kost ongeveer € 7 per maand en is in te stellen onder **Kosten besparen**; 0 zet het uit.

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

**Hashtags zijn geen trend.** Ze zijn het hulpmiddel om posts en accounts te vinden. Het onderwerp is wat ín de posts staat: een product, een zaak of een woordcombinatie. In het detailvenster van een onderwerp zie je wel welke hashtags erbij gebruikt worden, om verder te zoeken.

Door het aantal makers mee te wegen telt één account dat tien keer hetzelfde post niet als trend. De kolom **Makers** laat zien hoeveel verschillende accounts een onderwerp noemen, met tussen haakjes hoeveel meer dan normaal.

### Opvallend: views, likes en doorsturen

Per post vergelijkt de tool de cijfers met een gewone post **van dezelfde leeftijd** op hetzelfde platform. Een video van 2 uur oud heeft nu eenmaal minder views dan een video van 3 dagen oud.

| Label | Betekenis |
|---|---|
| ▶ views 8× | 8 keer zoveel views als een gewone post van dezelfde leeftijd |
| ↗ gedeeld 5× | 5 keer zo vaak doorgestuurd per view als normaal |
| ♥ likes 3× | 3 keer zoveel likes per view als normaal |
| 👥 bereik 40× volgers | de post bereikte 40 keer zoveel mensen als de maker volgers heeft |
| 🚀 doorbraak | een kleine maker (onder 20.000 volgers) die veel meer mensen bereikt dan het aantal volgers, of een post met 10× zoveel views als normaal |

Deze signalen tellen mee in de trendscore. Een onderwerp met één **doorbraak** komt ook in de lijst als maar één maker het noemt. Dat is precies de onbekende maker die als eerste viraal gaat met een snack.

**Taal.** Alleen Nederlandstalige posts tellen mee. Bevat een post meer veelgebruikte woorden uit een andere taal (Engels, Spaans, Portugees, Duits, Frans, Italiaans, Indonesisch, Tagalog, Turks) dan Nederlandse woorden, dan valt hij af. Nederlandse posts over Indisch eten (nasi, saté) blijven gewoon Nederlands.

De kaart **Doorbraken** op het Trends-tabblad toont die posts per maker. Bij Posts kun je sorteren op **Snelst groeiend**. Merk op dat "Nu" in de praktijk betekent: sinds de laatste ophaalronde. De tool haalt elke 6 uur op, en dat interval is instelbaar.

**Opbouwfase.** In de eerste dagen is er nog weinig historie. De interface meldt dat zolang de vergelijking nog niet betrouwbaar is.

## Vóór de hype: waar de tool op let

Snackhits beginnen vaak hetzelfde: een kleine zaak zet iets nieuws op de kaart, vaak een bekende snack in een onverwachte combinatie (een broodje met döner en kaassoufflé, een burger tussen suikerbrood). Een paar makers posten erover, daarna volgt het regionale nieuws. De tool zoekt naar die eerste stappen.

| Label | Betekenis |
|---|---|
| 🆕 Nieuw op de kaart | De post noemt iets als "nieuw op de kaart", "eigen creatie", "weekspecial" of "vanaf vandaag". |
| 🧪 Combinatie | Twee snacks die normaal niet samengaan, zoals *kaassoufflé + döner*. Gewone combinaties (friet met frikandel) tellen niet. |
| 🔄 Twist | Een bekende snack in een nieuwe vorm: *loaded kipcorn*, *gevulde kroket*, *xxl frikandel*. Heel gewone twists (loaded friet, mini frikandel) tellen niet. |

**Kandidaten** (bij Vandaag en Amsterdam) krijgen punten voor zo'n label, voor een doorbraak, voor veel views of doorsturen, voor een kleine maker en voor een post van minder dan een dag oud. Per maker en per onderwerp komen er maximaal twee in de lijst, zodat je verschillende dingen ziet.

**Fase van de hype** staat bij elk onderwerp:

| Fase | Wanneer |
|---|---|
| 🌱 Vroeg | Hooguit 3 makers en nog geen nieuws. Hier kun jij het verschil maken. |
| 📈 Groeit | Meer makers, nog geen nieuws. |
| 🔥 Piek | Minstens 2 nieuwsberichten of 15 makers. |
| 📉 Over hoogtepunt | Minstens 20% minder posts dan de periode ervoor. |

**TikTok** zoekt naast hashtags vooral op zoektermen. Zoekresultaten bevatten nieuwe video's van kleine makers, terwijl hashtagpagina's steeds dezelfde bekende video's tonen. Daarom krijgen TikTok-hashtags minder budget. De tool haalt de nieuwste video's op (niet de vastgepinde) en zoekt vanuit Nederland. Woorden en combinaties die opkomen (in de fase vroeg of groeit) worden **automatisch nieuwe TikTok-zoektermen**.

### Leren van jou

De tool leert uit vier dingen:

| Bron | Hoe het meetelt |
|---|---|
| **☆ Mijn lijst** | Wat je bewaart telt het zwaarst. *Afgevallen* telt juist tegen, *gereviewd* telt half mee. |
| **♥ en 👎** bij elke post | Niet om te bewaren, wel om de tool te laten weten wat je waardeert. ♥ betekent "meer zoals dit", 👎 "minder zoals dit". Klik nog een keer om het weg te halen. |
| **Je tips** (Tips & routes) | De zaken en specialiteiten uit je tiplijst. Duikt een tip op in een post, dan krijgt die post voorrang. |
| **Je eigen posts** (Mijn posts) | Welke snacks het bij jouw publiek beter doen dan je gemiddelde post. |

Van wat je bewaart, ♥ of 👎 geeft, kijkt de tool wat ze gemeen hebben: een woordcombinatie (*loaded kipcorn*), een twist, een combinatie, een snack, een zaak of een maker.

- **Vandaag** geeft posts die daarop lijken extra punten, met de reden erbij:
  - *⭐ Past bij jou: loaded kipcorn* (lijkt op wat je bewaarde, een ♥ gaf of in je tips hebt)
  - *📈 Jouw publiek: friet 1,27× je mediaan* (uit je eigen posts)
  - *Al gepost op 2025-03-16* (deze zaak noemde je al in een eigen post; hij zakt dan iets)
- Posts die je al bewaarde of beoordeelde, verdwijnen uit de kandidaten. Zo zie je steeds nieuwe dingen.
- Een losse snack (bijvoorbeeld kaassoufflé) telt alleen mee als je hem zelf bewaarde of een ♥ gaf. Anders zou door je ruim 200 tips elke kaassoufflé-post "bij jou passen".
- **Bronnen**: een woordcombinatie, twist of zaak die je bewaart of een ♥ geeft, wordt een TikTok-zoekopdracht. De maker van zo'n post wordt een gevolgd account. Bij de bron staat dan *"uit Mijn lijst of ♥"*. Je tips worden geen zoekopdrachten: dat zou het budget over te veel bronnen verdelen.

Op Vandaag zie je bij **⭐ Wat de tool van jou leert** wat de tool heeft opgepikt en op basis waarvan.

## Viral-potentie

Het tabblad **Viral-potentie** maakt een inschatting van welke tips uit Tips & routes de meeste kans hebben om viraal te gaan. Elke tip krijgt punten (0 tot 100), met de redenen erbij. De punten volgen het patroon van eerdere snackhits zoals het broodje Koet, het broodje kaassoufflé en de suikerbroodburger: een kleine zaak met iets eigens.

| Signaal | Punten | Voorbeeld uit je tips |
|---|---|---|
| Eigen creatie | +3 | broodje lammert, Steenwijkerbal, Huysfrikandel |
| Combinatie van bekende snacks | +3 | kapsalon met kaassoufflé, croissant döner |
| Opvallend om te zien | +2,5 | Friet Tank (friet in de vorm van een pantservoertuig) |
| Twist op een bekende snack | +2 | loaded fries, gevulde grillworst |
| Vaker getipt door volgers | +2 | "twee keer getipt" |
| Nu al posts over (🔥) | +1,5 | de zaak wordt genoemd in de radar |
| Een daarvan gaat hard | +1,5 | zo'n post haalt 3× zoveel views als normaal |
| Huisgemaakt | +1 | "zelfgemaakte bitterballen" |
| Verhaal of claim | +1 | "prijswinnaar beste hamburger", "60 jaar oud" |
| Schaars | +1 | "alleen vrijdag", "op de zaterdagmarkt" |
| Herkenbare snack | +1 | frikandel, kroket, kaassoufflé |
| Prijs als haakje | +0,5 | "broodje bal met mayo (€1,50)" |
| Niche gerecht | -0,75 | arepa, francescinha |
| Weinig bijzonders genoemd | -1 | "geen gekke dingen" |

Daarbovenop komt wat bij jouw publiek werkt, uit **Mijn posts** (tot ±1,5 punt):
- welke snacks het goed doen;
- of zaken buiten Amsterdam het beter doen;
- welk soort zaak goed scoort (snackbar, broodjeszaak).

Je ♥, 👎 en bewaarde items tellen ook mee (tot ±2).

Wat niet meetelt:
- zaken die je **al gepost** hebt;
- zaken die op *gereviewd* of *afgevallen* staan.

Zet je een tip op een van die statussen, dan schuift de volgende vanzelf de lijst in. Stops uit je routes die nog niet als tip in je lijst staan, doen ook mee; met één klik bewaar je ze als tip.

Rechts zie je de **routes met de meeste potentie**: de som van alle stops, met een knop naar Google Maps.

Het blijft een inschatting op basis van de beschrijving in je tips. Hoe meer je bij een tip opschrijft (wat er bijzonder aan is, of hij vaker getipt is), hoe beter de inschatting.

## Mijn posts

Klik op **Excel importeren** en kies je totaaloverzicht. De tool leest het tabblad met *Weergaven* en *Caption*. Afgeleide tabbladen als *Samenwerkingen* en *Per maand* herkent hij: posts die daar nog eens in staan, worden niet dubbel geteld. Opnieuw importeren vervangt je posts, dus je kunt elke maand het nieuwe overzicht inladen.

Je ziet per jaar (of alles):
- views en nieuwe volgers per maand, met dezelfde maand een jaar eerder;
- **Wat werkt**: conclusies in gewone taal, zoals je best bekeken format en of zaken buiten Amsterdam het beter doen;
- per format, kanaal, locatie en herkenbaarheid de mediaan views, de index (100 = je mediaan) en de volgers per post. Groepen met minder dan 5 posts staan grijs: die zeggen nog weinig;
- **Snacks bij jouw publiek**: snacks met minstens 6 posts, vergeleken met je mediaan;
- je toppers (op views, volgers of doorgestuurd) en je supermarkttests.

Volgers bij collabs tellen niet mee: die worden gedeeld met een ander account (zoals in je eigen overzicht).

## Tips & routes

Klik op **Excel importeren** en kies je tips- en routebestand.
- Tabbladen met *Naam* (of *Naam zaak*) worden **tips**, met de tabbladnaam als lijst (Burgers, Amsterdam, Broodje Bal, Buiten Amsterdam).
- Tabbladen met *Route* en *Stop 1* worden **routes**.
- Opnieuw importeren voegt nieuwe tips toe. Je status en notities blijven bewaard.

Bij elke tip:
- zet je een status (*te proberen* → *gepland* → *bezocht* → *gereviewd*) en een notitie;
- opent de naam de zaak in Google Maps;
- zie je 🔥 als er in de afgelopen 30 dagen over de zaak gepost is. Klik erop en je ziet die posts;
- zie je ✓ als je de zaak al eens noemde in een eigen post.

Elke route heeft een knop **Route in Google Maps**: Maps opent met alle stops, vanaf waar je bent.

**Zelf een tip toevoegen.** Je kunt op drie manieren een tip toevoegen:
- Met de knop **＋ Tip toevoegen** bovenaan Tips & routes. Je vult naam, plaats, specialiteit, lijst en notitie in. Schrijf op wat er bijzonder aan is (eigen creatie, vaker getipt, alleen op vrijdag): dat gebruikt de Viral-potentie.
- Met de knop 📍 bij een zaak in **Zaken & steden**.
- Bij **🔎 Ontdekt in de radar**. Daar staan zaken waar deze week meerdere makers over posten en die nog niet in je tips staan; met één klik zet je ze erbij.

**✨ Bedacht door de tool.** De tool bedenkt zelf routes. Hij combineert kansrijke tips uit de Viral-potentie die dicht bij elkaar liggen (binnen ±35 km), vanaf je thuisbasis en weer terug. Wat hij daarvoor leert:
- **Van je eigen routes:** hoe ver je gewoonlijk rijdt en met hoeveel stops (bij jou: meestal ±270 km retour, 3 of 4 stops).
- **Van je statussen:** bezochte, gereviewde en afgewezen tips doen niet mee.
- **Van je ♥, 👎 en bewaarde items:** die tellen mee in de potentie.
- **Van je keuzes:** met **Bewaren** komt een route bij je routes. Met **👎 Niet voor mij** stelt hij die route nooit meer voor.

Om te weten waar je tips liggen, zoekt de tool elke plaats één keer op bij OpenStreetMap (gratis). Dat gebeurt vanzelf bij elke ophaalronde, of meteen met de knop **nu opzoeken**. Afstand en rijtijd zijn een schatting: hemelsbreed × 1,3, met gemiddeld 75 km/u. Google Maps geeft de echte route. Je thuisbasis (standaard Amsterdam) stel je in bij **Budget & instellingen**.

Je tips komen ook terug op andere plekken:
- **Vandaag** (📍 Je tips in de radar);
- **Amsterdam** (Jouw Amsterdam-tips);
- **Zaken & steden** (📍 tip en ✓ gepost).

## Bronnen ontdekken

Na elke ronde zoekt de tool in de relevante Nederlandse posts van de afgelopen 7 dagen naar nieuwe bronnen:

- **Hashtags** die bij minstens 3 verschillende makers voorkomen.
- **Accounts** die minstens 2 relevante posts plaatsten.
- **Accounts** die door meerdere makers genoemd worden.
- **Wat je bewaart in Mijn lijst of een ♥ geeft** (zie hierboven). Deze gaan voor alles.
- **Opkomende woorden en combinaties** (zoals *frikandelijs*) als TikTok-zoekterm.
- **Hashtags en makers uit virale posts**, ook als het om één maker gaat. Deze gaan altijd voor. Bij de bron staat dan bijvoorbeeld: *"uit virale post van @maker (40× views, bereik 276× het aantal volgers)"*. Een onbekend woord mag hier (#tanghulu: een nieuwe snack staat nog niet in de woordenlijst), maar geen gebouw, plek of gelegenheid (#gerbrandytoren, #domplein, #bruiloft).

Standaard worden per ronde maximaal 6 ontdekte bronnen direct geactiveerd. De rest komt als **kandidaat** in de lijst, zodat jij kunt kiezen. Omgekeerd ruimt de tool ook op:

- **Gepauzeerd:** bronnen die na 3 rondes minder dan 15% relevante posts opleveren.
- **Ongeldig:** accounts die twee keer niets teruggeven.

Bronnen die je **zelf** toevoegt, worden nooit automatisch gepauzeerd. Wat de tool ontdekt, hoe streng hij is en hoeveel bronnen er maximaal actief zijn, stel je in onder **Budget & instellingen**.

### Apify-tegoed: het budget in de tool is iets anders dan je Apify-plan

Het maandbudget in de tool is een **plafond**: zoveel mag de tool hooguit uitgeven. Het geld zelf zit op je **Apify-account**:
- Het gratis Apify-plan heeft maar $5 per maand. Daarmee kom je hooguit een paar rondes ver.
- Voor het budget in de tool (bijvoorbeeld €60) heb je dus een **betaald Apify-plan** nodig. Dat kies je op apify.com onder *Billing*.

De tool vraagt bij elke ronde aan Apify hoeveel tegoed er nog is. Bij **Budget & instellingen** zie je dat als *Apify-account deze maand*.
- **Tegoed op:** de tool slaat Apify over, met een duidelijke melding in het logboek.
- **Bijna op:** de tool haalt minder op, zodat runs niet halverwege worden afgebroken.
- **Lager dan het budget in de tool:** dat staat er dan bij.

### Als het internet even wegvalt

Lukt het niet om Apify te bereiken (geen internet, of de naam api.apify.com is even niet te vinden), dan probeert de tool het na 20 seconden nog één keer. Lukt het dan nog niet, dan zie je in het logboek *"geen verbinding met Apify"*.
- Er is niets betaald.
- De bronnen tellen niet als leeg. Een account wordt dus niet ten onrechte als "ongeldig" gemarkeerd.
- De bronnen komen de volgende ronde weer aan de beurt. De ronde heet dan *deels*.

Een run die al gestart is, wordt nooit opnieuw gestart: dat zou dubbel kosten.

## Supermarkten

De tool legt drie bronnen naast elkaar: het **assortiment** van de supermarkten, **social posts** en **nieuws**.

**Assortiment.** Dat komt van [checkjebon](https://github.com/supermarkt/checkjebon). Dat open project (MIT-licentie, de data mag hergebruikt worden) verzamelt elke dag het online assortiment van Albert Heijn, Jumbo, Lidl, Plus, Dirk, Hoogvliet, DekaMarkt, Spar, Vomar en Poiesz. Samen zijn dat ruim 100.000 producten. De tool vergelijkt dat twee keer per dag:

- **Nulmeting.** De eerste keer legt de tool alleen vast wat elke winkel verkoopt.
- **Nieuw.** Alles wat daarna voor het eerst opduikt, is nieuw. Een product dat even uitverkocht was en terugkomt, telt niet opnieuw. Zet een winkel een bestaand product opnieuw online onder een ander artikelnummer (Spar doet dat), dan herkent de tool het aan naam en verpakking. Het telt dan niet als nieuw.
- **Alleen snacks.** Standaard zie je alleen nieuwe producten die over snacks, streetfood, snoep of drinken gaan. Een vinkje toont ook de rest. Dierenvoer en schoonmaakmiddelen worden altijd overgeslagen.
- **Zuinig.** Is het bestand niet veranderd, dan downloadt de tool de 10 MB niet opnieuw.

**Social.** Ook zonder AI herkent de tool productnamen in zinnen als *"Nieuw bij AH: Paprika Chips Limoen"* of *"Gespot bij Jumbo: Bitterbal Chips"*. Met een AI-sleutel herkent Claude productnamen in de hele post. Varianten van dezelfde naam worden samengevoegd, en per product telt de tool hoeveel verschillende makers het noemen.

**Bevestigd door.** Bij elk nieuw product in het schap staat of makers en nieuws het ook oppikken (🏪 winkel, 📱 social, 📰 nieuws).

**⚡ Vroege signalen.** Makers posten over een nieuw product dat (nog) niet in de winkeldata staat. Hier ben je eerder dan de supermarkt-app. Bij winkels waarvan we geen assortiment hebben (zoals Aldi) staat dat erbij, want daar zegt "niet in winkeldata" niets.

Nieuws over nieuwe producten komt via Google News. Onder Instellingen kun je eigen RSS-feeds toevoegen, bijvoorbeeld van vakbladen.

## Back-up

Eens per week maakt de tool een kopie van de database (je lijst, tips, routes, notities, ♥/👎) en bewaart de laatste acht. Het liefst in de Google Drive-map **Snackspert Trendradar**. Daarvoor één keer: open op je Chromebook de app *Bestanden*, ga naar *Google Drive > Mijn Drive*, klik met rechts op de map *Snackspert Trendradar* en kies **Delen met Linux**. Zonder die stap komen de kopieën in `data/backups`. Een back-up terugzetten: stop de tool, kopieer het bestand naar `data/trendradar.db` en start opnieuw.

## Nieuwe zaken en je eigen posts

- **Nieuw op Google Maps** (Tips & routes): elke week zoekt de tool in twee steden naar snackbars, foodtrucks, streetfood en frituren (± 1 dollar per week). De eerste keer per stad legt hij vast wat er is; daarna zie je wat er nieuw bij komt, met nog weinig reviews.
- **Je eigen posts**: vul bij Budget & instellingen je Instagram-account in, dan haalt de tool elke week je nieuwe posts en cijfers op (± 2 cent per week). Volgers per post en bewaard staan alleen in Instagram Insights: die komen uit je Excel-export.
- **Trefkans** (Mijn posts): de tool houdt bij wat hij aanraadt en ziet later in je posts welke tips je postte en hoe die liepen. Signalen die bij jou goed werken, tellen op Vandaag zwaarder mee.

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
│   ├── signals.py         # views/likes/doorsturen t.o.v. normaal, doorbraken
│   ├── products.py        # nieuwe producten: winkel, social en nieuws koppelen
│   ├── budget.py          # budgetbewaking
│   ├── snackspert.py      # koppeling met de recensies op snackspert.nl
│   ├── taste.py           # smaakprofiel: leren van je lijst, ♥/👎 en tips
│   ├── ownposts.py        # analyse van je eigen posts
│   ├── spots.py           # tips en routes, gekoppeld aan de radar
│   ├── potential.py       # viral-potentie van je tips
│   ├── routeplan.py       # routes die de tool zelf bedenkt
│   ├── geo.py             # waar liggen je tips (OpenStreetMap, één keer opgezocht)
│   ├── imports.py         # Excel-bestanden inlezen
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
