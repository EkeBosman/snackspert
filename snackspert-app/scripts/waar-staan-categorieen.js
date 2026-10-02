#!/usr/bin/env node
/**
 * Waar staan de categorie- en dieetgegevens van een restaurant zelf?
 *
 * De app leest ze nu via class="catLabel", maar die lijkt niet te bestaan.
 * Dit script toont de HTML rondom het eigen info-blok van een recensiepagina
 * en rondom een item in de overzichtslijst. Verandert niets.
 *
 * Gebruik: node scripts/waar-staan-categorieen.js
 */

const BASE = 'https://snackspert.nl';
const UA =
  'Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1';

async function haal(url) {
  const ctrl = new AbortController();
  const t = setTimeout(() => ctrl.abort(), 25000);
  try {
    const r = await fetch(url, { signal: ctrl.signal, headers: { 'User-Agent': UA } });
    if (!r.ok) throw new Error(`HTTP ${r.status}`);
    return await r.text();
  } finally {
    clearTimeout(t);
  }
}

const schoon = (s) => s.replace(/\s+/g, ' ').trim();

/** Print een venster HTML rond de eerste treffer. */
function venster(html, naald, label, voor = 200, na = 900) {
  const i = html.search(new RegExp(naald, 'i'));
  console.log(`\n   ── ${label} ──`);
  if (i < 0) return console.log('   (niet gevonden)');
  console.log(`   ...${schoon(html.slice(Math.max(0, i - voor), i + na))}...`);
}

(async () => {
  // 1) De overzichtslijst: dragen de items hun categorie mee?
  console.log('═══ OVERZICHTSPAGINA /restaurants/');
  const lijst = await haal(`${BASE}/restaurants/`);

  console.log('\n   ── alle data-attributen op lijst-items ──');
  const attrs = new Set();
  for (const m of lijst.matchAll(/<a[^>]*class="[^"]*item[^"]*"[^>]*>/g)) {
    for (const a of m[0].matchAll(/(data-[a-z_-]+)="([^"]*)"/g)) {
      attrs.add(`${a[1]} = "${a[2].slice(0, 60)}"`);
    }
  }
  if (attrs.size) [...attrs].slice(0, 15).forEach((a) => console.log(`   ${a}`));
  else console.log('   (geen data-attributen op lijst-items gevonden)');

  venster(lijst, '<a[^>]*class="[^"]*item[^"]*"', 'eerste lijst-item', 0, 900);

  // 2) Een recensiepagina: wat staat er rond de eigen titel/adres?
  const eerste = lijst.match(/"permalink":"([^"]+)"/);
  if (!eerste) return console.log('\nGeen permalink gevonden.');
  const url = eerste[1].replace(/\\\//g, '/');

  console.log(`\n\n═══ RECENSIEPAGINA ${url}`);
  const pagina = await haal(url);

  venster(pagina, 'class="bigTitle"', 'rond de titel (bigTitle)', 300, 1400);
  venster(pagina, 'class="innerAddress"', 'rond het adres (innerAddress)', 200, 900);

  console.log('\n   ── links naar filters op deze pagina (?_type_food= / ?_diet=) ──');
  const links = new Set();
  for (const m of pagina.matchAll(/\?_(type_food|diet)=([^"'>]+)"[^>]*>([^<]*)</g)) {
    links.add(`_${m[1]}=${m[2]}  →  ${schoon(m[3])}`);
  }
  if (links.size) [...links].forEach((l) => console.log(`   ${l}`));
  else console.log('   (geen filterlinks gevonden)');

  console.log('\n   ── alle class-namen die op een label lijken ──');
  const klassen = new Set();
  for (const m of pagina.matchAll(/class="([^"]+)"/g)) {
    for (const k of m[1].split(/\s+/)) {
      if (/label|tag|cat|type|soort|keuken|diet/i.test(k)) klassen.add(k);
    }
  }
  [...klassen].slice(0, 25).forEach((k) => console.log(`   ${k}`));
})().catch((e) => {
  console.error('\nFout:', e.message);
  process.exit(1);
});
