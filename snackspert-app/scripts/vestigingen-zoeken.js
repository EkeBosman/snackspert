#!/usr/bin/env node
/**
 * Zoek per restaurant of er meer vestigingen van dezelfde zaak bestaan.
 *
 * Wat het doet:
 *   1. Haalt al je restaurants op van snackspert.nl (naam, adres, coordinaten).
 *   2. Vraagt Google Places per zaak of er meer vestigingen met die naam zijn.
 *   3. Schrijft de treffers naar vestigingen.csv, met een kolom die jij invult.
 *
 * Er komt NIETS automatisch in de app. Jij keurt eerst goed.
 *
 * ── Vooraf ──────────────────────────────────────────────────────
 *
 * Je app-sleutels werken hier niet: de Places API is een webdienst, en die
 * accepteert geen beperking op bundle-id of package. Maak een aparte sleutel:
 *
 *   1. Google Cloud Console -> APIs & Services -> Library -> "Places API (New)"
 *      -> ENABLE
 *   2. Credentials -> + CREATE CREDENTIALS -> API key
 *   3. Noem hem "Snackspert vestigingen (tijdelijk)"
 *   4. Application restrictions: None
 *   5. API restrictions: alleen Places API (New)
 *   6. Verwijder hem zodra je klaar bent
 *
 * ── Gebruik ─────────────────────────────────────────────────────
 *
 * EERST een proef op twintig zaken, zodat je ziet wat eruit komt:
 *
 *   GOOGLE_PLACES_KEY=AIza... node scripts/vestigingen-zoeken.js --limiet 20
 *
 * Ziet het er goed uit? Dan alles:
 *
 *   GOOGLE_PLACES_KEY=AIza... node scripts/vestigingen-zoeken.js
 *
 * Kosten: ongeveer € 0,03 per zaak, dus zo'n € 25 voor alle 761. Antwoorden
 * worden bewaard in vestigingen-cache.json, dus een tweede run over dezelfde
 * zaken kost niets.
 */

const fs = require('fs');
const path = require('path');

const BASE = 'https://snackspert.nl';
const PER_PAGINA = 200;
const UA =
  'Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1';

const SLEUTEL = process.env.GOOGLE_PLACES_KEY || '';
const CACHE = path.join(__dirname, 'vestigingen-cache.json');
const CSV = path.join(__dirname, 'vestigingen.csv');

// Een treffer binnen deze afstand is de zaak zelf, geen tweede vestiging.
const ZELFDE_PLEK_METER = 200;

/* ───────────────────────── gereedschap ───────────────────────── */

async function haal(url, opties = {}, timeout = 30000) {
  const ctrl = new AbortController();
  const t = setTimeout(() => ctrl.abort(), timeout);
  try {
    const r = await fetch(url, { ...opties, signal: ctrl.signal });
    return { ok: r.ok, status: r.status, tekst: await r.text() };
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
const decode = (s) =>
  String(s).replace(/&[a-z#0-9]+;/gi, (m) => ENTITEITEN[m.toLowerCase()] ?? m)
    .replace(/\s+/g, ' ').trim();

/** Afstand in meters tussen twee punten. */
function afstand(a, b) {
  const R = 6371000;
  const rad = (x) => (x * Math.PI) / 180;
  const dLat = rad(b.lat - a.lat);
  const dLng = rad(b.lng - a.lng);
  const h =
    Math.sin(dLat / 2) ** 2 +
    Math.cos(rad(a.lat)) * Math.cos(rad(b.lat)) * Math.sin(dLng / 2) ** 2;
  return Math.round(2 * R * Math.asin(Math.sqrt(h)));
}

/**
 * Namen vergelijkbaar maken: kleine letters, accenten eraf, leestekens weg,
 * en lidwoorden vooraan weg ("'t Smikkelhoekje" en "Smikkelhoekje" horen bij
 * elkaar).
 */
function normaliseer(naam) {
  return String(naam)
    .toLowerCase()
    .normalize('NFD').replace(/[̀-ͯ]/g, '')
    .replace(/[^a-z0-9 ]+/g, ' ')
    .replace(/\b(de|het|een|t|s|the)\b/g, ' ')
    .replace(/\s+/g, ' ')
    .trim();
}

/* ───────────────────────── je eigen lijst ───────────────────────── */

function resultaatBlok(html) {
  const start = html.indexOf('facetwp-template');
  if (start < 0) return html;
  const vanaf = html.indexOf('>', start);
  const einde = ['facetwp-pager', 'facetwp-facet', '<footer']
    .map((m) => html.indexOf(m, vanaf))
    .filter((i) => i > vanaf)
    .reduce((a, b) => Math.min(a, b), html.length);
  return html.slice(vanaf + 1, einde);
}

function parseItems(html) {
  const blok = resultaatBlok(html);
  const uit = [];
  const re = /<a\s[^>]*href="https?:\/\/snackspert\.nl\/restaurant\/([^/"]+)\/?"([^>]*)>([\s\S]*?)<\/a>/gi;
  let m;
  while ((m = re.exec(blok)) !== null) {
    const [, slug, attributen, binnen] = m;
    const titel = attributen.match(/title="([^"]*)"/)?.[1] ?? '';
    const naam = binnen.match(/class="smallTitle"[^>]*>([\s\S]*?)<\/span>/i)?.[1] ?? titel;
    const adres = binnen.match(/class="address"[^>]*>([\s\S]*?)<\/span>/i)?.[1] ?? '';
    uit.push({
      slug,
      naam: decode(String(naam).replace(/<[^>]*>/g, '')),
      adres: decode(String(adres).replace(/<[^>]*>/g, ' ')),
    });
  }
  return uit;
}

function parseCoords(html) {
  const uit = new Map();
  const m = html.match(/restaurantLocations\s*=\s*(\[[\s\S]*?\])\s*;/);
  if (!m) return uit;
  let ruw;
  try { ruw = JSON.parse(m[1]); } catch { return uit; }
  for (const r of ruw) {
    if (typeof r.lat !== 'number' || typeof r.lng !== 'number' || !r.permalink) continue;
    const slug = r.permalink.match(/\/restaurant\/([^/]+)\/?/)?.[1];
    if (slug) uit.set(slug, { lat: r.lat, lng: r.lng });
  }
  return uit;
}

function totaalAantal(html) {
  const i = html.indexOf('FWP_JSON');
  const m = (i < 0 ? html : html.slice(i)).match(/"total_rows"\s*:\s*(\d+)/);
  return m ? parseInt(m[1], 10) : null;
}

async function haalRestaurants() {
  const url = (p) => `${BASE}/restaurants/?_per_page=${PER_PAGINA}${p > 1 ? `&_paged=${p}` : ''}`;
  const eerste = await haal(url(1));
  if (!eerste.ok) throw new Error(`Overzichtspagina gaf ${eerste.status}`);

  const items = parseItems(eerste.tekst);
  const coords = parseCoords(eerste.tekst);
  const totaal = totaalAantal(eerste.tekst) ?? items.length;
  const paginas = Math.ceil(totaal / Math.max(1, items.length));

  const rest = await metPool(
    Array.from({ length: Math.max(0, paginas - 1) }, (_, i) => async () => {
      const r = await haal(url(i + 2));
      return r.ok ? parseItems(r.tekst) : [];
    }),
    4
  );

  const perSlug = new Map();
  for (const item of [...items, ...rest.flat()]) {
    if (!perSlug.has(item.slug)) {
      perSlug.set(item.slug, { ...item, coord: coords.get(item.slug) ?? null });
    }
  }
  return Array.from(perSlug.values());
}

/* ───────────────────────── Google Places ───────────────────────── */

async function zoekVestigingen(naam) {
  const r = await haal('https://places.googleapis.com/v1/places:searchText', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'X-Goog-Api-Key': SLEUTEL,
      'X-Goog-FieldMask':
        'places.id,places.displayName,places.formattedAddress,places.location,places.businessStatus',
    },
    body: JSON.stringify({
      textQuery: `${naam} Nederland`,
      languageCode: 'nl',
      regionCode: 'NL',
      maxResultCount: 20,
    }),
  });

  if (!r.ok) throw new Error(`Places gaf ${r.status}: ${r.tekst.slice(0, 160)}`);
  const data = JSON.parse(r.tekst);
  return data.places || [];
}

/* ───────────────────────── hoofdprogramma ───────────────────────── */

(async () => {
  if (!SLEUTEL) {
    console.error('Geen sleutel. Gebruik:\n  GOOGLE_PLACES_KEY=AIza... node scripts/vestigingen-zoeken.js --limiet 20\n');
    process.exit(1);
  }

  const limietArg = process.argv.indexOf('--limiet');
  const limiet = limietArg >= 0 ? parseInt(process.argv[limietArg + 1], 10) : Infinity;

  console.log('Je restaurants ophalen ...');
  let zaken = await haalRestaurants();
  console.log(`   ${zaken.length} zaken.`);
  if (Number.isFinite(limiet)) {
    zaken = zaken.slice(0, limiet);
    console.log(`   PROEF: alleen de eerste ${zaken.length}.`);
  }

  const cache = fs.existsSync(CACHE) ? JSON.parse(fs.readFileSync(CACHE, 'utf8')) : {};
  const nieuw = zaken.filter((z) => !(z.slug in cache)).length;
  console.log(`   ${nieuw} nog op te vragen, ${zaken.length - nieuw} al in de cache.`);
  console.log(`   geschatte kosten: € ${(nieuw * 0.032).toFixed(2)}\n`);

  let gedaan = 0;
  let fouten = 0;
  await metPool(
    zaken.map((z) => async () => {
      if (!(z.slug in cache)) {
        try {
          cache[z.slug] = await zoekVestigingen(z.naam);
        } catch (e) {
          cache[z.slug] = [];
          fouten++;
          if (fouten <= 3) console.log(`   fout bij ${z.naam}: ${e.message}`);
        }
      }
      gedaan++;
      if (gedaan % 25 === 0 || gedaan === zaken.length) {
        process.stdout.write(`   ${gedaan}/${zaken.length}\r`);
        fs.writeFileSync(CACHE, JSON.stringify(cache));
      }
    }),
    5
  );
  fs.writeFileSync(CACHE, JSON.stringify(cache));
  console.log(`\n   klaar${fouten ? `, ${fouten} mislukt` : ''}.\n`);

  // ── Treffers beoordelen ──────────────────────────────────────
  const eigenNamen = new Set(zaken.map((z) => normaliseer(z.naam)));
  const eigenCoords = zaken.filter((z) => z.coord).map((z) => z.coord);
  const rijen = [];

  for (const zaak of zaken) {
    const kern = normaliseer(zaak.naam);
    if (kern.length < 4) continue;   // te korte naam geeft alleen ruis

    for (const p of cache[zaak.slug] || []) {
      if (p.businessStatus && p.businessStatus !== 'OPERATIONAL') continue;

      const naam = p.displayName?.text || '';
      const anderKern = normaliseer(naam);
      const gelijk = anderKern === kern;
      const bevat = !gelijk && (anderKern.includes(kern) || kern.includes(anderKern));
      if (!gelijk && !bevat) continue;

      const coord = p.location ? { lat: p.location.latitude, lng: p.location.longitude } : null;
      if (!coord) continue;

      // De zaak zelf overslaan.
      if (zaak.coord && afstand(zaak.coord, coord) < ZELFDE_PLEK_METER) continue;
      // Een vestiging die je zelf al hebt gerecenseerd heeft al een pin.
      if (eigenCoords.some((c) => afstand(c, coord) < ZELFDE_PLEK_METER)) continue;

      rijen.push({
        slug: zaak.slug,
        origineel: zaak.naam,
        origineel_adres: zaak.adres,
        vestiging: naam,
        vestiging_adres: p.formattedAddress || '',
        lat: coord.lat,
        lng: coord.lng,
        afstand_km: zaak.coord ? (afstand(zaak.coord, coord) / 1000).toFixed(1) : '',
        zekerheid: gelijk ? 'hoog' : 'twijfel',
        place_id: p.id,
        goedkeuren: '',
      });
    }
  }

  rijen.sort((a, b) =>
    a.zekerheid.localeCompare(b.zekerheid) || a.origineel.localeCompare(b.origineel, 'nl')
  );

  const kolommen = Object.keys(rijen[0] || { slug: '' });
  const veld = (v) => (/[",;\n]/.test(String(v)) ? `"${String(v).replace(/"/g, '""')}"` : v);
  fs.writeFileSync(
    CSV,
    '﻿' + [kolommen.join(';'), ...rijen.map((r) => kolommen.map((k) => veld(r[k])).join(';'))].join('\n'),
    'utf8'
  );

  const hoog = rijen.filter((r) => r.zekerheid === 'hoog').length;
  console.log(`✅ ${CSV}`);
  console.log(`   ${rijen.length} mogelijke vestigingen: ${hoog} met gelijke naam, ${rijen.length - hoog} twijfelgevallen.`);
  console.log(`   ${new Set(rijen.map((r) => r.slug)).size} van je zaken hebben er minstens één.`);
  console.log('\n   Open het bestand en zet "ja" in de laatste kolom bij alles wat klopt.');
  console.log('   Stuur het daarna terug, dan zet ik ze in de app.');
})().catch((e) => {
  console.error('\nFout:', e.message);
  process.exit(1);
});
