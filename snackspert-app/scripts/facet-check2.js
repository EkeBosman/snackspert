#!/usr/bin/env node
/**
 * Hertest met de JUISTE filternamen (_type_food en _diet), die uit de footer
 * van de site komen. Als filteren via de URL werkt, kan de app alle
 * categorieen en dieten in ~20 verzoeken ophalen in plaats van 755 pagina's.
 *
 * Verandert niets. Gebruik: node scripts/facet-check2.js
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

function markers(html) {
  const m = html.match(/restaurantLocations\s*=\s*(\[[\s\S]*?\])\s*;?\s*<\/script>/);
  if (!m) return null;
  try {
    return JSON.parse(m[1]);
  } catch {
    return null;
  }
}

/** Haal de filterlinks uit de footer: ?_type_food=... en ?_diet=... */
function filterLinks(html, param) {
  const uit = new Map();
  const re = new RegExp(`\\?_${param}=([^"'>]+)"[^>]*>([^<]+)<`, 'g');
  let m;
  while ((m = re.exec(html)) !== null) {
    const slug = decodeURIComponent(m[1]).trim();
    const label = m[2].replace(/&amp;/g, '&').trim();
    if (slug && !uit.has(slug)) uit.set(slug, label);
  }
  return uit;
}

(async () => {
  console.log('Basispagina ophalen ...');
  const basis = await haal(`${BASE}/restaurants/`);
  const basisAantal = markers(basis)?.length ?? null;
  console.log(`   markers zonder filter: ${basisAantal}\n`);

  const soorten = filterLinks(basis, 'type_food');
  const dieten = filterLinks(basis, 'diet');

  console.log(`Categorieen in de footer (${soorten.size}):`);
  for (const [slug, label] of soorten) console.log(`   ${slug.padEnd(20)} ${label}`);
  console.log(`\nDieten in de footer (${dieten.size}):`);
  for (const [slug, label] of dieten) console.log(`   ${slug.padEnd(20)} ${label}`);

  const test = async (param, slug) => {
    const url = `${BASE}/restaurants/?_${param}=${encodeURIComponent(slug)}`;
    try {
      const lijst = markers(await haal(url));
      if (!lijst) return console.log(`   ?_${param}=${slug}  →  geen markers gevonden`);
      const gefilterd = basisAantal != null && lijst.length < basisAantal;
      console.log(
        `   ?_${param}=${slug}  →  ${gefilterd ? '✅ GEFILTERD' : '❌ niet gefilterd'} (${lijst.length} van ${basisAantal})`
      );
      if (gefilterd && lijst[0]) console.log(`        voorbeeld: ${lijst[0].title}`);
    } catch (e) {
      console.log(`   ?_${param}=${slug}  →  fout: ${e.message}`);
    }
  };

  console.log('\nFilteren via de URL testen:');
  const eersteSoort = [...soorten.keys()][0] || 'hamburger';
  await test('type_food', eersteSoort);
  if (soorten.has('hamburger')) await test('type_food', 'hamburger');
  for (const slug of [...dieten.keys()].slice(0, 2)) await test('diet', slug);

  // Combineren? (categorie + dieet tegelijk)
  if (soorten.size && dieten.size) {
    const url = `${BASE}/restaurants/?_type_food=${[...soorten.keys()][0]}&_diet=${[...dieten.keys()][0]}`;
    try {
      const n = markers(await haal(url))?.length;
      console.log(`   combinatie van beide filters  →  ${n} van ${basisAantal}`);
    } catch (e) {
      console.log(`   combinatie  →  fout: ${e.message}`);
    }
  }
})().catch((e) => {
  console.error('\nFout:', e.message);
  process.exit(1);
});
