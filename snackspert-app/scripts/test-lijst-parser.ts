/**
 * Test de parsers in services/lijst.ts tegen echte HTML van snackspert.nl.
 *
 * De fragmenten hieronder zijn letterlijk van de site overgenomen, inclusief de
 * drie adresvormen die erop voorkomen: Nederlands met postcode, Belgisch met
 * land erachter, en Brits met een postcode die achter de plaatsnaam staat.
 *
 * Draaien:  npx tsc --project scripts/tsconfig.test.json && node ../.test-build/scripts/test-lijst-parser.js
 * of simpeler: npm run test:parser
 */

import {
  parseItems,
  parseTotaalAantal,
  parseSlugs,
  parseCoords,
  parseFacetOpties,
  splitsAdres,
} from '../services/lijst';

let mislukt = 0;

function check(wat: string, werkelijk: unknown, verwacht: unknown) {
  const a = JSON.stringify(werkelijk);
  const b = JSON.stringify(verwacht);
  if (a === b) {
    console.log(`  ok    ${wat}`);
  } else {
    mislukt++;
    console.log(`  FOUT  ${wat}\n          verwacht: ${b}\n          gekregen: ${a}`);
  }
}

/* ── Echte HTML van /restaurants/ ───────────────────────────────── */

const ITEM = (slug: string, titel: string, adres: string, foto: string) => `
<div class="fwpl-row el-1tpnod"><div class="fwpl-col fwpl-col el-k3e19t"><div class="fwpl-item el-oijppf">
<a href="https://snackspert.nl/restaurant/${slug}/" title="${titel}" data-distance="" data-diet="" class="item" data-scroll>
<span class="image"><span class="innerImage" style="background-image:url('${foto}')"></span>
<span class="extraInfo"><span class="distance"> van jou vandaan</span><br/><span class="diet"></span></span></span>
<span class="itemContent"><span class="smallTitle">${titel}</span><span class="address">${adres}</span>
<span class="icon"><i class="icon-arrow-right"></i></span></span></a>
</div></div></div>`;

const PAGINA = `
<html><body>
<div class="facetwp-facet facetwp-facet-category" data-name="category" data-type="fselect"></div>
<div class="facetwp-template">
  <div class="fwpl-layout el-87d7ec">
    <div class="fwpl-result r1">${ITEM(
      't-smikkelhoekje',
      "'t Smikkelhoekje",
      'Meeuwenlaan 185 B, 1021 JC Amsterdam',
      'https://snackspert.nl/wp-content/uploads/2024/08/56679298.jpg'
    )}</div>
    <div class="fwpl-result r2">${ITEM(
      'almost-famous',
      'Almost Famous',
      'UNIT 2, GREAT NORTHERN, Peter St, Manchester M3 4EN, Verenigd Koninkrijk',
      'https://snackspert.nl/wp-content/uploads/2024/08/26952381.jpg'
    )}</div>
    <div class="fwpl-result r3">${ITEM(
      't-fritkotje',
      "'t Fritkotje",
      'Londenstraat 48, 2000 Antwerpen, Belgi&euml;',
      ''
    )}</div>
  </div>
</div>
<div class="facetwp-pager">
  <a class="facetwp-page" href="https://snackspert.nl/restaurants/?_paged=2">2</a>
</div>
<footer><a href="https://snackspert.nl/privacy/">Privacy</a></footer>
<script>
var FWP_JSON = {"prefix":"_","preload_data":{"facets":{"location":"","category":"<select class=\\"facetwp-dropdown\\"><option value=\\"\\">Alle<\\/option><option value=\\"5-sterren\\">5 sterren (146)<\\/option><option value=\\"hamburger\\">Hamburger<\\/option><option value=\\"shoarma-doner\\">Shoarma\\/d&ouml;ner<\\/option><\\/select>","diet":"<div class=\\"facetwp-checkbox\\" data-value=\\"vega\\">vega <span class=\\"facetwp-counter\\">(131)<\\/span><\\/div><div class=\\"facetwp-checkbox\\" data-value=\\"vegan\\">vegan<\\/div>"},"settings":{"pager":{"page":1,"per_page":24,"total_rows":761}}}};
var restaurantLocations = [
  {"title":"'t Smikkelhoekje","permalink":"https://snackspert.nl/restaurant/t-smikkelhoekje/","lat":52.3912,"lng":4.9221},
  {"title":"Almost Famous","permalink":"https://snackspert.nl/restaurant/almost-famous/","lat":53.4781,"lng":-2.2489},
  {"title":"Zonder coords","permalink":"https://snackspert.nl/restaurant/zonder/","lat":null,"lng":null}
];
</script>
</body></html>`;

/* ── Tests ─────────────────────────────────────────────────────── */

console.log('\nsplitsAdres');
check('Nederlands adres', splitsAdres('Meeuwenlaan 185 B, 1021 JC Amsterdam'), {
  stad: 'Amsterdam',
  land: 'Nederland',
});
check('plaats met meerdere woorden', splitsAdres('Julianastraat 17, 2405 CG Alphen aan den Rijn'), {
  stad: 'Alphen aan den Rijn',
  land: 'Nederland',
});
check('Belgisch adres', splitsAdres('Londenstraat 48, 2000 Antwerpen, België'), {
  stad: 'Antwerpen',
  land: 'België',
});
check(
  'Brits adres met postcode achter de plaats',
  splitsAdres('UNIT 2, GREAT NORTHERN, Peter St, Manchester M3 4EN, Verenigd Koninkrijk'),
  { stad: 'Manchester', land: 'Verenigd Koninkrijk' }
);
check('Nederland expliciet vermeld', splitsAdres('Kerkstraat 1, 1017 GA Amsterdam, Nederland'), {
  stad: 'Amsterdam',
  land: 'Nederland',
});
check('Duits adres', splitsAdres('Hohe Str. 12, Köln 50667, Duitsland'), {
  stad: 'Köln',
  land: 'Duitsland',
});
check('alleen een plaats', splitsAdres('Amsterdam'), { stad: 'Amsterdam', land: 'Nederland' });
check('leeg adres', splitsAdres(''), { stad: '', land: '' });

console.log('\nparseItems');
const items = parseItems(PAGINA);
check('aantal items', items.length, 3);
check('eerste slug', items[0]?.slug, 't-smikkelhoekje');
check('naam met apostrof', items[0]?.naam, "'t Smikkelhoekje");
check('adres', items[0]?.adres, 'Meeuwenlaan 185 B, 1021 JC Amsterdam');
check('stad', items[0]?.stad, 'Amsterdam');
check('land', items[0]?.land, 'Nederland');
check('foto', items[0]?.afbeeldingUrl, 'https://snackspert.nl/wp-content/uploads/2024/08/56679298.jpg');
check('paginaUrl', items[0]?.paginaUrl, 'https://snackspert.nl/restaurant/t-smikkelhoekje/');
check('buitenland krijgt het juiste land', items[1]?.land, 'Verenigd Koninkrijk');
check('HTML-entiteit in adres wordt omgezet', items[2]?.land, 'België');
check('item zonder foto blijft leeg', items[2]?.afbeeldingUrl, '');
check(
  'de privacy-link uit de footer komt er niet in',
  items.some(i => i.slug === 'privacy'),
  false
);

console.log('\nparseSlugs');
const slugs = parseSlugs(PAGINA);
check('slugs', slugs, ['t-smikkelhoekje', 'almost-famous', 't-fritkotje']);

console.log('\nparseCoords');
const coords = parseCoords(PAGINA);
check('aantal coordinaten', coords.size, 2);
check('coordinaat', coords.get('t-smikkelhoekje'), { lat: 52.3912, lng: 4.9221 });
check('negatieve lengtegraad', coords.get('almost-famous'), { lat: 53.4781, lng: -2.2489 });
check('null-coordinaten worden overgeslagen', coords.has('zonder'), false);

console.log('\nparseTotaalAantal');
check('totaal uit de pager', parseTotaalAantal(PAGINA), 761);
check('geen pager aanwezig', parseTotaalAantal('<html></html>'), null);

console.log('\nparseFacetOpties');
const cats = parseFacetOpties(PAGINA, 'category');
check(
  'categorieen uit de dropdown',
  cats,
  [
    { slug: '5-sterren', label: '5 sterren' },
    { slug: 'hamburger', label: 'Hamburger' },
    { slug: 'shoarma-doner', label: 'Shoarma/döner' },
  ]
);
const diet = parseFacetOpties(PAGINA, 'diet');
check('dieten uit de aanvinkvakjes', diet, [
  { slug: 'vega', label: 'vega' },
  { slug: 'vegan', label: 'vegan' },
]);

console.log(
  mislukt === 0 ? '\nAlles goed.\n' : `\n${mislukt} test(s) mislukt.\n`
);
process.exit(mislukt === 0 ? 0 : 1);
