# Dagelijks een review live zetten

Je levert de review zelf aan als een tekstbestandje met een foto. Een commando
controleert het op huisstijl en zet het daarna direct live op snackspert.nl, als
nieuw item onder het post type `restaurant`. Geen conceptstap.

## Eenmalig instellen

### 1. De plugin op de site

Ga in wp-admin naar **Plugins > Nieuwe plugin > Plugin uploaden**, kies
`wp-plugin/snackspert-review-api.zip` en activeer hem. Geen FTP nodig.

Heb je wel toegang tot de bestanden en wil je hem niet per ongeluk kunnen
uitzetten, zet dan `wp-plugin/snackspert-review-api.php` in
`wp-content/mu-plugins/`. Mu-plugins staan altijd aan en hoef je niet te
activeren. Allebei werkt; de zip is minder werk.

Na een wijziging aan het PHP-bestand maak je een nieuwe zip met
`./wp-plugin/maak-zip.sh`.

Daarmee komen er drie routes bij:

| Route | Doet |
| --- | --- |
| `POST /wp-json/snackspert/v1/reviews` | publiceert een review |
| `GET /wp-json/snackspert/v1/schema` | leest de veldopbouw en de opslagvorm uit |
| `GET /wp-json/snackspert/v1/locaties` | geeft de bestaande plaatspagina's |

Alle drie vragen om een ingelogde gebruiker met publiceerrechten.

### 2. Inloggegevens lokaal

```bash
cp .env.voorbeeld .env
```

Vul `SNACKSPERT_USER` en `SNACKSPERT_APP_PASSWORD` in met het account
`Admin_Eke` en een Application Password uit
**wp-admin > Gebruikers > Admin_Eke > Application Passwords**. `.env` staat in
`.gitignore`; zet het wachtwoord nooit in een reviewbestand of in een commit.
Staat het wachtwoord niet meer paraat, genereer dan een nieuwe en trek de oude
in; dat is minder werk dan zoeken.

Blijf je 401 krijgen, kijk dan in Wordfence onder **All Options > Brute Force
Protection** of *Disable WordPress application passwords* niet opnieuw aan is
komen te staan.

### 3. Python

```bash
pip install -r requirements.txt
```

### 4. Controleren of alles staat

```bash
python -m publisher doctor
```

Dat logt in, kijkt of de plugin er staat, leest de ACF-veldgroep uit en laat
zien hoe de nieuwste bestaande review de velden `image`, `location` en `map`
werkelijk heeft opgeslagen. Doe dit voordat je de eerste keer publiceert.

## De dagelijkse ronde

```bash
python -m publisher nieuw "Cafetaria De Hoek"
```

Dat maakt `reviews/2026-09-01-cafetaria-de-hoek.md` aan. Vul de kop in, zet de
foto ernaast, en schrijf de review onder de tweede `---` regel. Zie
`reviews/_voorbeeld.md` voor een ingevuld exemplaar.

```bash
python -m publisher controleer reviews/2026-09-01-cafetaria-de-hoek.md
python -m publisher publiceer reviews/2026-09-01-cafetaria-de-hoek.md
```

`publiceer` doet de controle nog een keer en stopt bij fouten, dus je kunt de
tussenstap overslaan als je haast hebt. Wil je eerst zien wat er zou gebeuren
zonder iets weg te schrijven:

```bash
python -m publisher publiceer <bestand> --dry-run
```

Publiceren gaat in deze volgorde: foto naar de mediabibliotheek, dan het item
aanmaken met status `publish`, dan de ACF-velden en de uitgelichte afbeelding
zetten. Je krijgt de permalink terug plus eventuele waarschuwingen.

Ging er iets mis in de tekst en wil je dezelfde pagina overschrijven in plaats
van een tweede aan te maken:

```bash
python -m publisher publiceer <bestand> --bijwerken
```

Zonder `--bijwerken` weigert het endpoint een tweede item met dezelfde slug. Dat
is met opzet: een half mislukte publicatie die je opnieuw probeert, mag geen
dubbele pagina opleveren.

## Het reviewbestand

```yaml
---
naam: Cafetaria De Hoek        # wordt de paginatitel
sterren: 4                     # halve sterren mogen: 3.5, 4, 4.5
sterren_positie: onder         # onder (standaard), boven, of geen
hoofdcategorie: kroket         # main_category, bepaalt de gerelateerde zaken
categorie: [kroket, snackbar]  # category, nul of meer
dieet: []                      # Vega en/of Vegan, meestal leeg
plaats: Neede                  # moet een bestaande locatie-pagina zijn
adres: |
  Marktstraat 12
  7161 CT Neede
lat: 52.1401
lng: 6.6152
foto: fotos/de-hoek.jpg        # pad relatief aan dit bestand, of: zelf
foto_alt: Kroket op een papieren bakje
---

De reviewtekst. Een lege regel begint een nieuwe alinea; binnen een alinea
mag je afbreken waar je wilt, dat wordt op de site gewoon een spatie.
```

Alles behalve `naam` en de tekst mag weg; je krijgt dan een waarschuwing over
wat er daardoor niet werkt (geen kaartpin, geen plaatskoppeling, geen foto).
De Engelse ACF-namen (`main_category`, `address`, `image`) mogen ook als sleutel.

Minder gebruikte sleutels: `slug` (standaard afgeleid van de naam),
`foto_url` in plaats van `foto` als de foto al ergens online staat,
`maak_locatie_aan: true` om een ontbrekende plaatspagina te laten aanmaken, en
`ook_post_content: true` om de tekst ook in het gewone WordPress-contentveld te
zetten.

### De foto zelf toevoegen

Zet `foto: zelf` als je de foto liever met de hand in wp-admin plaatst. De
publisher uploadt dan niets, zeurt er niet over, en geeft na het publiceren de
bewerklink van de nieuwe pagina mee zodat je er meteen heen kunt.

Doe je het handmatig, zet dan **twee** dingen: het ACF-veld *image* (dat is de
foto op de detailpagina) en de **uitgelichte afbeelding** (die leest de
iPhone-app voor de overzichtslijst en de kaart). Zet je alleen het ACF-veld,
dan staat de zaak in de app zonder foto.

Laat je `foto` helemaal leeg, dan gebeurt hetzelfde, maar krijg je er elke keer
een waarschuwing bij.

### Sterren

De website leest de beoordeling uit de reviewtekst, niet uit een apart veld.
`sterren: 4` plakt er dus een regel `⭐⭐⭐⭐` aan vast. Staan er al sterren in je
tekst, dan blijft die staan en wordt er niets toegevoegd: twee sterrenregels
zouden het gemiddelde vertekenen. `doctor` vertelt je of bestaande reviews de
sterren boven of onder hebben staan, zodat `sterren_positie` daarbij aansluit.

## De huisstijlcontrole

Blokkerend (`fout`):

- liggende streepjes (`—`)
- emoji, behalve de sterren van de beoordeling
- ontbrekende naam of tekst, onbekende categorie, kwart sterren, foto die niet bestaat

Een seintje (`waarschuwing`), publiceren gaat gewoon door:

- zoete woorden (Snackspert doet hartig)
- los "friet" of "patat" waar "frietpatat" hoort te staan
- tekst tussen aanhalingstekens, om te controleren of het citaat echt zo gezegd is
- ontbrekende plaats, foto, coordinaten of beoordeling
- een review korter dan 180 tekens

Verzonnen anekdotes kan geen script zien. Dat blijft bij het schrijven.

`--streng` maakt van elke waarschuwing een fout; `--negeer-huisstijl` publiceert
ondanks fouten, voor als de controle een keer te streng is.

## Als de plugin er niet staat

`publiceer` valt dan automatisch terug op de standaard route
`POST /wp/v2/restaurant` met een `acf`-blok. Dat werkt alleen als de ACF-veldgroep
"Show in REST API" aan heeft staan, en de foto moet dan via `/wp/v2/media` kunnen.
Je krijgt een waarschuwing als WordPress geen gevulde velden terugmeldt.
Forceren kan met `--via=endpoint` of `--via=rest`.

## Wat er in git komt

De reviewbestanden zelf, zodat je terug kunt zien wat er wanneer live is gegaan
en een tekst kunt hergebruiken. De foto's niet (`reviews/**/fotos/` staat in
`.gitignore`): die staan na publicatie in de mediabibliotheek van WordPress.

## Vanaf een telefoon of een ander script

`POST /wp-json/snackspert/v1/reviews` is gewone JSON met Basic auth, dus een
Shortcut, een formulier of een ander script kan hetzelfde doen. De velden heten
daar `naam`, `tekst`, `category`, `main_category`, `diet`, `adres`, `plaats`,
`lat`, `lng`, plus `image_id`, `image_url` of `image_base64` voor de foto. De
huisstijlcontrole zit in de Python-kant, niet in het endpoint; die loop je dan
dus mis.
