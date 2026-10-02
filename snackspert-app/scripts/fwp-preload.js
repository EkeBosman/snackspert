#!/usr/bin/env node
/**
 * Mijn eerdere metingen waren fout: ik keek naar het aantal markers
 * (restaurantLocations), en dat is de hele dataset — die verandert nooit mee
 * met een filter. Dit script meet wat er wel verandert: FWP_JSON.preload_data.
 *
 * Verandert niets aan de site. Schrijft fwp-json.json (volledige dump).
 *
 * Gebruik: node scripts/fwp-preload.js
 */

const fs = require('fs');
const path = require('path');

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

async function json(url) {
  try {
    const r = await fetch(url, { headers: { 'User-Agent': UA } });
    const tekst = await r.text();
    let data = null;
    try { data = JSON.parse(tekst); } catch {}
    return { ok: r.ok, status: r.status, data, totaal: r.headers.get('X-WP-Total') };
  } catch (e) {
    return { ok: false, status: 0, data: null, fout: e.message };
  }
}

/** Haal een JS-objectliteraal uit de pagina: var NAAM = {...}; */
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

const schoon = (s) => String(s).replace(/\s+/g, ' ').trim();

/** Zoek overal in een object naar iets wat op een resultaatteller lijkt. */
function zoekTellers(obj, pad = '', uit = []) {
  if (!obj || typeof obj !== 'object') return uit;
  for (const [k, v] of Object.entries(obj)) {
    const p = pad ? `${pad}.${k}` : k;
    if (typeof v === 'number' && /total|rows|count|pages|per_page|page/i.test(k)) {
      uit.push([p, v]);
    } else if (typeof v === 'object') {
      if (uit.length < 40) zoekTellers(v, p, uit);
    }
  }
  return uit;
}

/** Permalinks van de restaurants in de zichtbare lijst (niet de kaartdata). */
function lijstLinks(html) {
  const template = html.match(/<div[^>]*class="[^"]*facetwp-template[^"]*"[^>]*>([\s\S]*?)(?=<div[^>]*class="[^"]*facetwp-(?:pager|facet)|<footer)/i);
  const blok = template ? template[1] : html;
  const uit = new Set();
  for (const m of blok.matchAll(/href="(https?:\/\/snackspert\.nl\/[^"]+)"/g)) {
    const u = m[1].replace(/[#?].*$/, '').replace(/\/$/, '');
    const deel = u.split('/').pop();
    if (deel && !/^(restaurants|category|tag|author|feed|page|wp-content|wp-json|privacy|contact|over|blog)$/i.test(deel)) {
      uit.add(deel);
    }
  }
  return { slugs: [...uit], blokLengte: blok.length, blokGevonden: !!template };
}

(async () => {
  // ── 1. De ongefilterde pagina volledig uitpluizen ───────────────
  console.log('1) Ongefilterde pagina: wat zit er in FWP_JSON?\n');
  const basis = await haal(`${BASE}/restaurants/`);
  const fwp = jsObject(basis, 'FWP_JSON');

  if (!fwp) {
    console.log('   FWP_JSON niet te lezen. Stop.');
    return;
  }
  fs.writeFileSync(path.join(__dirname, 'fwp-json.json'), JSON.stringify(fwp, null, 2));
  console.log(`   top-level velden: ${Object.keys(fwp).join(', ')}`);
  if (fwp.preload_data) {
    console.log(`   preload_data velden: ${Object.keys(fwp.preload_data).join(', ')}`);
  }
  console.log('\n   alles wat op een teller lijkt:');
  const tellers = zoekTellers(fwp);
  if (tellers.length) tellers.forEach(([p, v]) => console.log(`      ${p.padEnd(44)} ${v}`));
  else console.log('      (geen enkele teller gevonden)');

  // Waar komt het filter vandaan? (FacetWP noemt dit de "source")
  console.log('\n   facet-definities (source = waar de waarden vandaan komen):');
  const bronnen = [];
  (function zoekBronnen(o, pad = '') {
    if (!o || typeof o !== 'object') return;
    for (const [k, v] of Object.entries(o)) {
      const p = pad ? `${pad}.${k}` : k;
      if (k === 'source' && typeof v === 'string') bronnen.push([pad, v]);
      else if (typeof v === 'object' && bronnen.length < 20) zoekBronnen(v, p);
    }
  })(fwp);
  if (bronnen.length) bronnen.forEach(([p, v]) => console.log(`      ${p.padEnd(40)} source=${v}`));
  else console.log('      (niet in FWP_JSON; dan zit het alleen server-side)');

  const basisLijst = lijstLinks(basis);
  console.log(
    `\n   zichtbare lijst: ${basisLijst.slugs.length} restaurants ` +
    `(template-blok ${basisLijst.blokGevonden ? 'gevonden' : 'NIET gevonden'}, ${basisLijst.blokLengte} tekens)`
  );
  console.log(`   voorbeeld: ${basisLijst.slugs.slice(0, 6).join(', ')}`);
  if (!basisLijst.blokGevonden) {
    const i = basis.search(/facetwp-template/i);
    if (i >= 0) console.log(`\n   HTML rond facetwp-template:\n   ${schoon(basis.slice(i - 120, i + 1200))}`);
  }

  // ── 2. Nu filteren, en de juiste dingen vergelijken ─────────────
  console.log('\n\n2) Filteren via de URL — nu gemeten op de lijst en de tellers');
  const proeven = [
    '_category=hamburger',
    '_category=5-sterren',
    '_diet=vega',
    '_type_food=hamburger',
  ];
  for (const p of proeven) {
    try {
      const html = await haal(`${BASE}/restaurants/?${p}`);
      const f = jsObject(html, 'FWP_JSON');
      const t = zoekTellers(f || {});
      const rijen = t.find(([k]) => /total_rows/i.test(k))?.[1];
      const l = lijstLinks(html);
      const anders = l.slugs.length !== basisLijst.slugs.length ||
        l.slugs.some((s, i) => s !== basisLijst.slugs[i]);
      console.log(
        `   ?${p.padEnd(24)} lijst=${String(l.slugs.length).padStart(3)} ` +
        `total_rows=${rijen ?? '-'}  →  ${anders ? '✅ ANDERE RESULTATEN' : '❌ identiek aan ongefilterd'}`
      );
      if (anders) console.log(`        ${l.slugs.slice(0, 6).join(', ')}`);
    } catch (e) {
      console.log(`   ?${p.padEnd(24)} fout: ${e.message}`);
    }
  }

  // ── 3. Zijn die 20 categorieen een gewone WordPress-taxonomie? ──
  console.log('\n\n3) Zitten die 20 categorieen toch in de API, onder een andere naam?');
  const typen = await json(`${BASE}/wp-json/wp/v2/types`);
  if (typen.ok && typen.data) {
    console.log('   posttypes:');
    for (const [k, t] of Object.entries(typen.data)) {
      console.log(`      ${k.padEnd(18)} rest_base=${String(t.rest_base).padEnd(18)} taxonomieen: ${(t.taxonomies || []).join(',') || '-'}`);
    }
  }

  const bekend = ['aziatisch', 'hamburger', 'kroket', 'shoarma-doner', 'frietpatat'];
  for (const basePath of ['categories', 'post-category', 'post-location']) {
    const r = await json(`${BASE}/wp-json/wp/v2/${basePath}?per_page=100`);
    if (!r.ok || !Array.isArray(r.data)) {
      console.log(`   /${basePath}  →  HTTP ${r.status}`);
      continue;
    }
    const slugs = r.data.map((t) => t.slug);
    const raak = bekend.filter((b) => slugs.includes(b));
    console.log(`   /${basePath}  →  ${r.data.length} termen, ${raak.length}/${bekend.length} van onze slugs aanwezig ${raak.length ? '✅' : ''}`);
    if (raak.length) {
      r.data
        .filter((t) => bekend.includes(t.slug))
        .forEach((t) => console.log(`        id=${String(t.id).padEnd(6)} ${t.slug.padEnd(18)} ${t.count}x`));
      // Welke posts hangen eraan?
      const h = r.data.find((t) => t.slug === 'hamburger');
      if (h) {
        for (const pt of ['posts', 'restaurant', 'locatie']) {
          const q = await json(`${BASE}/wp-json/wp/v2/${pt}?per_page=3&${basePath === 'categories' ? 'categories' : basePath}=${h.id}&_fields=slug,link`);
          console.log(
            `        /${pt}?${basePath === 'categories' ? 'categories' : basePath}=${h.id}  →  HTTP ${q.status}` +
            (q.ok ? `  X-WP-Total=${q.totaal}  ${Array.isArray(q.data) ? q.data.map((x) => x.slug).join(', ') : ''}` : '')
          );
        }
      }
    }
  }
})().catch((e) => {
  console.error('\nFout:', e.message);
  process.exit(1);
});
