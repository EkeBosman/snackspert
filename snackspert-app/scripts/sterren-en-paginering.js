#!/usr/bin/env node
/**
 * Twee laatste vragen:
 *
 *  1. Staan de sterren (de ⭐-emoji's uit je recensie) in het veld "content"
 *     van de REST API? Zo ja, dan hoeft de app geen 761 pagina's meer te
 *     scrapen — die sterren komen dan mee in 8 verzoeken.
 *  2. Werkt ?_paged=2, en kunnen er meer dan 24 per pagina? (Mijn vorige test
 *     meette dit fout: de permalink is /restaurant/<slug>/, met een padstuk
 *     dat mijn regex niet meenam.)
 *
 * Verandert niets aan de site. Schrijft sterren-dump.json.
 *
 * Gebruik: node scripts/sterren-en-paginering.js
 */

const fs = require('fs');
const path = require('path');

const BASE = 'https://snackspert.nl';
const API = `${BASE}/wp-json/wp/v2`;
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
  const tekst = await haal(url);
  return JSON.parse(tekst);
}

const schoon = (s) => String(s).replace(/<[^>]*>/g, ' ').replace(/&amp;/g, '&').replace(/&#8217;/g, '’').replace(/\s+/g, ' ').trim();

/** Zelfde logica als de app: ⭐ of ★ tellen, ½ erbij. */
function telSterren(tekst) {
  const volle = (tekst.match(/[⭐★]️?/g) || []).length;
  const halve = /½|½|1\/2/.test(tekst) ? 0.5 : 0;
  return volle + halve;
}

/** De lijst-items uit een /restaurants/-pagina. */
function items(html) {
  const m = html.match(
    /<div[^>]*class="[^"]*facetwp-template[^"]*"[^>]*>([\s\S]*?)(?=<div[^>]*class="[^"]*facetwp-(?:pager|facet)|<footer)/i
  );
  const blok = m ? m[1] : html;
  const uit = [];
  for (const a of blok.matchAll(/<a\s[^>]*href="https?:\/\/snackspert\.nl\/restaurant\/([^/"]+)\/?"[^>]*>([\s\S]*?)<\/a>/gi)) {
    const slug = a[1];
    const tag = a[0];
    uit.push({
      slug,
      titel: schoon((tag.match(/title="([^"]*)"/) || [])[1] || ''),
      dieet: ((tag.match(/data-diet="([^"]*)"/) || [])[1] || '').trim(),
      adres: schoon((a[2].match(/class="address"[^>]*>([\s\S]*?)<\/span>/i) || [])[1] || ''),
      foto: ((a[2].match(/background-image:url\('([^']+)'\)/) || [])[1] || ''),
    });
  }
  return uit;
}

function pager(html) {
  const m = html.match(/"pager"\s*:\s*(\{[^}]*\})/);
  try { return m ? JSON.parse(m[1]) : null; } catch { return null; }
}

(async () => {
  // ── 1. Sterren uit de REST API ────────────────────────────────
  console.log('1) Staan de sterren in het content-veld van de API?\n');
  const proef = await json(`${API}/restaurant?per_page=3&_fields=slug,title,content`);
  for (const p of proef) {
    const ruw = p.content?.rendered || '';
    const n = telSterren(ruw);
    console.log(`   ${String(p.slug).padEnd(26)} content=${String(ruw.length).padStart(6)} tekens, sterren=${n}`);
    const i = ruw.search(/[⭐★]/);
    if (i >= 0) console.log(`      rond de sterren: ...${schoon(ruw.slice(Math.max(0, i - 160), i + 120))}...`);
    else console.log(`      begin van de tekst: ${schoon(ruw).slice(0, 180)}...`);
  }

  console.log('\n   Alle restaurants ophalen (met content) ...');
  const paginas = 8;
  const brokken = await Promise.all(
    Array.from({ length: paginas }, (_, i) =>
      json(`${API}/restaurant?per_page=100&page=${i + 1}&_fields=slug,title,link,content`).catch(() => [])
    )
  );
  const alles = brokken.flat();
  const metSterren = alles.filter((p) => telSterren(p.content?.rendered || '') > 0);
  console.log(`   ${alles.length} restaurants, ${metSterren.length} met sterren in content (${Math.round((metSterren.length / Math.max(1, alles.length)) * 100)}%)`);

  const verdeling = {};
  for (const p of alles) {
    const n = telSterren(p.content?.rendered || '');
    verdeling[n] = (verdeling[n] || 0) + 1;
  }
  console.log('   verdeling van het aantal sterren:');
  Object.entries(verdeling)
    .sort((a, b) => Number(a[0]) - Number(b[0]))
    .forEach(([n, c]) => console.log(`      ${String(n).padStart(4)} sterren: ${c}`));

  // ── 2. Paginering, nu met de juiste regex ─────────────────────
  console.log('\n\n2) Paginering van de lijst');
  const p1 = await haal(`${BASE}/restaurants/?_category=hamburger`);
  const i1 = items(p1);
  console.log(`   pagina 1: ${i1.length} items — ${i1.slice(0, 3).map((x) => x.slug).join(', ')}`);
  console.log(`   pager: ${JSON.stringify(pager(p1))}`);

  for (const proefUrl of ['_category=hamburger&_paged=2', '_category=hamburger&paged=2']) {
    try {
      const h = await haal(`${BASE}/restaurants/?${proefUrl}`);
      const s = items(h);
      const anders = s.length > 0 && s[0].slug !== i1[0]?.slug;
      console.log(`   ?${proefUrl.padEnd(32)} ${String(s.length).padStart(3)} items  ${anders ? '✅ echt pagina 2' : '❌ zelfde als pagina 1'}`);
      if (anders) console.log(`        ${s.slice(0, 3).map((x) => x.slug).join(', ')}`);
    } catch (e) {
      console.log(`   ?${proefUrl.padEnd(32)} fout: ${e.message}`);
    }
  }

  console.log('\n   Kan er meer dan 24 in één keer?');
  for (const proefUrl of ['_category=hamburger&_per_page=100', '_category=hamburger&per_page=100', '_category=hamburger&_pp=100']) {
    try {
      const s = items(await haal(`${BASE}/restaurants/?${proefUrl}`));
      console.log(`   ?${proefUrl.padEnd(34)} ${String(s.length).padStart(3)} items  ${s.length > 24 ? '✅ MEER DAN 24' : '❌ blijft 24'}`);
    } catch (e) {
      console.log(`   ?${proefUrl.padEnd(34)} fout: ${e.message}`);
    }
  }

  // ── 3. Wordt data-diet ooit gevuld? ──────────────────────────
  console.log('\n\n3) Dieet-labels op de lijst (?_diet=vega)');
  const vega = items(await haal(`${BASE}/restaurants/?_diet=vega`));
  const gevuld = vega.filter((x) => x.dieet);
  console.log(`   ${vega.length} items, ${gevuld.length} met een data-diet waarde`);
  gevuld.slice(0, 6).forEach((x) => console.log(`      ${x.slug.padEnd(26)} "${x.dieet}"`));
  if (!gevuld.length) console.log('      → data-diet blijft leeg; dan komt het dieet van ?_diet= zelf.');

  // ── 4. Adres en foto: compleetheid ───────────────────────────
  console.log('\n\n4) Wat de lijst per item oplevert (steekproef pagina 1 ongefilterd)');
  const basis = items(await haal(`${BASE}/restaurants/`));
  const metAdres = basis.filter((x) => x.adres).length;
  const metFoto = basis.filter((x) => x.foto).length;
  console.log(`   ${basis.length} items: ${metAdres} met adres, ${metFoto} met foto`);
  basis.slice(0, 3).forEach((x) =>
    console.log(`      ${x.slug.padEnd(24)} ${x.adres.slice(0, 60)}`)
  );

  const bestand = path.join(__dirname, 'sterren-dump.json');
  fs.writeFileSync(
    bestand,
    JSON.stringify(
      alles.map((p) => ({
        slug: p.slug,
        titel: schoon(p.title?.rendered || ''),
        link: p.link,
        sterren: telSterren(p.content?.rendered || ''),
      })),
      null,
      2
    )
  );
  console.log(`\n✅ ${bestand} (${alles.length} restaurants met hun sterren)`);
})().catch((e) => {
  console.error('\nFout:', e.message);
  process.exit(1);
});
