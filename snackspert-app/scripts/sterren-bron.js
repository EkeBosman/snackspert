#!/usr/bin/env node
/**
 * De sterren zijn het laatste probleem. Het veld "content" is leeg in de API,
 * dus de recensietekst zit in een veld dat WordPress niet uitlevert. Vier
 * mogelijke bronnen, alle vier hier getest:
 *
 *   A. yoast_head_json — die komt al mee in de 8 API-verzoeken. Als Yoast de
 *      beschrijving uit de recensie haalt, staan de sterren er gratis in.
 *   B. de RSS-feed — WordPress zet daar normaal de volledige tekst in.
 *   C. alleen het begin van de recensiepagina opvragen (HTTP Range). Als de
 *      sterren in de eerste 25 kB staan, is het 5x minder data.
 *   D. de volledige pagina — waar staan de sterren precies?
 *
 * En: kan _per_page hoger dan 100?
 *
 * Verandert niets aan de site. Gebruik: node scripts/sterren-bron.js
 */

const BASE = 'https://snackspert.nl';
const API = `${BASE}/wp-json/wp/v2`;
const UA =
  'Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1';

async function haal(url, extraHeaders = {}) {
  const ctrl = new AbortController();
  const t = setTimeout(() => ctrl.abort(), 30000);
  try {
    const r = await fetch(url, {
      signal: ctrl.signal,
      headers: { 'User-Agent': UA, ...extraHeaders },
    });
    const tekst = await r.text();
    return { ok: r.ok, status: r.status, tekst, lengte: tekst.length, type: r.headers.get('content-type') };
  } catch (e) {
    return { ok: false, status: 0, tekst: '', lengte: 0, fout: e.message };
  } finally {
    clearTimeout(t);
  }
}

const schoon = (s) =>
  String(s).replace(/<[^>]*>/g, ' ').replace(/&amp;/g, '&').replace(/\s+/g, ' ').trim();

const sterrenIn = (s) => (String(s).match(/[⭐★]️?/g) || []).length;

/** Toon een venster rond de eerste ster. */
function rondSter(tekst, voor = 200, na = 200) {
  const i = tekst.search(/[⭐★]/);
  if (i < 0) return null;
  return schoon(tekst.slice(Math.max(0, i - voor), i + na));
}

(async () => {
  // ── A. Yoast ───────────────────────────────────────────────────
  console.log('A) yoast_head_json — komt al mee in de API-verzoeken\n');
  const y = await haal(`${API}/restaurant?per_page=5&_fields=slug,yoast_head_json`);
  let yoastWerkt = false;
  if (y.ok) {
    const data = JSON.parse(y.tekst);
    for (const p of data) {
      const yh = p.yoast_head_json || {};
      const kandidaten = {
        description: yh.description,
        og_description: yh.og_description,
        twitter_description: yh.twitter_description,
      };
      const treffer = Object.entries(kandidaten).find(([, v]) => v && sterrenIn(v) > 0);
      if (treffer) yoastWerkt = true;
      console.log(`   ${String(p.slug).padEnd(26)} ${treffer ? `✅ ${treffer[0]}: ${sterrenIn(treffer[1])} sterren` : '❌ geen sterren'}`);
      for (const [k, v] of Object.entries(kandidaten)) {
        if (v) console.log(`      ${k}: ${schoon(v).slice(0, 150)}`);
      }
      // Zit er een rating in de schema-data?
      const graf = yh.schema?.['@graph'] || [];
      const rating = graf.find((g) => g.reviewRating || g.aggregateRating || g.ratingValue);
      if (rating) console.log(`      ✅ schema-rating: ${JSON.stringify(rating).slice(0, 200)}`);
    }
  } else {
    console.log(`   HTTP ${y.status}`);
  }

  // ── B. RSS-feed ────────────────────────────────────────────────
  console.log('\n\nB) RSS-feed\n');
  for (const pad of ['/restaurant/feed/', '/feed/?post_type=restaurant', '/feed/']) {
    const r = await haal(`${BASE}${pad}`);
    if (!r.ok) {
      console.log(`   ${pad.padEnd(32)} HTTP ${r.status}`);
      continue;
    }
    const items = (r.tekst.match(/<item>/g) || []).length;
    const sterren = sterrenIn(r.tekst);
    const heeftEncoded = /content:encoded/.test(r.tekst);
    console.log(
      `   ${pad.padEnd(32)} HTTP ${r.status}  ${items} items, content:encoded=${heeftEncoded ? 'ja' : 'nee'}, ${sterren} sterren ${sterren > 0 ? '✅' : ''}`
    );
    if (sterren > 0) console.log(`      ${rondSter(r.tekst)}`);
  }

  // ── C+D. De recensiepagina: hoe vroeg staan de sterren? ────────
  console.log('\n\nC) Alleen het begin van een recensiepagina opvragen\n');
  const url = `${BASE}/restaurant/t-smikkelhoekje/`;

  const vol = await haal(url);
  console.log(`   volledige pagina: ${vol.lengte} tekens, ${sterrenIn(vol.tekst)} sterren`);
  const eersteSter = vol.tekst.search(/[⭐★]/);
  console.log(`   eerste ster staat op positie ${eersteSter} van ${vol.lengte} (${Math.round((eersteSter / vol.lengte) * 100)}%)`);

  for (const grens of [15000, 25000, 40000, 60000]) {
    const r = await haal(url, { Range: `bytes=0-${grens}` });
    const genoeg = sterrenIn(r.tekst) > 0;
    console.log(
      `   Range 0-${String(grens).padEnd(6)} HTTP ${r.status}  ${String(r.lengte).padStart(6)} tekens ontvangen, ` +
      `${sterrenIn(r.tekst)} sterren ${genoeg ? '✅' : ''}${r.lengte >= vol.lengte ? '  (server negeert Range)' : ''}`
    );
  }

  console.log('\n\nD) Waar staan de sterren in de pagina?\n');
  const venster = rondSter(vol.tekst, 400, 300);
  console.log(`   ${venster || '(geen sterren gevonden)'}`);
  // Welke class omsluit ze?
  const i = vol.tekst.search(/[⭐★]/);
  if (i >= 0) {
    const voor = vol.tekst.slice(Math.max(0, i - 1500), i);
    const klassen = [...voor.matchAll(/class="([^"]+)"/g)].slice(-5).map((m) => m[1]);
    console.log(`   dichtstbijzijnde classes ervoor: ${klassen.join(' | ')}`);
  }

  // ── E. Hoe hoog kan _per_page? ────────────────────────────────
  console.log('\n\nE) Hoe veel items kan één lijstverzoek geven?\n');
  const tel = (html) => {
    const m = html.match(
      /<div[^>]*class="[^"]*facetwp-template[^"]*"[^>]*>([\s\S]*?)(?=<div[^>]*class="[^"]*facetwp-(?:pager|facet)|<footer)/i
    );
    const blok = m ? m[1] : html;
    return new Set([...blok.matchAll(/href="https?:\/\/snackspert\.nl\/restaurant\/([^/"]+)\//gi)].map((x) => x[1])).size;
  };
  for (const n of [200, 500, 800]) {
    const r = await haal(`${BASE}/restaurants/?_per_page=${n}`);
    console.log(`   _per_page=${String(n).padEnd(5)} HTTP ${r.status}  ${r.lengte} tekens, ${tel(r.tekst)} items`);
  }
})().catch((e) => {
  console.error('\nFout:', e.message);
  process.exit(1);
});
