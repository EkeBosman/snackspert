#!/usr/bin/env node
/**
 * Het restaurant-object in de API heeft een "acf"-veld (Advanced Custom Fields).
 * Daar staat de categorie waarschijnlijk in — er is namelijk geen type_food-
 * taxonomie. Dit toont precies wat er in acf zit, en welke velden bij alle
 * restaurants voorkomen.
 *
 * Verandert niets aan de site. Schrijft alleen acf-dump.json.
 *
 * Gebruik: node scripts/acf-dump.js
 */

const fs = require('fs');
const path = require('path');

const API = 'https://snackspert.nl/wp-json/wp/v2';
const UA =
  'Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1';

async function json(url) {
  const ctrl = new AbortController();
  const t = setTimeout(() => ctrl.abort(), 30000);
  try {
    const r = await fetch(url, { signal: ctrl.signal, headers: { 'User-Agent': UA } });
    const body = await r.text();
    let data = null;
    try { data = JSON.parse(body); } catch {}
    return { ok: r.ok, status: r.status, data, paginas: r.headers.get('X-WP-TotalPages') };
  } catch (e) {
    return { ok: false, status: 0, data: null, fout: e.message };
  } finally {
    clearTimeout(t);
  }
}

/** Beschrijf een waarde kort, zonder paginas tekst uit te spugen. */
function beschrijf(v, diep = 0) {
  if (v === null || v === undefined) return String(v);
  if (Array.isArray(v)) {
    if (!v.length) return '[]';
    if (diep > 1) return `[${v.length} items]`;
    return `[ ${v.slice(0, 6).map((x) => beschrijf(x, diep + 1)).join(' | ')}${v.length > 6 ? ` ... +${v.length - 6}` : ''} ]`;
  }
  if (typeof v === 'object') {
    const sleutels = Object.keys(v);
    // Een ACF-term/relatie ziet er zo uit: {term_id, name, slug} of {ID, post_title}
    const korte = ['name', 'slug', 'title', 'post_title', 'label', 'term_id', 'ID'];
    const treffers = korte.filter((k) => k in v);
    if (treffers.length) return `{${treffers.map((k) => `${k}:${JSON.stringify(v[k])}`).join(', ')}}`;
    if (diep > 1) return `{${sleutels.length} velden}`;
    return `{ ${sleutels.slice(0, 8).map((k) => `${k}: ${beschrijf(v[k], diep + 1)}`).join(', ')} }`;
  }
  const s = String(v);
  return JSON.stringify(s.length > 120 ? s.slice(0, 120) + '…' : s);
}

/** Maak van een acf-waarde een platte lijst met labels (voor categorie/dieet). */
function naarLabels(v) {
  if (v === null || v === undefined || v === '' || v === false) return [];
  if (Array.isArray(v)) return v.flatMap(naarLabels);
  if (typeof v === 'object') {
    for (const k of ['name', 'label', 'slug', 'title', 'post_title']) {
      if (typeof v[k] === 'string') return [v[k]];
    }
    return [];
  }
  return [String(v)];
}

(async () => {
  console.log('Drie restaurants volledig uitpakken ...\n');
  const r3 = await json(`${API}/restaurant?per_page=3`);
  if (!r3.ok || !Array.isArray(r3.data)) {
    console.log(`Lijst niet op te halen (HTTP ${r3.status}${r3.fout ? ' - ' + r3.fout : ''})`);
    return;
  }

  for (const p of r3.data) {
    console.log(`═══ ${String(p.title?.rendered)}  (${p.slug})`);
    const acf = p.acf;
    if (!acf || typeof acf !== 'object' || !Object.keys(acf).length) {
      console.log(`   acf = ${beschrijf(acf)}   ← leeg of niet gevuld`);
    } else {
      for (const [k, v] of Object.entries(acf)) {
        console.log(`   acf.${k.padEnd(24)} = ${beschrijf(v)}`);
      }
    }
    // Yoast kan de categorie in de breadcrumbs of schema hebben.
    const bc = p.yoast_head_json?.schema?.['@graph']
      ?.find?.((g) => g['@type'] === 'BreadcrumbList')?.itemListElement;
    if (bc) console.log(`   breadcrumbs: ${bc.map((b) => b.name).join(' › ')}`);
    console.log();
  }

  // ─────────────────────────────────────────────────────────────
  console.log('Alle restaurants ophalen om te zien hoe goed de velden gevuld zijn ...');
  const eerste = await json(`${API}/restaurant?per_page=100&page=1`);
  const paginas = Number(eerste.paginas || 1);
  const rest = await Promise.all(
    Array.from({ length: Math.max(0, paginas - 1) }, (_, i) =>
      json(`${API}/restaurant?per_page=100&page=${i + 2}`)
    )
  );
  const alles = [eerste, ...rest].flatMap((r) => (Array.isArray(r.data) ? r.data : []));
  console.log(`   ${alles.length} restaurants in ${paginas} verzoeken.\n`);

  if (!alles.length) return;

  const velden = new Map(); // veld → {gevuld, voorbeelden:Set}
  for (const p of alles) {
    for (const [k, v] of Object.entries(p.acf || {})) {
      const info = velden.get(k) || { gevuld: 0, voorbeelden: new Set() };
      const labels = naarLabels(v);
      if (labels.length) {
        info.gevuld++;
        for (const l of labels.slice(0, 2)) {
          if (info.voorbeelden.size < 12) info.voorbeelden.add(l.slice(0, 40));
        }
      }
      velden.set(k, info);
    }
  }

  console.log('acf-velden, gesorteerd op hoe vaak ze gevuld zijn:');
  [...velden.entries()]
    .sort((a, b) => b[1].gevuld - a[1].gevuld)
    .forEach(([k, i]) => {
      console.log(`   ${k.padEnd(26)} ${String(i.gevuld).padStart(4)}/${alles.length}`);
      if (i.voorbeelden.size) console.log(`        bv: ${[...i.voorbeelden].join(' · ')}`);
    });

  // Welk veld lijkt het meest op de categorielijst die je me gaf?
  const bekend = ['hamburger', 'pizza', 'snackbar', 'kroket', 'frietpatat', 'broodjes',
    'shoarma', 'aziatisch', 'italiaans', 'grieks', 'wraps', 'spareribs', 'hotdogs',
    'bakker', 'mexicaans', 'spaans', 'midden-oosters', 'vega', 'vegan', 'borrel'];
  console.log('\nWelk veld bevat jouw categorie-/dieetwoorden?');
  let beste = null;
  for (const [k, i] of velden) {
    const raak = [...i.voorbeelden].filter((v) =>
      bekend.some((b) => v.toLowerCase().includes(b))
    ).length;
    if (raak) {
      console.log(`   ✅ acf.${k}  (${raak} van de voorbeelden matcht)`);
      if (!beste || raak > beste.raak) beste = { veld: k, raak };
    }
  }
  if (!beste) console.log('   (geen enkel acf-veld bevat ze — dan zit het elders)');

  const bestand = path.join(__dirname, 'acf-dump.json');
  fs.writeFileSync(
    bestand,
    JSON.stringify(
      alles.map((p) => ({
        slug: p.slug,
        titel: String(p.title?.rendered || '').replace(/&amp;/g, '&'),
        link: p.link,
        acf: p.acf,
      })),
      null,
      2
    )
  );
  console.log(`\n✅ Volledige dump: ${bestand}`);
})().catch((e) => {
  console.error('\nFout:', e.message);
  process.exit(1);
});
