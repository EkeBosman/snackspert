#!/usr/bin/env node
/**
 * De categorieen staan niet in de REST API (geen taxonomie, acf leeg). Maar je
 * filterbalk werkt op de site wel — die praat met FacetWP's eigen endpoint.
 * Dit script doet precies wat je browser doet als je een filter aanvinkt.
 *
 * Verandert niets aan de site; alleen lezen. Schrijft facetwp-dump.json.
 *
 * Gebruik: node scripts/facetwp-api.js
 */

const fs = require('fs');
const path = require('path');

const BASE = 'https://snackspert.nl';
const PAGINA = `${BASE}/restaurants/`;
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

async function post(url, body) {
  const ctrl = new AbortController();
  const t = setTimeout(() => ctrl.abort(), 30000);
  try {
    const r = await fetch(url, {
      method: 'POST',
      signal: ctrl.signal,
      headers: {
        'User-Agent': UA,
        'Content-Type': 'application/json',
        Accept: 'application/json',
        Referer: PAGINA,
      },
      body: JSON.stringify(body),
    });
    const tekst = await r.text();
    let data = null;
    try { data = JSON.parse(tekst); } catch {}
    return { ok: r.ok, status: r.status, data, ruw: tekst.slice(0, 400) };
  } catch (e) {
    return { ok: false, status: 0, data: null, fout: e.message };
  } finally {
    clearTimeout(t);
  }
}

const schoon = (s) => s.replace(/<[^>]*>/g, '').replace(/&amp;/g, '&').replace(/\s+/g, ' ').trim();

/** Haal een JS-objectliteraal uit de pagina: var NAAM = {...}; */
function jsObject(html, naam) {
  const i = html.indexOf(naam);
  if (i < 0) return null;
  const start = html.indexOf('{', i);
  if (start < 0) return null;
  let diep = 0;
  for (let j = start; j < html.length; j++) {
    const c = html[j];
    if (c === '{') diep++;
    else if (c === '}') {
      diep--;
      if (diep === 0) {
        try { return JSON.parse(html.slice(start, j + 1)); } catch { return null; }
      }
    }
  }
  return null;
}

/** Opties + aantallen uit de gerenderde HTML van een facet. */
function faceOpties(html) {
  if (typeof html !== 'string') return [];
  const uit = [];
  const gezien = new Set();
  const voeg = (slug, label, aantal) => {
    if (!slug || gezien.has(slug)) return;
    gezien.add(slug);
    uit.push({ slug, label: schoon(label || slug), aantal: aantal ? Number(aantal) : null });
  };
  for (const m of html.matchAll(
    /data-value="([^"]*)"[^>]*>([\s\S]*?)(?:<span[^>]*class="facetwp-counter"[^>]*>\s*\(?(\d+)\)?\s*<\/span>)?[\s\S]*?<\/(?:li|div|a|span)>/g
  )) {
    voeg(m[1], m[2], m[3]);
  }
  for (const m of html.matchAll(/<option[^>]*value="([^"]+)"[^>]*>([\s\S]*?)<\/option>/g)) {
    const label = schoon(m[2]);
    const a = label.match(/\((\d+)\)\s*$/);
    voeg(m[1], label.replace(/\s*\(\d+\)\s*$/, ''), a?.[1]);
  }
  return uit;
}

/** Slugs van de restaurants in een stuk lijst-HTML. */
function itemSlugs(html) {
  if (typeof html !== 'string') return [];
  const uit = new Set();
  for (const m of html.matchAll(/https?:\/\/snackspert\.nl\/([a-z0-9][a-z0-9-]{2,})\/?["'#]/gi)) {
    const slug = m[1].toLowerCase();
    if (!['restaurants', 'category', 'tag', 'author', 'wp-content', 'wp-json', 'feed', 'page'].includes(slug)) {
      uit.add(slug);
    }
  }
  return [...uit];
}

/** Markers uit de restaurantLocations-array. */
function markers(html) {
  const m = String(html).match(/restaurantLocations\s*=\s*(\[[\s\S]*?\])\s*;/);
  if (!m) return null;
  try { return JSON.parse(m[1]); } catch { return null; }
}

(async () => {
  console.log('Pagina ophalen en FacetWP-instellingen zoeken ...\n');
  const html = await haal(PAGINA);

  const basisMarkers = markers(html);
  console.log(`   markers zonder filter: ${basisMarkers?.length ?? '?'}`);

  const fwpJson = jsObject(html, 'FWP_JSON');
  const fwpHttp = jsObject(html, 'FWP_HTTP');
  console.log(`   FWP_JSON gevonden: ${fwpJson ? 'ja' : 'nee'}`);
  console.log(`   FWP_HTTP gevonden: ${fwpHttp ? 'ja' : 'nee'}`);

  // Welke facets staan er, en hoe heten ze precies?
  const facetNamen = [];
  for (const m of html.matchAll(/data-name="([^"]+)"[^>]*data-type="([^"]+)"/g)) {
    if (!facetNamen.some((f) => f.naam === m[1])) facetNamen.push({ naam: m[1], type: m[2] });
  }
  for (const m of html.matchAll(/data-type="([^"]+)"[^>]*data-name="([^"]+)"/g)) {
    if (!facetNamen.some((f) => f.naam === m[2])) facetNamen.push({ naam: m[2], type: m[1] });
  }
  console.log(`   facets op de pagina: ${facetNamen.map((f) => `${f.naam}(${f.type})`).join(', ') || 'geen'}`);

  // Staan de opties al voorgeladen in de pagina?
  const voorgeladen = fwpJson?.preload_data?.facets;
  if (voorgeladen) {
    console.log('\n   ✅ FWP_JSON.preload_data.facets aanwezig — opties zitten al in de pagina:');
    for (const [naam, inhoud] of Object.entries(voorgeladen)) {
      const o = faceOpties(inhoud);
      console.log(`      ${naam.padEnd(14)} ${o.length} opties`);
      o.slice(0, 25).forEach((x) =>
        console.log(`         ${x.slug.padEnd(22)} ${x.label}${x.aantal != null ? `  (${x.aantal})` : ''}`)
      );
    }
  }

  // ─────────────────────────────────────────────────────────────
  console.log('\nFacetWP-endpoint aanspreken (zoals de browser doet) ...');

  const alleFacets = facetNamen.length
    ? facetNamen.map((f) => f.naam)
    : ['type_food', 'diet', 'location', 'pagination'];

  const lading = (selectie = {}, paged = 1) => ({
    data: {
      facets: Object.fromEntries(alleFacets.map((n) => [n, selectie[n] || []])),
      frozen_facets: {},
      http_params: { get: {}, uri: 'restaurants', url_vars: {} },
      template: fwpHttp?.template || 'wp',
      extras: { sort: 'default' },
      soft_refresh: 0,
      is_bfcache: 0,
      first_load: 0,
      paged,
    },
  });

  const endpoints = [
    `${BASE}/wp-json/facetwp/v1/refresh`,
    `${BASE}/wp-admin/admin-ajax.php?action=facetwp_refresh`,
  ];

  let werkend = null;
  let leeg = null;
  for (const ep of endpoints) {
    const r = await post(ep, lading());
    const bruikbaar = r.ok && r.data && (r.data.facets || r.data.template);
    console.log(`   ${ep}`);
    console.log(`      HTTP ${r.status}${r.fout ? ' - ' + r.fout : ''}  →  ${bruikbaar ? '✅ bruikbaar' : '❌'}`);
    if (!bruikbaar && r.ruw) console.log(`      antwoord: ${r.ruw.replace(/\s+/g, ' ').slice(0, 200)}`);
    if (bruikbaar) { werkend = ep; leeg = r.data; break; }
  }

  if (!werkend) {
    console.log('\n⛔ Geen van beide endpoints werkt. Stuur dit terug, dan kies ik een andere aanpak.');
    return;
  }

  console.log(`\n   velden in het antwoord: ${Object.keys(leeg).join(', ')}`);
  if (leeg.pager) console.log(`   pager: ${JSON.stringify(leeg.pager).slice(0, 200)}`);

  // Welke opties kent elke facet?
  const opties = {};
  console.log('\n   Opties per facet:');
  for (const [naam, inhoud] of Object.entries(leeg.facets || {})) {
    const o = faceOpties(inhoud);
    opties[naam] = o;
    console.log(`      ${naam.padEnd(14)} ${o.length} opties`);
    o.slice(0, 25).forEach((x) =>
      console.log(`         ${x.slug.padEnd(22)} ${x.label}${x.aantal != null ? `  (${x.aantal})` : ''}`)
    );
    if (o.length > 25) console.log(`         ... en nog ${o.length - 25}`);
  }

  // Hoe zien de resultaten eruit zonder filter?
  const basisSlugs = itemSlugs(leeg.template);
  console.log(`\n   resultaten zonder filter: ${basisSlugs.length} slugs uit de template-HTML`);
  console.log(`   voorbeeld: ${basisSlugs.slice(0, 5).join(', ')}`);
  if (!basisSlugs.length && typeof leeg.template === 'string') {
    console.log(`   template begint met: ${leeg.template.replace(/\s+/g, ' ').slice(0, 300)}`);
  }

  // ─────────────────────────────────────────────────────────────
  // Nu echt filteren: per categorie de restaurants ophalen.
  const catFacet = Object.keys(opties).find((n) => /food|categor|soort|keuken/i.test(n));
  const dietFacet = Object.keys(opties).find((n) => /diet|dieet|vega/i.test(n));
  console.log(`\n   categorie-facet: ${catFacet || 'niet gevonden'}   dieet-facet: ${dietFacet || 'niet gevonden'}`);

  if (!catFacet || !opties[catFacet]?.length) {
    console.log('\n⛔ Geen categorie-opties. Stuur de uitvoer terug.');
    return;
  }

  const perSlug = new Map();
  const raak = async (facet, optie, veld) => {
    const r = await post(werkend, lading({ [facet]: [optie.slug] }));
    if (!r.ok || !r.data) return console.log(`      ${optie.slug.padEnd(22)} ❌ HTTP ${r.status}`);
    const slugs = itemSlugs(r.data.template);
    const totaal = r.data.pager?.total_rows ?? r.data.settings?.pager?.total_rows ?? '?';
    console.log(`      ${optie.slug.padEnd(22)} ${String(totaal).padStart(4)} totaal, ${slugs.length} op pagina 1`);
    for (const s of slugs) {
      const rij = perSlug.get(s) || { slug: s, categorieen: [], dieten: [] };
      rij[veld].push(optie.slug);
      perSlug.set(s, rij);
    }
    return { totaal, slugs };
  };

  console.log('\n   Per categorie filteren:');
  for (const o of opties[catFacet]) await raak(catFacet, o, 'categorieen');

  if (dietFacet && opties[dietFacet]?.length) {
    console.log('\n   Per dieet filteren:');
    for (const o of opties[dietFacet]) await raak(dietFacet, o, 'dieten');
  }

  const bestand = path.join(__dirname, 'facetwp-dump.json');
  fs.writeFileSync(
    bestand,
    JSON.stringify(
      {
        endpoint: werkend,
        facets: facetNamen,
        categorieFacet: catFacet,
        dieetFacet: dietFacet,
        opties,
        restaurants: [...perSlug.values()],
      },
      null,
      2
    )
  );
  console.log(`\n✅ ${bestand}`);
  console.log(`   ${perSlug.size} restaurants gekoppeld aan een categorie of dieet.`);
  console.log('   (Staat er maar ~10 per categorie? Dan filtert het wel, maar met paginering —');
  console.log('    dat is prima, dan haalt de app de pagina\'s erbij.)');
})().catch((e) => {
  console.error('\nFout:', e.message);
  process.exit(1);
});
