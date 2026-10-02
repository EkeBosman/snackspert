#!/usr/bin/env node
/**
 * Kan de app de categorieen (taxonomie "type_food") en de dieten (vega/vegan)
 * rechtstreeks uit de WordPress API halen? Dit test alle ingangen die nog open
 * staan, en als er een werkt haalt hij meteen alles op.
 *
 * Verandert niets aan de site. Schrijft alleen taxonomie-dump.json.
 *
 * Gebruik: node scripts/taxonomie-check.js
 */

const fs = require('fs');
const path = require('path');

const API = 'https://snackspert.nl/wp-json/wp/v2';
const UA =
  'Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1';

async function json(url) {
  const ctrl = new AbortController();
  const t = setTimeout(() => ctrl.abort(), 25000);
  try {
    const r = await fetch(url, { signal: ctrl.signal, headers: { 'User-Agent': UA } });
    const body = await r.text();
    let data = null;
    try { data = JSON.parse(body); } catch {}
    return {
      ok: r.ok,
      status: r.status,
      data,
      totaal: r.headers.get('X-WP-Total'),
      paginas: r.headers.get('X-WP-TotalPages'),
    };
  } catch (e) {
    return { ok: false, status: 0, data: null, fout: e.message };
  } finally {
    clearTimeout(t);
  }
}

/** Zoek termen in class_list: "type_food-hamburger" → {type_food: [hamburger]} */
function termenUitClassList(lijst) {
  const uit = {};
  for (const k of lijst || []) {
    const m = String(k).match(/^(type_food|diet|restaurant-categorie|restaurant_cat)-(.+)$/);
    if (m) (uit[m[1]] ||= []).push(m[2]);
  }
  return uit;
}

(async () => {
  // ─────────────────────────────────────────────────────────────
  console.log('1) Welke taxonomieen kent de API, en onder welke naam?');
  const tax = await json(`${API}/taxonomies`);
  const restBases = [];
  if (tax.ok && tax.data && !Array.isArray(tax.data)) {
    for (const [sleutel, t] of Object.entries(tax.data)) {
      const types = (t.types || []).join(',');
      console.log(
        `   ${sleutel.padEnd(20)} rest_base=${String(t.rest_base).padEnd(20)} voor: ${types}`
      );
      if ((t.types || []).includes('restaurant')) restBases.push(t.rest_base || sleutel);
    }
    if (restBases.length) console.log(`   → van toepassing op restaurants: ${restBases.join(', ')}`);
  } else {
    console.log(`   niet beschikbaar (HTTP ${tax.status}${tax.fout ? ' - ' + tax.fout : ''})`);
  }

  // ─────────────────────────────────────────────────────────────
  console.log('\n2) Staan de termen zelf in de API?');
  const kandidaten = [...new Set([...restBases, 'type_food', 'diet', 'restaurant-categorie'])];
  const termen = {};
  for (const naam of kandidaten) {
    const r = await json(`${API}/${naam}?per_page=100`);
    if (r.ok && Array.isArray(r.data) && r.data.length) {
      termen[naam] = r.data.map((t) => ({ id: t.id, slug: t.slug, naam: t.name, aantal: t.count }));
      console.log(`   /${naam}  →  ✅ ${r.data.length} termen`);
      termen[naam].forEach((t) =>
        console.log(`        id=${String(t.id).padEnd(6)} ${String(t.slug).padEnd(22)} ${t.naam} (${t.aantal}x)`)
      );
    } else {
      console.log(`   /${naam}  →  ❌ HTTP ${r.status}${r.fout ? ' - ' + r.fout : ''}`);
    }
  }

  // ─────────────────────────────────────────────────────────────
  console.log('\n3) Komen de termen mee in het restaurant-object zelf?');
  const r5 = await json(`${API}/restaurant?per_page=5`);
  let classListWerkt = false;
  if (r5.ok && Array.isArray(r5.data) && r5.data.length) {
    console.log(`   alle velden: ${Object.keys(r5.data[0]).join(', ')}`);
    for (const p of r5.data) {
      const uitClass = termenUitClassList(p.class_list);
      if (Object.keys(uitClass).length) classListWerkt = true;
      const taxVelden = Object.entries(p)
        .filter(([k, v]) => Array.isArray(v) && /food|diet|categor|tax/i.test(k))
        .map(([k, v]) => `${k}=[${v}]`);
      console.log(
        `   ${String(p.title?.rendered).slice(0, 26).padEnd(28)} ` +
        (Object.keys(uitClass).length ? `✅ ${JSON.stringify(uitClass)}` : `class_list=${JSON.stringify(p.class_list || []).slice(0, 90)}`) +
        (taxVelden.length ? `  ${taxVelden.join(' ')}` : '')
      );
    }
  } else {
    console.log(`   restaurant-lijst niet op te halen (HTTP ${r5.status})`);
  }

  // ─────────────────────────────────────────────────────────────
  console.log('\n4) Filteren op taxonomie via de API?');
  let filterWerkt = null;
  for (const naam of Object.keys(termen)) {
    const t = termen[naam]?.[0];
    if (!t) continue;
    for (const [sleutel, waarde] of [[naam, t.id], [naam, t.slug]]) {
      const r = await json(`${API}/restaurant?per_page=1&${sleutel}=${waarde}`);
      const gefilterd = r.ok && r.totaal && Number(r.totaal) > 0 && Number(r.totaal) < 700;
      console.log(
        `   ?${sleutel}=${String(waarde).padEnd(22)} →  HTTP ${r.status}` +
        (r.ok ? `  X-WP-Total=${r.totaal}  ${gefilterd ? '✅ GEFILTERD' : '❌ niet gefilterd'}` : '')
      );
      if (gefilterd && !filterWerkt) filterWerkt = { taxonomie: naam, sleutel };
    }
  }
  console.log('\n   (755 = niet gefilterd; een lager getal = het werkt)');

  // ─────────────────────────────────────────────────────────────
  // 5) Als er een route werkt: haal meteen ALLES op.
  console.log('\n5) Alles ophalen via de werkende route');

  if (!classListWerkt && !filterWerkt) {
    console.log('   ⛔ Geen werkende route gevonden. Niets gedumpt.');
    console.log('   Stuur de uitvoering hierboven terug, dan kies ik de volgende aanpak.');
    return;
  }

  /** alle restaurants in zo weinig verzoeken mogelijk */
  async function alleRestaurants() {
    const eerste = await json(`${API}/restaurant?per_page=100&page=1`);
    if (!eerste.ok || !Array.isArray(eerste.data)) return [];
    const paginas = Number(eerste.paginas || 1);
    const rest = await Promise.all(
      Array.from({ length: Math.max(0, paginas - 1) }, (_, i) =>
        json(`${API}/restaurant?per_page=100&page=${i + 2}`)
      )
    );
    return [eerste, ...rest].flatMap((r) => (Array.isArray(r.data) ? r.data : []));
  }

  const alles = await alleRestaurants();
  console.log(`   ${alles.length} restaurants opgehaald in ${Math.ceil(alles.length / 100)} verzoeken.`);

  const dump = [];
  const tellers = {};

  if (classListWerkt) {
    console.log('   bron: class_list op het restaurant-object (geen extra verzoeken nodig)');
    for (const p of alles) {
      const t = termenUitClassList(p.class_list);
      const soorten = t.type_food || t['restaurant-categorie'] || t.restaurant_cat || [];
      const dieten = t.diet || [];
      dump.push({
        slug: p.slug,
        titel: String(p.title?.rendered || '').replace(/&amp;/g, '&'),
        link: p.link,
        categorieen: soorten,
        dieten,
      });
      for (const s of soorten) tellers[s] = (tellers[s] || 0) + 1;
    }
  } else {
    console.log(`   bron: filteren per term via ?${filterWerkt.sleutel}=`);
    const perSlug = new Map(alles.map((p) => [p.slug, { slug: p.slug, titel: String(p.title?.rendered || '').replace(/&amp;/g, '&'), link: p.link, categorieen: [], dieten: [] }]));
    for (const naam of Object.keys(termen)) {
      for (const t of termen[naam]) {
        const r = await json(`${API}/restaurant?per_page=100&${naam}=${t.id}&_fields=slug`);
        const slugs = Array.isArray(r.data) ? r.data.map((x) => x.slug) : [];
        const veld = /diet/i.test(naam) ? 'dieten' : 'categorieen';
        for (const s of slugs) perSlug.get(s)?.[veld].push(t.slug);
        if (veld === 'categorieen') tellers[t.slug] = slugs.length;
        console.log(`      ${naam}=${t.slug.padEnd(20)} ${slugs.length} restaurants`);
      }
    }
    dump.push(...perSlug.values());
  }

  const bestand = path.join(__dirname, 'taxonomie-dump.json');
  fs.writeFileSync(bestand, JSON.stringify(dump, null, 2));
  const zonder = dump.filter((d) => d.categorieen.length === 0).length;
  const metDieet = dump.filter((d) => d.dieten.length > 0).length;

  console.log(`\n   ✅ ${bestand}`);
  console.log(`   ${dump.length} restaurants, ${zonder} zonder categorie, ${metDieet} met een dieet-label.`);
  console.log('\n   Verdeling per categorie:');
  Object.entries(tellers)
    .sort((a, b) => b[1] - a[1])
    .forEach(([s, n]) => console.log(`      ${s.padEnd(22)} ${n}`));
})().catch((e) => {
  console.error('\nFout:', e.message);
  process.exit(1);
});
