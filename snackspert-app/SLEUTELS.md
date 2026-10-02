# Google Maps-sleutels beveiligen — klik voor klik

Je hebt twee sleutels nodig: één voor Android, één voor iOS. Ze komen straks
allebei in hetzelfde Google Cloud-project te staan.

Reken op een kwartier.

---

## Deel A — Vraag eerst je SHA-1 op

Die heb je nodig bij stap B7. Zet hem even in een kladbestand.

**A1.** Open je terminal en typ:

```
cd ~/snackspert/snackspert-app
npx eas-cli credentials --platform android
```

**A2.** Kies je project als hij dat vraagt.

**A3.** Kies in het menu: `Keystore: Manage everything needed to build your project`

**A4.** Er verschijnt een overzicht met regels als `SHA1 Fingerprint`. Kopieer
de waarde achter **SHA1** — een lange reeks met dubbele punten, zoiets als
`A1:B2:C3:...`

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

**B8.** Klik **DONE**.

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

## Deel F — Pas later: de oude sleutel opruimen

**Doe dit niet nu.** De app die nu op je telefoon staat gebruikt de oude
iOS-sleutel nog; verwijder je hem meteen, dan blijft de kaart daar leeg.

Zodra je nieuwe build draait en je hebt gecontroleerd dat de kaart werkt:

**F1.** Zoek het Cloud-project waar de oude sleutel `AIzaSyASmO` in staat.

**F2.** Vink hem aan in de lijst en klik **DELETE**.

---

## Als de kaart grijs blijft na de nieuwe build

Dan is er iets met de sleutel, en bijna altijd is het één van deze drie:

1. **De verkeerde API aangevinkt.** Android heeft *Maps SDK for Android*, iOS
   heeft *Maps SDK for iOS*. Ze zijn niet uitwisselbaar.
2. **De SDK staat niet aan in het project** (deel C).
3. **De SHA-1 hoort bij de verkeerde keystore.** Bouw je met EAS, dan moet het
   de SHA-1 zijn uit `eas credentials`, niet die van een lokale debug-keystore.

Je kunt ook tijdelijk alle beperkingen weghalen om te zien of het dáár aan ligt.
Zet ze er dan wel meteen weer op.
