#!/usr/bin/env node
/**
 * Twee laatste gokjes, beide goedkoop. Ik bouw ondertussen al verder — dit kan
 * de sterren alleen nóg sneller maken als het meezit.
 *
 *   1. restaurantLocations (de kaartdata) — welke velden zitten daar eigenlijk
 *      in? Als het popupje op je site een beoordeling toont, staat de
 *      waardering daar misschien al in. Dan zijn alle sterren één verzoek.
 *   2. De oude ACF-REST-route (/wp-json/acf/v3/...), die soms nog aan staat
 *      terwijl het moderne acf-veld leeg blijft.
 *
 * Verandert niets aan de site. Gebruik: node scripts/laatste-check.js
 */

const BASE = 'https://snackspert.nl';
const UA =
  'Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1';

async function haal(url) {
  const r = await fetch(url, { headers: { 'User-Agent': UA } });
  return { ok: r.ok, status: r.status, tekst: await r.text() };
}

(async () => {
  console.log('1) Welke velden zitten er in de kaartdata (restaurantLocations)?\n');
  const html = (await haal(`${BASE}/restaurants/`)).tekst;
  const m = html.match(/restaurantLocations\s*=\s*(\[[\s\S]*?\])\s*;/);
  if (!m) {
    console.log('   niet gevonden');
  } else {
    const lijst = JSON.parse(m[1]);
    console.log(`   ${lijst.length} items`);
    console.log(`   velden: ${Object.keys(lijst[0] || {}).join(', ')}`);
    console.log('\n   eerste twee items, volledig:');
    lijst.slice(0, 2).forEach((x) => console.log(`      ${JSON.stringify(x)}`));
    const sterrig = Object.keys(lijst[0] || {}).filter((k) =>
      /ster|star|rating|score|waarde|cijfer/i.test(k)
    );
    console.log(
      `\n   velden die op een beoordeling lijken: ${sterrig.length ? '✅ ' + sterrig.join(', ') : 'geen'}`
    );
    const metSter = lijst.filter((x) => /[⭐★]/.test(JSON.stringify(x))).length;
    console.log(`   items met een ster-emoji ergens in: ${metSter} ${metSter ? '✅' : ''}`);
  }

  console.log('\n\n2) De oude ACF-REST-route\n');
  const een = JSON.parse((await haal(`${BASE}/wp-json/wp/v2/restaurant?per_page=1&_fields=id,slug`)).tekst)[0];
  console.log(`   test op: ${een.slug} (id ${een.id})`);
  for (const pad of [
    `/wp-json/acf/v3/restaurant/${een.id}`,
    `/wp-json/acf/v3/restaurant/${een.id}/fields`,
    `/wp-json/wp/v2/restaurant/${een.id}?_fields=meta`,
  ]) {
    const r = await haal(`${BASE}${pad}`);
    const kort = r.tekst.replace(/\s+/g, ' ').slice(0, 260);
    const heeftSterren = /[⭐★]/.test(r.tekst);
    console.log(`   ${pad}`);
    console.log(`      HTTP ${r.status}${heeftSterren ? '  ✅ BEVAT STERREN' : ''}  ${kort}`);
  }
})().catch((e) => {
  console.error('\nFout:', e.message);
  process.exit(1);
});
