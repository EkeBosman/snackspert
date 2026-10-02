#!/usr/bin/env node
/**
 * Toont hoe categorie- en dieet-labels in de HTML van een recensiepagina staan,
 * zodat de app ze betrouwbaar kan uitlezen. Verandert niets.
 *
 * Gebruik: node scripts/diet-markup.js
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

/** Print de HTML rondom elke treffer, opgeschoond en ingekort. */
function toonContext(html, naald, label, max = 3) {
  const re = new RegExp(naald, 'gi');
  let m, n = 0;
  console.log(`\n   ── ${label} ──`);
  while ((m = re.exec(html)) !== null && n < max) {
    const van = Math.max(0, m.index - 180);
    const tot = Math.min(html.length, m.index + 320);
    const stuk = html.slice(van, tot).replace(/\s+/g, ' ').trim();
    console.log(`   ...${stuk}...`);
    n++;
  }
  if (n === 0) console.log('   (niet gevonden)');
}

(async () => {
  console.log('Permalinks ophalen ...');
  const basis = await haal(`${BASE}/restaurants/`);
  const alle = [...basis.matchAll(/"permalink":"([^"]+)"/g)].map((m) =>
    m[1].replace(/\\\//g, '/')
  );
  console.log(`   ${alle.length} gevonden.`);

  // La Calle bevatte het woord "vega"; daarnaast twee willekeurige pagina's.
  const teBekijken = [
    alle.find((u) => /la-calle/.test(u)) || alle[0],
    alle[5],
    alle[50],
  ].filter(Boolean);

  for (const url of teBekijken) {
    console.log(`\n═══ ${url}`);
    const html = await haal(url);
    toonContext(html, 'class="[^"]*diet[^"]*"', 'class bevat "diet"');
    toonContext(html, 'class="[^"]*catLabel[^"]*"', 'class bevat "catLabel"');
    toonContext(html, 'class="label"', 'class="label"');
    toonContext(html, 'vega', 'het woord "vega"', 2);
  }
})().catch((e) => {
  console.error('\nFout:', e.message);
  process.exit(1);
});
