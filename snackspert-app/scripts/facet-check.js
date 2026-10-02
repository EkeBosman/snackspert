#!/usr/bin/env node
/**
 * Diagnose: kan de app de filters (categorie + dieet) rechtstreeks van de
 * FacetWP-pagina halen, in plaats van 761 recensiepagina's te scrapen?
 *
 * Dit script verandert niets — het kijkt alleen en rapporteert.
 *
 * Gebruik: node scripts/facet-check.js
 */

const BASE = 'https://snackspert.nl';
const PAGINA = `${BASE}/restaurants/`;
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

/** Aantal markers in de ingebedde restaurantLocations-array. */
function aantalMarkers(html) {
  const m = html.match(/restaurantLocations\s*=\s*(\[[\s\S]*?\])\s*;?\s*<\/script>/);
  if (!m) return null;
  try {
    return JSON.parse(m[1]).length;
  } catch {
    return null;
  }
}

/**
 * Zoek de facet-blokken en hun keuzemogelijkheden.
 * We knippen op de openings-tags (niet op </div>), want de aanvinkvakjes
 * zitten genest en dan zou het blok te vroeg eindigen.
 */
function facets(html) {
  const open = /<div[^>]*class="[^"]*facetwp-facet[^"]*"[^>]*data-name="([^"]+)"[^>]*data-type="([^"]+)"[^>]*>/g;
  const starts = [];
  let m;
  while ((m = open.exec(html)) !== null) {
    starts.push({ naam: m[1], type: m[2], tagStart: m.index, inhoudStart: m.index + m[0].length });
  }

  return starts.map((s, i) => {
    const eind = i + 1 < starts.length
      ? starts[i + 1].tagStart
      : Math.min(html.length, s.inhoudStart + 12000);
    const blok = html.slice(s.inhoudStart, eind);

    const opties = [];
    const gezien = new Set();
    const voegToe = (slug, ruw) => {
      const label = ruw.replace(/<[^>]*>/g, '').trim();
      if (slug && !gezien.has(slug)) {
        gezien.add(slug);
        opties.push({ slug, label });
      }
    };
    for (const o of blok.matchAll(/data-value="([^"]*)"[^>]*>([\s\S]*?)</g)) voegToe(o[1], o[2]);
    for (const o of blok.matchAll(/<option[^>]*value="([^"]+)"[^>]*>([\s\S]*?)<\/option>/g)) voegToe(o[1], o[2]);

    return { naam: s.naam, type: s.type, opties };
  });
}

(async () => {
  console.log('Basispagina ophalen ...');
  const basis = await haal(PAGINA);
  const basisAantal = aantalMarkers(basis);
  console.log(`   markers zonder filter: ${basisAantal ?? 'NIET GEVONDEN'}\n`);

  const gevonden = facets(basis);
  if (!gevonden.length) {
    console.log('Geen facet-blokken herkend. Ruwe hints uit de HTML:');
    for (const m of basis.matchAll(/facetwp-facet[^"]*"[^>]*data-name="([^"]+)"[^>]*data-type="([^"]+)"/g)) {
      console.log(`   data-name="${m[1]}"  data-type="${m[2]}"`);
    }
  } else {
    console.log('Gevonden filters:');
    for (const f of gevonden) {
      console.log(`   ${f.naam} (${f.type}) — ${f.opties.length} opties`);
      f.opties.slice(0, 25).forEach((o) => console.log(`      ${o.slug}  →  ${o.label}`));
      if (f.opties.length > 25) console.log(`      ... en nog ${f.opties.length - 25}`);
    }
  }
  console.log();

  // Test of filteren via de URL ook de markers filtert.
  const proeven = [];
  const cat = gevonden.find((f) => /categor/i.test(f.naam));
  const diet = gevonden.find((f) => /diet|dieet/i.test(f.naam));
  if (cat?.opties.length) proeven.push([cat.naam, cat.opties[0].slug]);
  if (diet?.opties.length) for (const o of diet.opties.slice(0, 2)) proeven.push([diet.naam, o.slug]);
  // Terugvaloptie als de opties niet uitgelezen konden worden:
  if (!proeven.length) proeven.push(['category', 'hamburger'], ['diet', 'vega']);

  console.log('Filteren via de URL testen:');
  for (const [naam, slug] of proeven) {
    const url = `${PAGINA}?_${naam}=${encodeURIComponent(slug)}`;
    try {
      const n = aantalMarkers(await haal(url));
      const oordeel =
        n == null ? 'geen markers gevonden'
        : basisAantal != null && n < basisAantal ? `✅ GEFILTERD (${n} van ${basisAantal})`
        : `❌ niet gefilterd (${n})`;
      console.log(`   ?_${naam}=${slug}  →  ${oordeel}`);
    } catch (e) {
      console.log(`   ?_${naam}=${slug}  →  fout: ${e.message}`);
    }
  }

  // Hoe staan dieet-labels op een recensiepagina zelf?
  console.log('\nEén recensiepagina bekijken op dieet-labels ...');
  const eerste = basis.match(/"permalink":"([^"]+)"/);
  if (eerste) {
    const url = eerste[1].replace(/\\\//g, '/');
    const html = await haal(url);
    const klassen = new Set();
    for (const m of html.matchAll(/class="([^"]*(?:label|tag|cat|diet|dieet)[^"]*)"/gi)) {
      klassen.add(m[1].trim());
    }
    console.log(`   ${url}`);
    console.log('   class-namen die op labels lijken:');
    [...klassen].slice(0, 20).forEach((k) => console.log(`      ${k}`));
    const vega = /vega/i.test(html);
    console.log(`   bevat het woord "vega": ${vega ? 'ja' : 'nee'}`);
  }
})().catch((e) => {
  console.error('\nFout:', e.message);
  process.exit(1);
});
