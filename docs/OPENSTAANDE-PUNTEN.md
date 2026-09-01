# De vier openstaande punten

Vooraf, eerlijk: de omgeving waarin dit gebouwd is kan snackspert.nl niet
bereiken (uitgaand verkeer daarheen wordt geblokkeerd), dus ik heb de site niet
zelf kunnen bevragen. Wat hieronder als "vastgesteld" staat, volgt uit hoe ACF
en WordPress deze veldtypes opslaan; wat als "te bevestigen" staat, leest
`python -m publisher doctor` in een paar seconden uit de echte database. Draai
dat commando dus voordat je de eerste keer publiceert.

## 1. show_in_rest staat op 0

**Dit is geen blokkade meer.** De plugin schrijft de velden server-side met
`update_field()`, en die functie trekt zich niets aan van de REST-instelling van
de veldgroep. Publiceren werkt dus met `show_in_rest` op 0.

Je kunt hem alsnog aanzetten, en daar is een goede reden voor die los staat van
publiceren: de iPhone-app in `snackspert-app/` schraapt nu per zaak de HTML van
de detailpagina om de reviewtekst, het adres en de sterren te pakken te krijgen
(zie `snackspert-app/services/api.ts`). Met `show_in_rest` aan komen `text`,
`address`, `map` en `location` gewoon in `/wp/v2/restaurant` te staan en kan dat
scrapen eruit. Nadeel: die velden worden daarmee publiek leesbaar. Voor een
reviewsite die alles toch al op de pagina zet, lijkt me dat geen bezwaar.

Zet je hem aan, dan werkt ook de terugvalroute `--via=rest` zonder plugin.

## 2. image: attachment-ID, geen URL

**Vastgesteld.** Een ACF image-veld bewaart in `wp_postmeta` altijd het
attachment-ID, ongeacht wat `return_format` zegt. `return_format: url` gaat
alleen over wat `get_field()` teruggeeft bij het *lezen*. Schrijf je een kale
URL weg, dan komt die letterlijk in de meta te staan en toont de front-end niets.

De volgorde is dus: foto naar `POST /wp/v2/media`, het `id` uit het antwoord
pakken, en dat wegschrijven. Dat doet de publisher automatisch. Staat
`/wp/v2/media` dicht (Wordfence, een uploadfilter), dan gaat de foto als base64
mee met het eigen endpoint en doet WordPress de upload zelf.

De plugin zet de foto ook als uitgelichte afbeelding, want de app leest de
overzichtslijst via `wp:featuredmedia`. Alleen het ACF-veld vullen zou het item
in de app zonder foto laten staan.

**Te bevestigen met `doctor`:** die leest de ruwe meta van de nieuwste bestaande
review en meldt of daar inderdaad een kaal ID in staat.

## 3. location: bestaand post-ID van type `locatie`

**Vastgesteld** dat een enkelvoudig `post_object`-veld het post-ID opslaat, en
dat het ID naar een bestaande `locatie`-post moet wijzen.

**Beleid dat ik gekozen heb, wijzig het gerust:** de plugin zoekt de plaats op
exacte titel of slug, hoofdletterongevoelig. Geen fuzzy match, want een review
aan de verkeerde plaats hangen is vervelender dan hem aan geen plaats hangen.
Wordt er niets gevonden, dan publiceert het item gewoon door met een
waarschuwing, en blijft `location` leeg. Alleen met `maak_locatie_aan: true`
maakt hij een nieuwe plaatspagina aan (titel = plaatsnaam, direct gepubliceerd)
en meldt dat je die inhoudelijk moet nalopen.

Voor de dagelijkse ronde is dit denk ik de goede stand: `python -m publisher
locaties Neede` laat je vooraf zien of de plaats bestaat, en anders maak je hem
in wp-admin fatsoenlijk aan.

## 4. map: een array, geen platte waarde

**Vastgesteld** dat het `google_map`-veldtype een array opslaat. De front-end
heeft `lat`, `lng` en `address` nodig; de rest (`zoom`, `place_id`,
`street_name`, `city`, `post_code`, `country`) vult Google's autocomplete
normaal aan en mag ontbreken.

De plugin schrijft standaard:

```php
array(
    'address' => 'Marktstraat 12 7161 CT Neede',
    'lat'     => 52.1401,
    'lng'     => 6.6152,
    'zoom'    => 15,
)
```

Extra sleutels kun je meesturen als je ze hebt. Geen `lat`/`lng` betekent geen
kaartpin, en dat zegt de publisher er ook bij.

**Te bevestigen met `doctor`:** die drukt de sleutels af die de nieuwste
bestaande review in `map` heeft staan. Blijkt daar een sleutel bij te zitten die
de kaart nodig heeft en die wij niet vullen, dan is dat een regel bijwerken in
`build_map()`.

## Nog een punt dat niet op de lijst stond

De sterrenbeoordeling staat niet in een eigen veld: de site en de app lezen hem
uit de reviewtekst zelf, door de ster-emoji te tellen (zie `telSterren()` in
`snackspert-app/services/api.ts`). Daarom voegt de publisher de sterrenregel aan
de tekst toe in plaats van aan een veld, en laat hij bestaande sterren met rust.
`doctor` kijkt bij een bestaande review of de sterren boven of onder in de tekst
staan, zodat je `sterren_positie` daarop kunt zetten.
