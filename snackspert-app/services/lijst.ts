import he from 'he';
import { fetchMetTimeout } from './api';

/**
 * De overzichtspagina /restaurants/ als databron.
 *
 * Waarom: de WordPress REST API levert van een restaurant alleen naam, slug en
 * link. Het veld `content` is leeg en `acf` ook, en de categorie-taxonomie
 * bestaat niet in de API. De overzichtspagina daarentegen geeft per restaurant
 * het volledige adres (inclusief land) en de foto, en laat zich filteren met
 * ?_category= en ?_diet=. Met `_per_page` kunnen alle 761 in één keer mee.
 *
 * Daarmee komt alles wat de kaart, de lijst en de filters nodig hebben uit een
 * kleine twintig verzoeken, in plaats van 761 losse recensiepagina's. Alleen de
 * sterren staan nergens anders dan in de recensie zelf; die vult de app op de
 * achtergrond bij (zie RestaurantContext).
 */

const BASE_URL = 'https://snackspert.nl';
const LIJST_URL = `${BASE_URL}/restaurants/`;

// Eén verzoek mag de hele collectie teruggeven; ruim boven het huidige aantal
// zodat nieuwe recensies er vanzelf in blijven passen.
// 800 is de waarde die op de site is nagemeten: die gaf alle 761 in één
// antwoord. haalVolledigeLijst() controleert alsnog of het compleet is.
const ALLES_PER_PAGINA = 800;

// De overzichtspagina met alles erop is een paar honderd kilobyte, dus hier mag
// het wat langer duren dan bij een gewone API-call.
const LIJST_TIMEOUT = 30000;

/** De categorie die eigenlijk een beoordeling is: die hoort bij het sterrenfilter. */
const VIJF_STERREN_SLUG = '5-sterren';

export interface LijstItem {
  slug: string;
  naam: string;
  adres: string;
  stad: string;
  land: string;
  afbeeldingUrl: string;
  paginaUrl: string;
}

export interface TermOptie {
  slug: string;
  label: string;
}

export interface SiteIndex {
  items: LijstItem[];
  /** Coördinaten per slug, uit de kaartdata op dezelfde pagina. */
  coords: Map<string, { lat: number; lng: number }>;
  categorieen: TermOptie[];
  dieten: TermOptie[];
  /** Per restaurant-slug de labels die erbij horen. */
  categorieenPerSlug: Map<string, string[]>;
  dietenPerSlug: Map<string, string[]>;
  /** Restaurants in de categorie "5 sterren" — daarmee weten we hun score al. */
  vijfSterrenSlugs: Set<string>;
}

/* ───────────────────────── HTML uitlezen ───────────────────────── */

/**
 * Knip het blok met de resultaten uit de pagina.
 *
 * Met indexOf in plaats van een regex: de pagina is met alle restaurants erop
 * honderden kilobytes groot, en daar wil je geen `[\s\S]*?` over laten lopen.
 */
export function resultaatBlok(html: string): string {
  const start = html.indexOf('facetwp-template');
  if (start < 0) return html;
  const vanaf = html.indexOf('>', start);
  if (vanaf < 0) return html;

  // Het blok eindigt waar de pager of het volgende facet begint.
  const einde = ['facetwp-pager', 'facetwp-facet', '<footer']
    .map(m => html.indexOf(m, vanaf))
    .filter(i => i > vanaf)
    .reduce((a, b) => Math.min(a, b), html.length);

  return html.slice(vanaf + 1, einde);
}

/**
 * Splits een adres in stad en land.
 *
 * Een Nederlands adres eindigt op "<postcode> <stad>"; staat daar iets anders,
 * dan is dat laatste deel het land (de site schrijft die voluit, bijv.
 * "Londenstraat 48, 2000 Antwerpen, België").
 */
export function splitsAdres(adres: string): { stad: string; land: string } {
  const delen = adres.split(',').map(d => d.trim()).filter(Boolean);
  if (delen.length === 0) return { stad: '', land: '' };

  const laatste = delen[delen.length - 1];

  // "1021 JC Amsterdam" → Nederland.
  const nederlands = laatste.match(/^\d{4}\s*[A-Z]{2}\s+(.+)$/);
  if (nederlands) return { stad: nederlands[1].trim(), land: 'Nederland' };

  // Een landnaam bevat geen cijfers. Zit er een cijfer in, dan is dit geen land
  // maar een (buitenlandse) postcode-plaats en gokken we op Nederland.
  if (delen.length === 1 || /\d/.test(laatste)) {
    return { stad: schoonStad(laatste), land: 'Nederland' };
  }

  return { stad: schoonStad(delen[delen.length - 2] || ''), land: laatste };
}

/** Haal postcodes weg zodat alleen de plaatsnaam overblijft. */
function schoonStad(deel: string): string {
  return deel
    // "1021 JC Amsterdam", "2000 Antwerpen"
    .replace(/^\d{4,6}\s*(?:[A-Z]{2}\s+)?/, '')
    // "Manchester M3 4EN"
    .replace(/\s+[A-Z]{1,2}\d[A-Z\d]?\s+\d[A-Z]{2}$/i, '')
    // "Köln 50667"
    .replace(/\s+\d{4,6}$/, '')
    .trim();
}

/** Lees de restaurants uit een resultaatblok. */
export function parseItems(html: string): LijstItem[] {
  const blok = resultaatBlok(html);
  const items: LijstItem[] = [];
  const gezien = new Set<string>();

  const anker = /<a\s[^>]*href="(https?:\/\/snackspert\.nl\/restaurant\/([^/"]+)\/?)"([^>]*)>([\s\S]*?)<\/a>/gi;
  let m: RegExpExecArray | null;

  while ((m = anker.exec(blok)) !== null) {
    const [, url, slug, attributen, binnen] = m;
    if (gezien.has(slug)) continue;
    gezien.add(slug);

    const titel = attributen.match(/title="([^"]*)"/)?.[1] ?? '';
    const adresRuw = binnen.match(/class="address"[^>]*>([\s\S]*?)<\/span>/i)?.[1] ?? '';
    const adres = he.decode(adresRuw.replace(/<[^>]*>/g, ' ').replace(/\s+/g, ' ').trim());
    const naamRuw = binnen.match(/class="smallTitle"[^>]*>([\s\S]*?)<\/span>/i)?.[1] ?? titel;

    const { stad, land } = splitsAdres(adres);

    items.push({
      slug,
      naam: he.decode(naamRuw.replace(/<[^>]*>/g, '').trim()),
      adres,
      stad,
      land,
      afbeeldingUrl: binnen.match(/background-image:\s*url\(['"]?([^'")]+)['"]?\)/i)?.[1] ?? '',
      paginaUrl: url.endsWith('/') ? url : `${url}/`,
    });
  }

  return items;
}

/** Alleen de slugs — voor de gefilterde pagina's, waar we de rest al kennen. */
export function parseSlugs(html: string): string[] {
  const blok = resultaatBlok(html);
  const uit = new Set<string>();
  for (const m of blok.matchAll(/href="https?:\/\/snackspert\.nl\/restaurant\/([^/"]+)\//gi)) {
    uit.add(m[1]);
  }
  return Array.from(uit);
}

/** De coördinaten uit de kaartdata op dezelfde pagina. */
export function parseCoords(html: string): Map<string, { lat: number; lng: number }> {
  const uit = new Map<string, { lat: number; lng: number }>();
  const match = html.match(/restaurantLocations\s*=\s*(\[[\s\S]*?\])\s*;/);
  if (!match) return uit;

  let ruw: Array<{ lat?: number; lng?: number; permalink?: string }>;
  try {
    ruw = JSON.parse(match[1]);
  } catch {
    return uit;
  }

  for (const m of ruw) {
    if (typeof m.lat !== 'number' || typeof m.lng !== 'number' || !m.permalink) continue;
    const slug = m.permalink.match(/\/restaurant\/([^/]+)\/?/)?.[1];
    if (slug) uit.set(slug, { lat: m.lat, lng: m.lng });
  }
  return uit;
}

/**
 * De filteropties, zoals FacetWP ze in de pagina zet.
 *
 * Ze staan in FWP_JSON.preload_data.facets als stukjes HTML. Dat hele object
 * parsen zou de volledige resultaatlijst meenemen, dus we pakken alleen de twee
 * velden die we nodig hebben en laten JSON.parse de escapes eruit halen.
 */
export function parseFacetOpties(html: string, naam: string): TermOptie[] {
  const vanaf = html.indexOf('FWP_JSON');
  if (vanaf < 0) return [];

  const re = new RegExp(`"${naam}"\\s*:\\s*"((?:\\\\.|[^"\\\\])*)"`);
  const treffer = html.slice(vanaf).match(re);
  if (!treffer) return [];

  let facetHtml: string;
  try {
    facetHtml = JSON.parse(`"${treffer[1]}"`);
  } catch {
    return [];
  }

  const opties: TermOptie[] = [];
  const gezien = new Set<string>();
  const voegToe = (slug: string, ruwLabel: string) => {
    const schoon = he.decode(ruwLabel.replace(/<[^>]*>/g, ' '))
      .replace(/\s*\(\d+\)\s*$/, '')
      .replace(/\s+/g, ' ')
      .trim();
    if (!slug || gezien.has(slug)) return;
    gezien.add(slug);
    opties.push({ slug, label: schoon || slug });
  };

  for (const m of facetHtml.matchAll(/data-value="([^"]*)"[^>]*>([\s\S]*?)</g)) voegToe(m[1], m[2]);
  for (const m of facetHtml.matchAll(/<option[^>]*value="([^"]+)"[^>]*>([\s\S]*?)<\/option>/g)) voegToe(m[1], m[2]);

  return opties;
}

/**
 * Het aantal resultaten dat de site zelf meldt, uit de pager in FWP_JSON.
 * Hiermee kunnen we controleren of we echt alles binnen hebben.
 */
export function parseTotaalAantal(html: string): number | null {
  const vanaf = html.indexOf('FWP_JSON');
  const bron = vanaf < 0 ? html : html.slice(vanaf);
  const m = bron.match(/"total_rows"\s*:\s*(\d+)/);
  return m ? parseInt(m[1], 10) : null;
}

/* ───────────────────────── Verzoeken ───────────────────────── */

/** Voer taken uit met maximaal `max` tegelijk. */
async function metPool<T>(taken: Array<() => Promise<T>>, max: number): Promise<T[]> {
  const uit: T[] = new Array(taken.length);
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


async function haalPagina(zoekArgumenten: string): Promise<string> {
  const url = zoekArgumenten ? `${LIJST_URL}?${zoekArgumenten}` : LIJST_URL;
  const resp = await fetchMetTimeout(url, LIJST_TIMEOUT);
  if (!resp.ok) throw new Error(`Overzichtspagina gaf ${resp.status}`);
  return resp.text();
}

/**
 * Haal een (eventueel gefilterde) lijst volledig op.
 *
 * `_per_page` laat de site alles in één antwoord geven, maar dat is niet iets
 * waar we blind op mogen vertrouwen: wordt die parameter ooit begrensd of
 * genegeerd, dan zouden we stilletjes maar 24 restaurants overhouden. Daarom
 * vergelijken we met het aantal dat de site zelf meldt en halen we de rest
 * desnoods per pagina op.
 *
 * @returns De HTML van elke pagina, samen compleet.
 */
async function haalVolledigeLijst(filter: string): Promise<string[]> {
  const argumenten = (extra: string) =>
    [filter, `_per_page=${ALLES_PER_PAGINA}`, extra].filter(Boolean).join('&');

  const eerste = await haalPagina(argumenten(''));
  const paginas = [eerste];

  const totaal = parseTotaalAantal(eerste);
  const perPagina = parseSlugs(eerste).length;

  // Niets te vergelijken, of alles zit er al in: klaar.
  if (!totaal || perPagina === 0 || perPagina >= totaal) return paginas;

  const aantalPaginas = Math.ceil(totaal / perPagina);
  const rest = await metPool(
    Array.from({ length: aantalPaginas - 1 }, (_, i) => async () => {
      try {
        return await haalPagina(argumenten(`_paged=${i + 2}`));
      } catch {
        return '';
      }
    }),
    4
  );

  return paginas.concat(rest.filter(Boolean));
}

/**
 * Haal in één keer alles op wat de app nodig heeft behalve de sterren:
 * alle restaurants met adres en foto, hun coördinaten, en per restaurant de
 * categorieën en diëten.
 *
 * @param onProgress  Wordt aangeroepen met het aantal afgeronde verzoeken.
 */
export async function fetchSiteIndex(
  onProgress?: (gereed: number, totaal: number) => void
): Promise<SiteIndex> {
  // Stap 1: de ongefilterde pagina. Hier staan de filteropties in; die hebben we
  // nodig om te weten welke categorieën er zijn. We vragen meteen alles op, dan
  // komen de restaurants, hun adressen en de kaartdata in hetzelfde antwoord.
  const basisPaginas = await haalVolledigeLijst('');
  const basisHtml = basisPaginas[0];

  // De kaartdata staat op elke pagina en gaat over de hele collectie, dus die
  // hoeft maar één keer gelezen te worden; de items juist van alle pagina's.
  // Ontdubbelen: als er toch per pagina geladen is, kan een restaurant op de
  // rand van twee pagina's tweemaal voorbijkomen.
  const perSlug = new Map<string, LijstItem>();
  for (const item of basisPaginas.flatMap(parseItems)) {
    if (!perSlug.has(item.slug)) perSlug.set(item.slug, item);
  }
  const items = Array.from(perSlug.values());
  const coords = parseCoords(basisHtml);

  const alleCategorieen = parseFacetOpties(basisHtml, 'category');
  const dieten = parseFacetOpties(basisHtml, 'diet').map(o => ({
    slug: o.slug,
    // De facet schrijft "vega" met kleine letter; op de kaart en in het menu
    // staat het als eigennaam.
    label: o.label.charAt(0).toUpperCase() + o.label.slice(1),
  }));

  // "5 sterren" is geen keuken maar een beoordeling: die hoort bij het
  // sterrenfilter, niet bij de categorieën.
  const categorieen = alleCategorieen.filter(o => o.slug !== VIJF_STERREN_SLUG);

  // Stap 2: per term opvragen wie erin zit. Eén verzoek per categorie en per
  // dieet, met een pool zodat we de server niet overvragen.
  const termen: Array<{ param: '_category' | '_diet'; optie: TermOptie }> = [
    ...alleCategorieen.map(optie => ({ param: '_category' as const, optie })),
    ...dieten.map(optie => ({ param: '_diet' as const, optie })),
  ];

  let gereed = 0;
  const totaal = termen.length;
  onProgress?.(0, totaal);

  const resultaten = await metPool(
    termen.map(({ param, optie }) => async () => {
      try {
        const paginas = await haalVolledigeLijst(
          `${param}=${encodeURIComponent(optie.slug)}`
        );
        return { param, optie, slugs: paginas.flatMap(parseSlugs) };
      } catch {
        // Eén mislukte categorie mag de rest niet meesleuren; die blijft dan
        // gewoon leeg en vult zich bij de volgende ververs.
        return { param, optie, slugs: [] as string[] };
      } finally {
        onProgress?.(++gereed, totaal);
      }
    }),
    6
  );

  const categorieenPerSlug = new Map<string, string[]>();
  const dietenPerSlug = new Map<string, string[]>();
  const vijfSterrenSlugs = new Set<string>();

  for (const { param, optie, slugs } of resultaten) {
    if (optie.slug === VIJF_STERREN_SLUG) {
      for (const s of slugs) vijfSterrenSlugs.add(s);
      continue;
    }
    const doel = param === '_diet' ? dietenPerSlug : categorieenPerSlug;
    for (const s of slugs) {
      const lijst = doel.get(s);
      if (lijst) {
        if (!lijst.includes(optie.label)) lijst.push(optie.label);
      } else {
        doel.set(s, [optie.label]);
      }
    }
  }

  return {
    items,
    coords,
    categorieen,
    dieten,
    categorieenPerSlug,
    dietenPerSlug,
    vijfSterrenSlugs,
  };
}
