# Google Maps-sleutels beveiligen — klik voor klik

Je krijgt **twee nieuwe sleutels**: één voor Android, één voor iOS. De sleutel
die je nu hebt laat je met rust — die is van je website.

Reken op een kwartier.

---

## Waarom nieuwe sleutels?

De sleutel `AIzaSyDkif...` wordt op dit moment gebruikt voor geocoding,
directions, places, static maps en street view. Je app gebruikt daar niets van,
dus dat is **snackspert.nl zelf**: de kaart op je site, de routeknoppen op je
recensiepagina's, en het geocoderen van adressen als je een restaurant
toevoegt.

Zet je op die sleutel een beperking als "alleen Android apps", dan gaat je
website stuk. Daarom:

| Waarvoor | Welke sleutel | Beperking |
|---|---|---|
| snackspert.nl | de bestaande `AIzaSyDkif...` | laat voorlopig staan — zie deel G |
| Android-app | nieuw, deel B | Android apps + Maps SDK for Android |
| iOS-app | nieuw, deel D | iOS apps + Maps SDK for iOS |

Eén sleutel per gebruik betekent ook: gaat er ooit één fout, dan ligt niet
alles plat.

---

## Deel A — Je SHA-1

Die heb je al opgehaald:

```
D1:77:9E:4C:8A:12:35:50:3E:AC:23:43:E6:4B:2E:87:46:98:A5:BE
```

Je hebt er straks nog een tweede bij nodig, maar die bestaat nog niet.

> ### Waarom twee?
>
> Google Play ondertekent je app opnieuw. Jouw keystore is alleen een
> *uploadsleutel*; de app die mensen uit de Play Store installeren is
> ondertekend met een sleutel van Google zelf. Dat is verplicht voor alle
> nieuwe apps.
>
> Zet je alleen je eigen SHA-1 erin, dan werkt de kaart op je testtoestel wél
> en voor Play Store-gebruikers **niet** — een fout die je pas na publicatie
> ontdekt.
>
> | Welke | Waarvoor | Waar vandaan |
> |---|---|---|
> | Jouw uploadsleutel | builds die je zelf installeert | hierboven |
> | Google's app signing key | de app uit de Play Store | Play Console, ná je eerste `.aab`-upload → deel F |

---

## Deel B — Nieuwe Android-sleutel

**B1.** Ga naar https://console.cloud.google.com/apis/credentials

**B2.** Kijk bovenin naast het Google Cloud-logo. Daar staat je projectnaam.
Zorg dat dit het project is waar je huidige sleutel in staat
(`ecstatic-cosmos-420412`).

**B3.** Klik bovenaan op **+ CREATE CREDENTIALS** → **API key**.

**B4.** Er verschijnt een venster met je nieuwe sleutel. **Kopieer hem** en zet
hem even in een kladbestand. Klik dan op **Edit API key**.

**B5.** Geef hem bovenaan de naam: `Snackspert Android app`

**B6.** Bij **Application restrictions**: kies **Android apps**.

**B7.** Klik op **ADD** en vul in:
- *Package name:* `nl.snackspert.app`
- *SHA-1 certificate fingerprint:* de reeks uit deel A

**B8.** Klik **DONE**. (In deel F komt hier een tweede regel bij.)

**B9.** Bij **API restrictions**: kies **Restrict key**.

**B10.** Open de keuzelijst en vink alleen aan: **Maps SDK for Android**

**B11.** Klik onderaan **SAVE**.

> Nu krijg je **geen** waarschuwing over actief gebruik: deze sleutel is nieuw
> en wordt nog nergens gebruikt. Krijg je die waarschuwing wél, dan zit je per
> ongeluk in de oude sleutel — ga terug.

---

## Deel C — Zet Maps SDK for iOS aan

Dit moet vóór deel D, anders werkt de nieuwe iOS-sleutel niet.

**C1.** Ga naar https://console.cloud.google.com/apis/library

**C2.** Let op dat bovenin nog hetzelfde project staat.

**C3.** Zoek op: `Maps SDK for iOS`

**C4.** Klik op het resultaat en klik op **ENABLE**. (Staat er al *Manage*, dan
is het goed.)

---

## Deel D — Nieuwe iOS-sleutel

**D1.** Ga terug naar https://console.cloud.google.com/apis/credentials

**D2.** Klik op **+ CREATE CREDENTIALS** → **API key**.

**D3.** **Kopieer de sleutel** en klik op **Edit API key**.

**D4.** Naam: `Snackspert iOS app`

**D5.** Bij **Application restrictions**: kies **iOS apps**.

**D6.** Klik op **ADD** en vul in bij *Bundle ID:* `nl.snackspert.app`

**D7.** Klik **DONE**.

**D8.** Bij **API restrictions**: **Restrict key** → alleen
**Maps SDK for iOS**

**D9.** Klik **SAVE**.

---

## Deel E — Stuur me beide sleutels

Uit stap B4 en D3. Dan zet ik ze in `app.json` en kun je bouwen.

Wil je het zelf doen: in `app.json` staan ze bij
`ios.config.googleMapsApiKey` en `android.config.googleMaps.apiKey`.

---

## Deel F — Budgetwaarschuwing

Dit staat helemaal los van je app en van de build — je kunt het ervoor of erna
doen.

Het is een **e-mail van Google als het gebruik van Maps geld gaat kosten**. Geen
limiet: het zet niets stop, het waarschuwt alleen.

Waarom het nuttig is: Maps heeft een gratis maandtegoed, en jouw site plus app
blijven daar normaal ruim onder. Maar de sleutel van je website is nog
onbeperkt en staat in je paginabron. Haalt iemand hem eruit en gaat er
grootschalig mee geocoderen, dan loopt dat op jouw rekening. Met een
waarschuwing hoor je dat binnen een dag in plaats van aan het eind van de
maand.

**F1.** Ga naar https://console.cloud.google.com/billing

**F2.** Klik op je factureringsaccount.

**F3.** Klik links op **Budgets & alerts**.

**F4.** Klik **CREATE BUDGET**.

**F5.** Naam: `Snackspert`. Bedrag: `20` euro per maand.

**F6.** Laat de drempels staan (50%, 90%, 100%) en klik **FINISH**.

---

## Deel G — Na je eerste upload naar Google Play

**Niet vergeten.** Zonder deze stap blijft de kaart grijs voor iedereen die de
app uit de Play Store installeert.

**G1.** Upload je `.aab` naar de Play Console (een gesloten test is genoeg).

**G2.** Ga naar **Release → Setup → App signing**
(Nederlands: *Release → Instellen → App-ondertekening*).

**G3.** Onder **App signing key certificate** staat een **SHA-1 certificate
fingerprint**. Kopieer die.

**G4.** Ga terug naar je Android-sleutel uit deel B, klik bij *Application
restrictions* op **ADD**, en voeg toe:
- *Package name:* `nl.snackspert.app`
- *SHA-1:* de waarde uit G3

**G5.** **DONE** → **SAVE**.

---

## Deel H — Later: de sleutel van je website

Dit is een apart klusje, en het kan wachten tot na de lancering. Maar laat het
niet liggen: die sleutel is nu onbeperkt, en hij staat in de broncode van je
website — dus iedereen kan hem uit je pagina halen.

Het beveiligen gaat anders dan bij een app: een website beperk je op
**HTTP referrer**, niet op een bundle-id.

1. Open de sleutel `AIzaSyDkif...`
2. *Application restrictions* → **Websites**
3. Voeg toe: `https://snackspert.nl/*` en `https://www.snackspert.nl/*`
4. *API restrictions* → laat voorlopig **alle** API's aan staan

Die laatste stap is bewust voorzichtig. Welke API's je site precies gebruikt
weten we niet, en de waarschuwing noemde er elf. Beperk je de verkeerde, dan
gaat je site stuk. Eerst de referrer vastzetten is al het grootste deel van de
winst: dan kan niemand jouw sleutel meer vanaf zijn eigen site gebruiken.

Wil je het daarna helemaal goed doen, dan kijken we samen in **Metrics
Explorer** welke API's werkelijk gebruikt worden, en beperken we het tot die
lijst.

---

## Als de kaart grijs blijft na de nieuwe build

Bijna altijd één van deze drie:

1. **De verkeerde API aangevinkt.** Android heeft *Maps SDK for Android*, iOS
   heeft *Maps SDK for iOS*. Ze zijn niet uitwisselbaar.
2. **De SDK staat niet aan in het project** (deel C).
3. **Deel G overgeslagen.** Werkt de kaart bij jou wel en bij Play
   Store-gebruikers niet, dan is dat het.

Een beperking kan tot vijf minuten duren voordat hij werkt. Schrik dus niet als
het meteen na SAVE nog niet klopt.
