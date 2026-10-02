#!/usr/bin/env node
/**
 * Filteren via ?_category= werkt. Nu de laatste vraag: wat staat er in een
 * lijst-item? Als de sterren en het adres er al in staan, kan de app alles uit
 * ~50 lijstpagina's halen in plaats van 761 losse recensiepagina's.
 *
 * Verandert niets aan de site. Gebruik: node scripts/item-markup.js
 */

const BASE = 'https://snackspert.nl';
const UA =
  'Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1';

async function haal(url) {
  const ctrl = new AbortController();
  const t = setTimeout(() => ctrl.abort(), 30000);
  try {
    const r = await fetch(url, { signal: ctrl.signal, headers: { 'User-Agent': UA } });
    if (!r.ok) throw new Error(`HTTP ${r.status}`);
    return await r.text();
  } finally {
    clearTimeout(t);
  }
}

function jsObject(html, naam) {
  const i = html.indexOf(naam);
  if (i < 0) return null;
  const start = html.indexOf('{', i);
  if (start < 0) return null;
  let diep = 0, inString = false, quote = '';
  for (let j = start; j < html.length; j++) {
    const c = html[j];
    if (inString) {
      if (c === '\\') j++;
      else if (c === quote) inString = false;
      continue;
    }
    if (c === '"' || c === "'") { inString = true; quote = c; continue; }
    if (c === '{') diep++;
    else if (c === '}' && --diep === 0) {
      try { return JSON.parse(html.slice(start, j + 1)); } catch { return null; }
    }
  }
  return null;
}

/** De template-HTML zoals FacetWP die voorlaadt — dat is precies de lijst. */
function template(html) {
  return jsObject(html, 'FWP_JSON')?.preload_data?.template ?? null;
}

function pager(html) {
  return jsObject(html, 'FWP_JSON')?.preload_data?.settings?.pager ?? null;
}

/** Knip de template op in items, op basis van de meest voorkomende openings-tag. */
function splitsItems(tpl) {
  // Zoek de tag die 24 keer voorkomt — dat is het item.
  const kandidaten = new Map();
  for (const m of tpl.matchAll(/<(\w+)[^>]*class="([^"]*)"/g)) {
    const sleutel = `${m[1]}.${m[2].trim().split(/\s+/).join('.')}`;
    kandidaten.set(sleutel, (kandidaten.get(sleutel) || 0) + 1);
  }
  const top = [...kandidaten.entries()].sort((a, b) => b[1] - a[1]).slice(0, 6);
  console.log('   meest voorkomende elementen in de template:');
  top.forEach(([k, n]) => console.log(`      ${String(n).padStart(3)}x  ${k}`));

  const beste = top.find(([, n]) => n >= 20 && n <= 30) || top[0];
  if (!beste) return [];
  const [tag, ...klassen] = beste[0].split('.');
  const re = new RegExp(`<${tag}[^>]*class="[^"]*${klassen[0]}[^"]*"[\\s\\S]*?(?=<${tag}[^>]*class="[^"]*${klassen[0]}|$)`, 'g');
  return [...tpl.matchAll(re)].map((m) => m[0]);
}

(async () => {
  console.log('Pagina 1 van de hamburgers ophalen ...\n');
  const html = await haal(`${BASE}/restaurants/?_category=hamburger`);
  const tpl = template(html);
  const p = pager(html);
  console.log(`   pager: ${JSON.stringify(p)}`);

  if (!tpl) {
    console.log('   Geen template in preload_data. Stop.');
    return;
  }
  console.log(`   template: ${tpl.length} tekens\n`);

  const items = splitsItems(tpl);
  console.log(`\n   ${items.length} items herkend.`);

  console.log('\n═══ EERSTE ITEM, LETTERLIJK ═══');
  console.log(items[0] ? items[0].replace(/>\s*</g, '>\n<') : tpl.slice(0, 2500));

  if (items[1]) {
    console.log('\n═══ TWEEDE ITEM, LETTERLIJK ═══');
    console.log(items[1].replace(/>\s*</g, '>\n<'));
  }

  // Wat voor gegevens zitten er in?
  console.log('\n═══ WAT ZIT ER IN DE ITEMS ═══');
  const attrs = new Set();
  for (const m of tpl.matchAll(/(data-[a-z0-9_-]+)="([^"]*)"/gi)) {
    if (attrs.size < 25) attrs.add(`${m[1]} = "${m[2].slice(0, 50)}"`);
  }
  console.log('   data-attributen:');
  attrs.size ? [...attrs].forEach((a) => console.log(`      ${a}`)) : console.log('      (geen)');

  const klassen = new Set();
  for (const m of tpl.matchAll(/class="([^"]+)"/g)) {
    m[1].split(/\s+/).forEach((k) => klassen.add(k));
  }
  console.log(`   class-namen: ${[...klassen].join(', ')}`);

  console.log(`   sterren-tekens aanwezig: ${/★|⭐|&#9733;|star/i.test(tpl) ? 'JA' : 'nee'}`);
  console.log(`   afbeeldingen: ${(tpl.match(/<img/g) || []).length}`);

  // ── Werkt paginering, en kan per_page omhoog? ──────────────────
  console.log('\n═══ PAGINERING ═══');
  const slugsVan = (h) => {
    const t = template(h) || '';
    const uit = new Set();
    for (const m of t.matchAll(/href="https?:\/\/snackspert\.nl\/([a-z0-9][a-z0-9-]+)\/?"/gi)) uit.add(m[1]);
    return [...uit];
  };
  const p1 = slugsVan(html);
  console.log(`   pagina 1: ${p1.length} slugs — ${p1.slice(0, 4).join(', ')}`);

  for (const proef of ['_category=hamburger&_paged=2', '_category=hamburger&paged=2']) {
    try {
      const h = await haal(`${BASE}/restaurants/?${proef}`);
      const s = slugsVan(h);
      const anders = s.length && s[0] !== p1[0];
      console.log(`   ?${proef.padEnd(32)} ${s.length} slugs  ${anders ? '✅ pagina 2' : '❌ zelfde als pagina 1'}`);
      if (anders) console.log(`        ${s.slice(0, 4).join(', ')}`);
    } catch (e) {
      console.log(`   ?${proef.padEnd(32)} fout: ${e.message}`);
    }
  }

  console.log('\n   Kan er meer in één keer?');
  for (const proef of ['_category=hamburger&_per_page=100', '_category=hamburger&per_page=100']) {
    try {
      const h = await haal(`${BASE}/restaurants/?${proef}`);
      const s = slugsVan(h);
      console.log(`   ?${proef.padEnd(34)} ${s.length} slugs  ${s.length > 24 ? '✅ MEER DAN 24' : '❌ blijft 24'}`);
    } catch (e) {
      console.log(`   ?${proef.padEnd(34)} fout: ${e.message}`);
    }
  }
})().catch((e) => {
  console.error('\nFout:', e.message);
  process.exit(1);
});
