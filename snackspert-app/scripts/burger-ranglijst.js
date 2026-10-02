#!/usr/bin/env node
/**
 * Ranglijst van alle burgers die je in NEDERLAND hebt getest.
 *
 * Vier kolommen: naam, aantal sterren (daarop gesorteerd), stad, provincie.
 *
 * Hoe het werkt:
 *   1. /restaurants/?_category=hamburger geeft alle burgerzaken in één keer,
 *      met naam en volledig adres. Het aantal klopt met de teller op de site.
 *   2. Het adres bepaalt het land: een Nederlands adres eindigt op
 *      "<postcode> <plaats>", buitenlandse adressen hebben het land erachter.
 *   3. De sterren staan alleen in de recensie zelf, dus die pagina's worden
 *      gelezen — maar alleen van de Nederlandse zaken.
 *   4. De provincie komt van PDOK (de locatiedienst van de overheid, gratis en
 *      zonder sleutel), opgezocht op postcode.
 *
 * Verandert niets. Schrijft burgers-nederland.csv.
 *
 * Gebruik: node scripts/burger-ranglijst.js
 */

const fs = require('fs');
const path = require('path');

const BASE = 'https://snackspert.nl';
const CATEGORIE = 'hamburger';
const PER_PAGINA = 800;
const UA =
  'Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1';

/* ───────────────────────── gereedschap ───────────────────────── */

async function haal(url, timeout = 30000) {
  const ctrl = new AbortController();
  const t = setTimeout(() => ctrl.abort(), timeout);
  try {
    const r = await fetch(url, { signal: ctrl.signal, headers: { 'User-Agent': UA } });
    if (!r.ok) throw new Error(`HTTP ${r.status}`);
    return await r.text();
  } finally {
    clearTimeout(t);
  }
}

async function metPool(taken, max) {
  const uit = new Array(taken.length);
  let volgende = 0;
  const worker = async () => {
    while (true) {
      const i = volgende++;
      if (i >= taken.length) return;
      uit[i] = await taken[i]();
    }
  };
  await Promise.all(Array.from({ length: Math.min(max, taken.length) }, worker));
  return uit;
}

const ENTITEITEN = {
  '&amp;': '&', '&lt;': '<', '&gt;': '>', '&quot;': '"', '&#039;': "'",
  '&#8217;': '’', '&#8216;': '‘', '&#8211;': '–', '&#8212;': '—',
  '&euml;': 'ë', '&eacute;': 'é', '&egrave;': 'è', '&ouml;': 'ö', '&uuml;': 'ü',
  '&auml;': 'ä', '&iuml;': 'ï', '&ccedil;': 'ç', '&oacute;': 'ó', '&nbsp;': ' ',
};

function decode(s) {
  return String(s)
    .replace(/&[a-z#0-9]+;/gi, m => ENTITEITEN[m.toLowerCase()] ?? m)
    .replace(/\s+/g, ' ')
    .trim();
}

/* ───────────────────────── de lijst ───────────────────────── */

function resultaatBlok(html) {
  const start = html.indexOf('facetwp-template');
  if (start < 0) return html;
  const vanaf = html.indexOf('>', start);
  if (vanaf < 0) return html;
  const einde = ['facetwp-pager', 'facetwp-facet', '<footer']
    .map(m => html.indexOf(m, vanaf))
    .filter(i => i > vanaf)
    .reduce((a, b) => Math.min(a, b), html.length);
  return html.slice(vanaf + 1, einde);
}

function parseItems(html) {
  const blok = resultaatBlok(html);
  const uit = [];
  const gezien = new Set();
  const anker = /<a\s[^>]*href="(https?:\/\/snackspert\.nl\/restaurant\/([^/"]+)\/?)"([^>]*)>([\s\S]*?)<\/a>/gi;
  let m;
  while ((m = anker.exec(blok)) !== null) {
    const [, url, slug, attributen, binnen] = m;
    if (gezien.has(slug)) continue;
    gezien.add(slug);
    const titel = attributen.match(/title="([^"]*)"/)?.[1] ?? '';
    const naamRuw = binnen.match(/class="smallTitle"[^>]*>([\s\S]*?)<\/span>/i)?.[1] ?? titel;
    const adresRuw = binnen.match(/class="address"[^>]*>([\s\S]*?)<\/span>/i)?.[1] ?? '';
    uit.push({
      slug,
      naam: decode(naamRuw.replace(/<[^>]*>/g, '')),
      adres: decode(adresRuw.replace(/<[^>]*>/g, ' ')),
      url: url.endsWith('/') ? url : `${url}/`,
    });
  }
  return uit;
}

function totaalAantal(html) {
  const i = html.indexOf('FWP_JSON');
  const m = (i < 0 ? html : html.slice(i)).match(/"total_rows"\s*:\s*(\d+)/);
  return m ? parseInt(m[1], 10) : null;
}

/** Nederlands adres? Dan eindigt het op "<postcode> <plaats>". */
function ontleedAdres(adres) {
  const delen = adres.split(',').map(d => d.trim()).filter(Boolean);
  const laatste = delen[delen.length - 1] || '';

  const nl = laatste.match(/^(\d{4})\s*([A-Z]{2})\s+(.+)$/);
  if (nl) {
    return { nederland: true, postcode: `${nl[1]} ${nl[2]}`, stad: nl[3].trim() };
  }

  // Expliciet "..., Nederland" achter het adres.
  if (/^nederland$/i.test(laatste)) {
    const vorige = delen[delen.length - 2] || '';
    const pc = vorige.match(/^(\d{4})\s*([A-Z]{2})?\s*(.*)$/);
    return {
      nederland: true,
      postcode: pc?.[1] ? `${pc[1]} ${pc[2] ?? ''}`.trim() : '',
      stad: (pc?.[3] || vorige).trim(),
    };
  }

  return { nederland: false, postcode: '', stad: laatste };
}

/* ───────────────────────── de sterren ───────────────────────── */

/**
 * Zelfde telling als de app: losse clusters van ster-emoji's zoeken en daarvan
 * het gemiddelde nemen (sommige recensies beoordelen meerdere gerechten).
 */
function sterrenUitPagina(html) {
  const tekst = decode(html.replace(/<[^>]+>/g, ' '));
  const cijfers = [];
  const cluster = /([⭐★]️?\s*){1,5}(½|1\/2)?/g;
  let m;
  while ((m = cluster.exec(tekst)) !== null) {
    const volle = (m[0].match(/[⭐★]/g) || []).length;
    const halve = /½|1\/2/.test(m[0]) ? 0.5 : 0;
    const totaal = volle + halve;
    if (totaal > 0 && totaal <= 5) cijfers.push(totaal);
  }
  if (cijfers.length === 0) return null;
  const gem = cijfers.reduce((a, b) => a + b, 0) / cijfers.length;
  return Math.round(gem * 2) / 2;
}

/* ───────────────────────── de provincie ───────────────────────── */

const PDOK = 'https://api.pdok.nl/bzk/locatieserver/search/v3_1/free';
const provincieCache = new Map();

async function zoekProvincie(postcode, stad) {
  const sleutel = postcode.slice(0, 4) || stad.toLowerCase();
  if (provincieCache.has(sleutel)) return provincieCache.get(sleutel);

  const pogingen = [];
  if (postcode) pogingen.push(`q=${encodeURIComponent(postcode)}&fq=type:postcode`);
  if (stad) pogingen.push(`q=${encodeURIComponent(stad)}&fq=type:woonplaats`);

  let provincie = '';
  for (const vraag of pogingen) {
    try {
      const ruw = await haal(`${PDOK}?${vraag}&fl=provincienaam&rows=1`, 12000);
      provincie = JSON.parse(ruw)?.response?.docs?.[0]?.provincienaam || '';
      if (provincie) break;
    } catch {
      // Volgende poging.
    }
  }

  provincieCache.set(sleutel, provincie);
  return provincie;
}

/* ───────────────────────── hoofdprogramma ───────────────────────── */

(async () => {
  console.log(`Burgerzaken ophalen (categorie "${CATEGORIE}") ...`);

  const eerste = await haal(`${BASE}/restaurants/?_category=${CATEGORIE}&_per_page=${PER_PAGINA}`);
  const gemeld = totaalAantal(eerste);
  let items = parseItems(eerste);

  // Terugval als _per_page ooit begrensd wordt.
  if (gemeld && items.length > 0 && items.length < gemeld) {
    const paginas = Math.ceil(gemeld / items.length);
    console.log(`   ${items.length} van ${gemeld} in één keer; nog ${paginas - 1} pagina's ophalen ...`);
    const rest = await metPool(
      Array.from({ length: paginas - 1 }, (_, i) => () =>
        haal(`${BASE}/restaurants/?_category=${CATEGORIE}&_per_page=${PER_PAGINA}&_paged=${i + 2}`)
          .then(parseItems)
          .catch(() => [])
      ),
      4
    );
    const perSlug = new Map(items.map(i => [i.slug, i]));
    for (const i of rest.flat()) if (!perSlug.has(i.slug)) perSlug.set(i.slug, i);
    items = Array.from(perSlug.values());
  }

  console.log(`   ${items.length} burgerzaken${gemeld ? ` (site meldt ${gemeld})` : ''}.`);

  const ontleed = items.map(i => ({ ...i, ...ontleedAdres(i.adres) }));
  const nederlandse = ontleed.filter(i => i.nederland);
  const buitenland = ontleed.filter(i => !i.nederland);

  console.log(`   ${nederlandse.length} in Nederland, ${buitenland.length} in het buitenland.`);
  if (buitenland.length) {
    const landen = new Map();
    for (const b of buitenland) landen.set(b.stad, (landen.get(b.stad) || 0) + 1);
    console.log(`   buitenland: ${[...landen].map(([l, n]) => `${l} (${n})`).join(', ')}`);
  }

  console.log(`\nSterren ophalen uit ${nederlandse.length} recensies ...`);
  let gereed = 0;
  await metPool(
    nederlandse.map(r => async () => {
      try {
        r.sterren = sterrenUitPagina(await haal(r.url));
      } catch {
        r.sterren = null;
      }
      gereed++;
      if (gereed % 20 === 0 || gereed === nederlandse.length) {
        process.stdout.write(`   ${gereed}/${nederlandse.length}\r`);
      }
    }),
    8
  );
  console.log();

  console.log('\nProvincies opzoeken bij PDOK ...');
  for (const r of nederlandse) {
    r.provincie = await zoekProvincie(r.postcode, r.stad);
  }
  console.log(`   ${provincieCache.size} unieke postcodegebieden opgezocht.`);

  // Sorteren: sterren omlaag, daarna op naam zodat de lijst stabiel is.
  nederlandse.sort((a, b) => (b.sterren ?? -1) - (a.sterren ?? -1) || a.naam.localeCompare(b.naam, 'nl'));

  /* ── tabel ── */
  const kolommen = [
    { kop: 'Naam zaak', waarde: r => r.naam },
    { kop: 'Sterren', waarde: r => (r.sterren == null ? '—' : String(r.sterren).replace('.', ',')) },
    { kop: 'Stad', waarde: r => r.stad },
    { kop: 'Provincie', waarde: r => r.provincie || '—' },
  ];
  const breedtes = kolommen.map((k, i) =>
    Math.max(k.kop.length, ...nederlandse.map(r => kolommen[i].waarde(r).length))
  );

  const regel = cellen => cellen.map((c, i) => c.padEnd(breedtes[i])).join('  ');
  console.log(`\n${'═'.repeat(breedtes.reduce((a, b) => a + b + 2, 0))}`);
  console.log(`BURGERS IN NEDERLAND — ${nederlandse.length} zaken\n`);
  console.log(regel(kolommen.map(k => k.kop)));
  console.log(breedtes.map(b => '─'.repeat(b)).join('  '));
  for (const r of nederlandse) console.log(regel(kolommen.map(k => k.waarde(r))));

  /* ── CSV ── */
  const csvVeld = v => (/[",;\n]/.test(v) ? `"${v.replace(/"/g, '""')}"` : v);
  const csv = [
    kolommen.map(k => k.kop).join(';'),
    ...nederlandse.map(r => kolommen.map(k => csvVeld(k.waarde(r))).join(';')),
  ].join('\n');
  const bestand = path.join(__dirname, 'burgers-nederland.csv');
  fs.writeFileSync(bestand, '﻿' + csv, 'utf8');
  console.log(`\n✅ ${bestand}`);

  const zonder = nederlandse.filter(r => r.sterren == null).length;
  if (zonder) console.log(`   ${zonder} zaken zonder sterren in de recensie (met — aangegeven).`);
  const geenProvincie = nederlandse.filter(r => !r.provincie).length;
  if (geenProvincie) console.log(`   ${geenProvincie} zaken zonder provincie gevonden.`);
})().catch(e => {
  console.error('\nFout:', e.message);
  process.exit(1);
});
