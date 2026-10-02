# Google Maps-sleutels beveiligen — klik voor klik

Je hebt twee sleutels nodig: één voor Android, één voor iOS. Ze komen straks
allebei in hetzelfde Google Cloud-project te staan.

Reken op een kwartier.

---

## Deel A — Vraag je SHA-1 op

Je hebt er straks **twee** nodig. Lees eerst het kadertje hieronder, want dat
is de valkuil in dit hele verhaal.

> ### Waarom twee?
>
> Google Play ondertekent je app opnieuw. Jouw keystore is alleen een
> *uploadsleutel*; de app die gebruikers uit de Play Store installeren is
> ondertekend met een sleutel van Google zelf. Dat is verplicht voor alle
> nieuwe apps.
>
> Beperk je je Maps-sleutel dus alleen tot jouw eigen SHA-1, dan **werkt de
> kaart niet voor iedereen die de app uit de Play Store haalt** — terwijl hij
> bij jou op je testtoestel gewoon werkt. Dat is een fout die je pas na
> publicatie ontdekt.
>
> Daarom zet je er beide in:
>
> | Welke | Waarvoor | Waar vandaan |
> |---|---|---|
> | Jouw uploadsleutel | preview-builds, APK's die je zelf installeert | `eas credentials` (deel A) |
> | Google's app signing key | de app uit de Play Store | Play Console, **pas nadat je je eerste .aab hebt geüpload** |
>
> Nu voeg je de eerste toe. De tweede doe je in deel F, na je eerste upload.

**A1.** Open je terminal en typ:

```
cd ~/snackspert/snackspert-app
npx eas-cli credentials --platform android
```

**A2.** Vraagt hij *"Which build profile do you want to configure?"* — kies
**production**.

**A3.** Kies in het menu: `Keystore: Manage everything needed to build your project`

**A4.** Er verschijnt een overzicht. Kopieer de waarde achter **SHA1
Fingerprint** — een lange reeks met dubbele punten, zoiets als `A1:B2:C3:...`

**A5.** Druk op Ctrl+C om het menu te verlaten.

---

## Deel B — De Android-sleutel beveiligen

**B1.** Ga naar https://console.cloud.google.com/apis/credentials

**B2.** Kijk bovenin, naast het Google Cloud-logo. Daar staat de naam van je
project. Klik erop en kies het project waar je **Android**-sleutel in staat
(dat is het project dat je laatst hebt aangemaakt).

**B3.** Je ziet nu een lijst **API keys**. Klik op de naam van de sleutel die
begint met `AIzaSyDkif`.

**B4.** Geef hem bovenaan een duidelijke naam: `Snackspert Android`

**B5.** Zoek het kopje **Application restrictions**. Kies **Android apps**.

**B6.** Klik op **ADD** (of `+ Add an item`).

**B7.** Vul in:
- *Package name:* `nl.snackspert.app`
- *SHA-1 certificate fingerprint:* de waarde uit stap A4

**B8.** Klik **DONE**. (In deel F komt hier een tweede regel bij.)

**B9.** Zoek het kopje **API restrictions**. Kies **Restrict key**.

**B10.** Open de keuzelijst en vink alleen aan: **Maps SDK for Android**

**B11.** Klik onderaan **SAVE**.

> Het kan tot vijf minuten duren voordat dit werkt. Dat is normaal.

---

## Deel C — Zet Maps SDK for iOS aan in dit project

Dit moet vóór deel D, anders werkt de nieuwe sleutel niet.

**C1.** Ga naar https://console.cloud.google.com/apis/library

**C2.** Let op dat bovenin nog hetzelfde project staat als bij B2.

**C3.** Zoek op: `Maps SDK for iOS`

**C4.** Klik op het resultaat en klik op **ENABLE**.

---

## Deel D — Een nieuwe iOS-sleutel maken

De oude iOS-sleutel staat in een ander project en is lastig te vinden. We maken
een nieuwe; dat is sneller en netter.

**D1.** Ga terug naar https://console.cloud.google.com/apis/credentials

**D2.** Klik bovenaan op **+ CREATE CREDENTIALS** → **API key**.

**D3.** Er verschijnt een venster met je nieuwe sleutel. **Kopieer hem** en
bewaar hem even. Klik dan op **Edit API key** (of sluit het venster en klik in
de lijst op de nieuwe sleutel).

**D4.** Geef hem de naam: `Snackspert iOS`

**D5.** Bij **Application restrictions**: kies **iOS apps**.

**D6.** Klik op **ADD** en vul in bij *Bundle ID:* `nl.snackspert.app`

**D7.** Klik **DONE**.

**D8.** Bij **API restrictions**: kies **Restrict key** en vink alleen aan:
**Maps SDK for iOS**

**D9.** Klik **SAVE**.

**D10.** Stuur me de nieuwe sleutel uit stap D3, dan zet ik hem in de app.

---

## Deel E — Budgetwaarschuwing

Zodat je het hoort als er iets misgaat, in plaats van het op de rekening te
zien.

**E1.** Ga naar https://console.cloud.google.com/billing

**E2.** Klik op je factureringsaccount.

**E3.** Klik links op **Budgets & alerts**.

**E4.** Klik **CREATE BUDGET**.

**E5.** Naam: `Snackspert`. Bedrag: `20` euro per maand.

**E6.** Laat de waarschuwingsdrempels staan zoals ze zijn (50%, 90%, 100%) en
klik **FINISH**.

---

## Deel F — Na je eerste upload naar Google Play

**Niet vergeten.** Zonder deze stap blijft de kaart grijs voor iedereen die de
app uit de Play Store installeert.

**F1.** Upload je `.aab` naar de Play Console (dat hoeft nog niet publiek te
zijn — een gesloten test is genoeg).

**F2.** Ga in de Play Console naar **Release → Setup → App signing**
(Nederlands: *Release → Instellen → App-ondertekening*).

**F3.** Onder **App signing key certificate** staat een **SHA-1 certificate
fingerprint**. Kopieer die.

**F4.** Ga terug naar je Android-sleutel in de Google Cloud Console
(deel B), klik bij *Application restrictions* op **ADD**, en voeg een tweede
regel toe:
- *Package name:* `nl.snackspert.app`
- *SHA-1:* de waarde uit stap G3

**F5.** Klik **DONE** en **SAVE**.

Nu werken beide: je eigen builds én de versie uit de Play Store.

---

## Deel G — Pas later: de oude sleutel opruimen

**Doe dit niet nu.** De app die nu op je telefoon staat gebruikt de oude
iOS-sleutel nog; verwijder je hem meteen, dan blijft de kaart daar leeg.

Zodra je nieuwe build draait en je hebt gecontroleerd dat de kaart werkt:

**G1.** Zoek het Cloud-project waar de oude sleutel `AIzaSyASmO` in staat.

**G2.** Vink hem aan in de lijst en klik **DELETE**.

---

## Als de kaart grijs blijft na de nieuwe build

Dan is er iets met de sleutel, en bijna altijd is het één van deze drie:

1. **De verkeerde API aangevinkt.** Android heeft *Maps SDK for Android*, iOS
   heeft *Maps SDK for iOS*. Ze zijn niet uitwisselbaar.
2. **De SDK staat niet aan in het project** (deel C).
3. **De SHA-1 klopt niet.** Werkt de kaart bij jou wél maar bij gebruikers uit
   de Play Store niet, dan is deel F overgeslagen — dan mist Google's eigen
   app signing-SHA-1.

Je kunt ook tijdelijk alle beperkingen weghalen om te zien of het dáár aan ligt.
Zet ze er dan wel meteen weer op.
