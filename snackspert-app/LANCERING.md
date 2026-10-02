# Lancering Snackspert

Afvinklijst voor de eerste publieke release. Van boven naar beneden.

---

## 1. Beveilig je Google Maps-sleutels — doe dit eerst

Je twee sleutels staan in `app.json`, en dat kan niet anders: een app moet ze
kunnen lezen. Maar daarmee staan ze ook in het installatiebestand, en dat is
straks publiek te downloaden. Een onbeperkte sleutel kan iedereen gebruiken, en
de rekening komt op jouw Google-account.

Ga naar [Google Cloud → Credentials](https://console.cloud.google.com/apis/credentials)
en beperk beide sleutels:

**iOS-sleutel** (`AIzaSyASmO...MI9bg`)
- Application restrictions → **iOS apps** → bundle ID: `nl.snackspert.app`
- API restrictions → alleen *Maps SDK for iOS* en *Geocoding API*

**Android-sleutel** (`AIzaSyDkif...Rf21tw`)
- Application restrictions → **Android apps** → package: `nl.snackspert.app`
  en de SHA-1 van je release-keystore
- API restrictions → alleen *Maps SDK for Android*

Je SHA-1 opvragen:

```
npx eas-cli credentials --platform android
```

Kies je project → *Keystore: Manage everything* → de SHA-1 staat in het
overzicht.

Zet daarna ook een **budgetwaarschuwing** op je Google Cloud-project
(Billing → Budgets & alerts), bijvoorbeeld op € 20. Dan hoor je het als er iets
misgaat in plaats van het pas op de rekening te zien.

---

## 2. Beslis: wil je iPad ondersteunen?

In `app.json` staat nu `"supportsTablet": true`. Gevolgen:

- Apple **reviewt je app op een iPad**, en de app is nooit op een iPad getest
- App Store Connect **eist iPad-screenshots** voordat je kunt inzenden

Zet je het op `false`, dan hoeft geen van beide. iPad-gebruikers kunnen je app
dan nog steeds installeren — iPhone-apps draaien op iPad, alleen in een
iPhone-venster.

Mijn advies voor 1.0: op `false`. Zeg het, dan pas ik het aan.

---

## 3. De build

De app die nu in TestFlight staat is verouderd: die heeft het kapotte
categoriefilter nog en kan geen updates over de lucht ontvangen. Je hebt dus
één nieuwe build nodig.

```
cd ~/snackspert/snackspert-app
git pull origin claude/instagram-reviews-google-docs-jNwal
npm install

npx eas-cli build --profile production --platform ios
npx eas-cli build --profile production --platform android
```

Daarna inzenden naar Apple:

```
npx eas-cli submit --platform ios --latest
```

Voor Android levert de production-build een `.aab` op die je in de Google Play
Console uploadt.

---

## 4. App Store Connect

**App Privacy** — dit is wat je app werkelijk doet:

| Vraag | Antwoord |
|---|---|
| Verzamelt de app data? | Ja, één soort: **Locatie** (precies én bij benadering) |
| Waarvoor? | **App Functionality** — afstand tot restaurants en de kaart |
| Gekoppeld aan de gebruiker? | **Nee** |
| Gebruikt voor tracking? | **Nee** |
| Andere categorieën | Geen. Geen accounts, geen analytics, geen advertenties |

Je favorieten en afgevinkte restaurants staan alleen op het toestel zelf en
verlaten het nooit. De locatie wordt op het toestel gebruikt; dat Google hem
voor het tekenen van de kaart ontvangt is de reden dat je hem wél opgeeft.

**Overige velden**
- Categorie: *Food & Drink* (secundair: *Travel*)
- Leeftijd: 4+
- Encryptie: al geregeld via `ITSAppUsesNonExemptEncryption: false` in `app.json`
- Privacybeleid-URL: die van je site
- Support-URL: je site of je contactpagina — dit veld is verplicht

**Screenshots** — App Store Connect laat zien welke maten het op dit moment
vraagt; dat verandert af en toe, dus volg wat er staat. Neem er drie tot vijf:
de kaart met pins, de lijst met beoordelingen, het filtermenu met Vega/Vegan,
een recensiepagina, en Opgeslagen.

---

## 5. Google Play

Twee dingen die je kunnen verrassen:

**Testvereiste.** Is je Google Play-ontwikkelaarsaccount een persoonlijk account
dat na november 2023 is aangemaakt, dan eist Google eerst een gesloten test met
**minimaal 12 testers, 14 dagen aaneengesloten**, voordat je publiek mag.
Controleer dit nu in de Play Console, want het bepaalt je planning. Je vier
testers zijn dan niet genoeg.

**Data safety-formulier.** Zelfde antwoorden als bij Apple: alleen locatie, voor
app-functionaliteit, niet gedeeld, niet voor tracking. Vermeld dat de verbinding
versleuteld is (je site is https) en dat gebruikers geen verwijderverzoek hoeven
te doen omdat er niets wordt opgeslagen.

Verder nodig: contentclassificatie (vragenlijst), doelgroep, en je
privacybeleid-URL.

---

## 6. Winkelteksten

**Naam:** Snackspert

**Subtitel** (max 30 tekens):
> Alle snacks, eerlijk getest

**Promotietekst** (max 170 tekens, los van de review aan te passen):
> 750+ zaken persoonlijk getest en beoordeeld. Vind de beste burger, kroket of
> shoarma bij jou in de buurt — op de kaart of in de lijst.

**Beschrijving:**
> Snackspert test snackbars, burgerzaken, friettenten en broodjeszaken, en
> schrijft er eerlijk over. Geen sponsoring, geen reclamepraatjes: één persoon
> die alles zelf eet en opschrijft wat hij ervan vindt.
>
> In deze app staan alle recensies van snackspert.nl — ruim 750 zaken, van
> Amsterdam tot Maastricht en af en toe over de grens.
>
> **Op de kaart**
> Zie meteen wat er bij je in de buurt zit. Tik op een pin voor de foto, de
> beoordeling en het adres, en open de route in één tik.
>
> **Filter op wat je zoekt**
> Hamburger, kroket, frietpatat, shoarma/döner, pizza, broodjes, spareribs en
> meer. Apart filter voor Vega en Vegan. Of laat alleen de zaken zien die vier
> of vijf sterren kregen.
>
> **Bewaar wat je wil proberen**
> Zet zaken op je lijst, en vink af waar je al geweest bent.
>
> **Sorteer op afstand**
> Zie de dichtstbijzijnde zaken eerst, overal waar je bent.
>
> Snackspert blijft groeien: er komen steeds nieuwe recensies bij, en die staan
> automatisch in de app.

**Trefwoorden** (max 100 tekens, met komma's, zonder spaties erna):
> snackbar,friet,kroket,burger,shoarma,patat,frituur,snacks,eten,recensies,vega,broodjes

**Wat is er nieuw** (voor 1.0):
> De eerste versie van Snackspert. Alle 750+ recensies op de kaart, met filters
> op keuken, dieet en beoordeling.

---

## 7. Na de lancering

Vanaf nu hoef je voor een JavaScript-wijziging geen build meer te maken:

```
npx eas-cli update --branch production --message "waar het over gaat"
```

Een minuut werk, geen review. Gebruikers hebben het bij de volgende keer
opstarten. Dit geldt voor alles wat je in de app ziet: teksten, filters,
schermen, bugfixes.

Pas als er een **native** onderdeel bij komt — een nieuw pakket dat eigen
Android- of iOS-code meebrengt — is er een nieuwe build nodig. In dat geval
weigert de app de update netjes in plaats van om te vallen, omdat de
runtimeversie op `fingerprint` staat.

### Waar je nog geen oog op hebt

Er zit **geen foutmelding naar jou** in de app. Crasht hij bij een gebruiker,
dan hoor je dat alleen als die het zelf meldt. Sentry toevoegen is ongeveer een
half uur werk en vereist één build. Niet nodig om te lanceren, maar wel iets om
te overwegen zodra er echt mensen op zitten — juist omdat je zei dat de app niet
mag omvallen.
