# Lancering Snackspert

Afvinklijst voor de eerste publieke release. Van boven naar beneden.

---

## 1. Beveilig je Google Maps-sleutels — doe dit eerst

Je sleutels staan in `app.json`, en dat kan niet anders: een app moet ze kunnen
lezen. Daarmee staan ze ook in het installatiebestand, en dat is straks publiek
te downloaden. Een onbeperkte sleutel kan iedereen gebruiken, en de rekening
komt op jouw Google-account.

**De stappen staan in [SLEUTELS.md](./SLEUTELS.md)** — klik voor klik, zo'n
kwartier werk.

Let op: deze sleutels staan *niet* in EAS. `eas credentials` beheert alleen je
ondertekening voor Apple en Google. API-sleutels regel je in de Google Cloud
Console.

## 2. Zet je Sentry-DSN erin

De foutmelding zit in de app, maar staat uit tot je er een DSN in zet. Zonder
DSN doet hij niets: geen verbinding, geen vertraging.

1. Maak een gratis account op [sentry.io](https://sentry.io) → nieuw project →
   platform **React Native** → noem het `snackspert`
2. Je krijgt een **DSN** te zien (`https://...@....ingest.sentry.io/...`)
3. Zet die in **`constants/sentry.ts`**:

```ts
export const SENTRY_DSN = 'https://jouw-dsn-hier';
```

4. Sturen met `npx eas-cli update --branch production --message "foutmelding aan"`

**Dit kan dus ná je build.** Dat is precies waarom de DSN in een codebestand
staat en niet in `app.json`: dat laatste zit in de vingerafdruk van de build, en
een wijziging daar zou nooit via een update aankomen.

De regelnummers in de meldingen verwijzen voorlopig naar de samengevoegde code.
Wil je leesbare meldingen (`index.tsx:142` in plaats van `bundle:1:284910`),
stuur me dan je **organisatie- en projectnaam** uit Sentry, dan zet ik dat
erbij — dat vereist wel een nieuwe build.

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

**Testvereiste.** Het gaat hier om de datum waarop je **Play
Console-ontwikkelaarsaccount** is aangemaakt — dat account van eenmalig $ 25 —
niet om de leeftijd van je Google-account. Die twee zijn los van elkaar: je kunt
al vijftien jaar een Gmail hebben en vorige maand ontwikkelaar zijn geworden.

Is dat ontwikkelaarsaccount een **persoonlijk** account van ná 13 november 2023,
dan eist Google eerst een gesloten test met **minimaal 12 testers, 14 dagen
aaneengesloten**. Organisatieaccounts zijn hiervan uitgezonderd.

Je hoeft dit niet uit te rekenen: de Play Console zegt het zelf. Geldt het voor
jou, dan staat de eis als taak in je publicatieoverzicht, met een teller van hoe
veel testers je hebt. Staat die taak er niet, dan kun je direct publiceren.

Valt je account eronder, dan is er geen trucje: nepaccounts zijn precies waar
Google op controleert, en daar raak je je ontwikkelaarsaccount mee kwijt. Wel
werkt dit:

- **Vraag het je volgers.** Je hebt een publiek dat van snacks houdt — dat is
  precies de doelgroep. Eén story met "wie heeft Android en wil mijn app
  testen?" levert meestal meer dan twaalf mensen op. Ze hoeven alleen te
  installeren en af en toe te openen.
- **Werk met een Google-groep.** Maak één groep aan en zet die als testerslijst
  in de Play Console. Dan hoef je geen twaalf losse e-mailadressen bij te
  houden en kunnen mensen er later bij.
- **De veertien dagen lopen door.** Ze beginnen zodra je twaalf testers hebt,
  dus hoe eerder je de gesloten test aanzet, hoe eerder je publiek kunt.

Vandaar het advies: **lanceer iOS nu**, en laat Android meelopen terwijl de
testperiode draait. Daar hoeft niemand op te wachten.

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

### Als er iets misgaat

Crasht de app bij een gebruiker, dan krijg je daar nu bericht van in Sentry
(zodra je de DSN hebt ingevuld, stap 2). De gebruiker ziet geen wit scherm meer
maar een melding met twee knoppen; de tweede wist de opgeslagen gegevens, zodat
een beschadigde cache geen app oplevert die bij elke start opnieuw omvalt.

Is de oorzaak JavaScript — en dat is het bijna altijd — dan los je het op en
stuur je het dezelfde dag door met `eas update`, zonder nieuwe build en zonder
review.
