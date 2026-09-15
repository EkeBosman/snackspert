#!/usr/bin/env node
/**
 * Ranglijst van alle in NEDERLAND geteste burgers van Snackspert.
 *
 * Wat het doet:
 *  1. Haalt alle restaurants op via de WordPress REST API van snackspert.nl
 *  2. Filtert op de categorie "Hamburger"
 *  3. Scrapet per zaak de recensiepagina voor sterren + adres
 *  4. Zoekt de provincie op via PDOK (officiele NL overheids-locatiedienst)
 *  5. Houdt alleen Nederlandse zaken over (herkenbaar aan de postcode)
 *  6. Sorteert op sterren (hoog -> laag), daarna alfabetisch
 *
 * Gebruik:  node scripts/burger-ranglijst.js
 * Resultaat: tabel in de terminal + burgers-nederland.csv
 */

const BASE = 'https://snackspert.nl';
const UA =
  'Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1';

// Welke categorie telt als "burger"? (hoofdletterongevoelig, deel van de naam volstaat)
const BURGER_TERMEN = ['hamburger', 'burger'];

const CONCURRENTIE = 8; // gelijktijdige paginaverzoeken naar je eigen site

// ---------- kleine helpers ----------

const NAMED = {
  amp: '&', lt: '<', gt: '>', quot: '"', apos: "'", nbsp: ' ',
  eacute: 'é', egrave: 'è', euml: 'ë', iuml: 'ï', ouml: 'ö', uuml: 'ü',
  agrave: 'à', auml: 'ä', ccedil: 'ç', oslash: 'ø', euro: '€', hellip: '…',
  rsquo: '’', lsquo: '‘', ldquo: '“', rdquo: '”', ndash: '–', mdash: '—',
};

function decodeEntities(s) {
  if (!s) return '';
  return s
    .replace(/&#x([0-9a-fA-F]+);/g, (_, h) => String.fromCodePoint(parseInt(h, 16)))
    .replace(/&#(\d+);/g, (_, d) => String.fromCodePoint(parseInt(d, 10)))
    .replace(/&([a-zA-Z]+);/g, (m, n) => (n in NAMED ? NAMED[n] : m));
}

async function haal(url, opts = {}) {
  const ctrl = new AbortController();
  const t = setTimeout(() => ctrl.abort(), opts.timeout || 20000);
  try {
    return await fetch(url, { signal: ctrl.signal, headers: { 'User-Agent': UA } });
  } finally {
    clearTimeout(t);
  }
}

/** Zelfde sterren-logica als in de app, zodat de cijfers overeenkomen. */
function sterrenUitHtml(html) {
  const tekst = decodeEntities(html.replace(/<[^>]+>/g, ' '));
  const clusters = tekst.match(/(?:[⭐★]️?\s*){1,5}(?:½|1\/2)?/g) || [];
  const scores = [];
  for (const c of clusters) {
    const volle = (c.match(/[⭐★]️?/g) || []).length;
    const half = /½|1\/2/.test(c) ? 0.5 : 0;
    const s = volle + half;
    if (s > 0 && s <= 5) scores.push(s);
  }
  if (!scores.length) return null;
  const gem = scores.reduce((a, b) => a + b, 0) / scores.length;
  return Math.round(gem * 2) / 2;
}

/** Draai taken met een maximum aantal tegelijk. */
async function parallel(items, limiet, fn, onVoortgang) {
  const uit = new Array(items.length);
  let i = 0, klaar = 0;
  await Promise.all(
    Array.from({ length: Math.min(limiet, items.length) }, async () => {
      while (true) {
        const idx = i++;
        if (idx >= items.length) return;
        try { uit[idx] = await fn(items[idx]); } catch { uit[idx] = null; }
        klaar++;
        if (onVoortgang && klaar % 10 === 0) onVoortgang(klaar, items.length);
      }
    })
  );
  return uit;
}

// ---------- stap 1: restaurants ophalen ----------

async function alleRestaurants() {
  const url = (p) => `${BASE}/wp-json/wp/v2/restaurant?per_page=100&page=${p}&_embed`;
  const eerste = await haal(url(1));
  if (!eerste.ok) throw new Error(`WP API gaf ${eerste.status}`);
  const paginas = parseInt(eerste.headers.get('X-WP-TotalPages') || '1', 10);

  const alles = [...(await eerste.json())];
  for (let p = 2; p <= paginas; p++) {
    const r = await haal(url(p));
    if (!r.ok) throw new Error(`WP API pagina ${p} gaf ${r.status}`);
    alles.push(...(await r.json()));
  }

  return alles.map((item) => {
    const termen = [];
    try {
      for (const groep of item._embedded?.['wp:term'] || []) {
        for (const t of groep) if (t?.name) termen.push(decodeEntities(t.name));
      }
    } catch {}
    return {
      naam: decodeEntities(item.title?.rendered || ''),
      url: item.link,
      categorieen: termen,
    };
  });
}

// ---------- stap 2: detailpagina ----------

async function detail(zaak) {
  const r = await haal(zaak.url);
  if (!r.ok) return { ...zaak, sterren: null, adres: '' };
  const html = await r.text();
  const m = html.match(/class="innerAddress"[^>]*>([\s\S]*?)<\//);
  return {
    ...zaak,
    adres: m ? decodeEntities(m[1].replace(/<[^>]+>/g, ' ')).replace(/\s+/g, ' ').trim() : '',
    sterren: sterrenUitHtml(html),
  };
}

// ---------- stap 3: provincie via PDOK ----------

const provCache = new Map();

async function provincie(postcode, stad) {
  const sleutel = postcode || stad;
  if (provCache.has(sleutel)) return provCache.get(sleutel);
  let res = { provincie: '', woonplaats: stad };
  try {
    const q = encodeURIComponent(postcode || stad);
    const r = await haal(
      `https://api.pdok.nl/bzk/locatieserver/search/v3_1/free?q=${q}&rows=1&fl=provincienaam,woonplaatsnaam`,
      { timeout: 15000 }
    );
    if (r.ok) {
      const d = (await r.json())?.response?.docs?.[0];
      if (d) res = { provincie: d.provincienaam || '', woonplaats: d.woonplaatsnaam || stad };
    }
  } catch {}
  provCache.set(sleutel, res);
  await new Promise((r) => setTimeout(r, 120)); // netjes tegen een publieke API
  return res;
}

// ---------- hoofdprogramma ----------

(async () => {
  console.log('Restaurants ophalen van snackspert.nl ...');
  const alle = await alleRestaurants();
  console.log(`   ${alle.length} restaurants gevonden.\n`);

  // Diagnose: welke categorieen bestaan er eigenlijk?
  const telling = new Map();
  for (const r of alle) for (const c of r.categorieen) telling.set(c, (telling.get(c) || 0) + 1);
  if (telling.size) {
    console.log('Categorieen in je data:');
    [...telling.entries()].sort((a, b) => b[1] - a[1])
      .forEach(([c, n]) => console.log(`   ${String(n).padStart(4)}  ${c}`));
    console.log();
  } else {
    console.log('LET OP: geen categorieen gevonden via de API.\n');
  }

  const burgers = alle.filter((r) =>
    r.categorieen.some((c) => BURGER_TERMEN.some((t) => c.toLowerCase().includes(t)))
  );
  console.log(`Burgerzaken (alle landen): ${burgers.length}`);
  if (!burgers.length) {
    console.log('Geen zaken met een burger-categorie gevonden. Pas BURGER_TERMEN bovenin aan.');
    return;
  }

  console.log('Recensiepagina\'s ophalen (sterren + adres) ...');
  const met = (await parallel(burgers, CONCURRENTIE, detail, (k, t) =>
    process.stdout.write(`\r   ${k}/${t}`)
  )).filter(Boolean);
  process.stdout.write('\r');

  // Nederlandse zaken = adres met Nederlandse postcode (1234 AB)
  const nl = [];
  for (const z of met) {
    const pc = (z.adres || '').match(/(\d{4})\s*([A-Z]{2})\b/);
    if (!pc) continue;
    const postcode = `${pc[1]} ${pc[2]}`;
    const na = z.adres.slice(z.adres.indexOf(pc[0]) + pc[0].length).trim();
    nl.push({ ...z, postcode, stad: na.replace(/^[,\s]+/, '') });
  }
  console.log(`Daarvan in Nederland:      ${nl.length}`);
  console.log(`Buiten Nederland / geen NL-adres: ${met.length - nl.length}\n`);

  console.log('Provincies opzoeken via PDOK ...');
  for (let i = 0; i < nl.length; i++) {
    const p = await provincie(nl[i].postcode, nl[i].stad);
    nl[i].provincie = p.provincie;
    if (p.woonplaats) nl[i].stad = p.woonplaats;
    process.stdout.write(`\r   ${i + 1}/${nl.length}`);
  }
  process.stdout.write('\r');

  nl.sort((a, b) => (b.sterren ?? -1) - (a.sterren ?? -1) || a.naam.localeCompare(b.naam, 'nl'));

  // Tabel
  const kol = (s, n) => String(s ?? '').padEnd(n).slice(0, n);
  const lijn = '─'.repeat(86);
  console.log(`\nRANGLIJST — BURGERS IN NEDERLAND (${nl.length} zaken)\n${lijn}`);
  console.log(`${kol('#', 4)}${kol('Naam zaak', 38)}${kol('Sterren', 9)}${kol('Stad', 20)}Provincie`);
  console.log(lijn);
  nl.forEach((z, i) => {
    const s = z.sterren == null ? '—' : String(z.sterren).replace('.', ',');
    console.log(`${kol(i + 1, 4)}${kol(z.naam, 38)}${kol(s, 9)}${kol(z.stad, 20)}${z.provincie}`);
  });
  console.log(lijn);

  // CSV (puntkomma = opent netjes in Nederlandse Excel)
  const esc = (v) => `"${String(v ?? '').replace(/"/g, '""')}"`;
  const csv = [
    ['Positie', 'Naam zaak', 'Sterren', 'Stad', 'Provincie'].join(';'),
    ...nl.map((z, i) =>
      [i + 1, z.naam, z.sterren == null ? '' : String(z.sterren).replace('.', ','), z.stad, z.provincie]
        .map(esc).join(';')
    ),
  ].join('\n');
  require('fs').writeFileSync('burgers-nederland.csv', '﻿' + csv);
  console.log('\nOpgeslagen als: burgers-nederland.csv (opent in Excel/Sheets)');
})().catch((e) => {
  console.error('\nFout:', e.message);
  process.exit(1);
});
