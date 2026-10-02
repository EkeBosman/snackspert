import he from 'he';
import { Restaurant, RestaurantSummary, WPRestaurant } from '../types';

const BASE_URL = 'https://snackspert.nl';
const API_URL = `${BASE_URL}/wp-json/wp/v2`;
const FETCH_TIMEOUT = 15000;

/**
 * Fetch met timeout - voorkomt eindeloos wachten.
 */
export async function fetchMetTimeout(url: string, timeout = FETCH_TIMEOUT): Promise<Response> {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), timeout);
  try {
    const resp = await fetch(url, {
      signal: controller.signal,
      headers: {
        'User-Agent': 'Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1',
      },
    });
    return resp;
  } finally {
    clearTimeout(timer);
  }
}

/**
 * Haal alle restaurants op via de WordPress REST API.
 * Pagina 1 bepaalt het totaal; de overige pagina's worden parallel geladen.
 *
 * Gooit een error bij een mislukte pagina in plaats van stilletjes een
 * (gedeeltelijk) lege lijst terug te geven — de aanroeper behoudt dan de
 * bestaande (gecachte) data in plaats van die te overschrijven.
 */
export async function fetchAlleRestaurants(
  onProgress?: (loaded: number, total: number) => void
): Promise<RestaurantSummary[]> {
  // `_embed` haalt de uitgelichte afbeelding mee, als terugval voor de enkele
  // restaurants waar de overzichtspagina geen foto bij heeft staan.
  //
  // Taxonomie-termen zitten hier NIET in: de categorieën van deze site bestaan
  // niet als taxonomie in de REST API. Die komen uit services/lijst.ts.
  const paginaUrl = (p: number) =>
    `${API_URL}/restaurant?per_page=100&page=${p}&_embed`;

  const parseItems = (data: WPRestaurant[]): RestaurantSummary[] =>
    data.map(item => {
      const embedded = (item as any)._embedded || {};

      // Afbeelding ophalen uit _embedded data
      let afbeeldingUrl = '';
      try {
        const media = embedded['wp:featuredmedia']?.[0];
        afbeeldingUrl = media?.source_url || media?.media_details?.sizes?.medium?.source_url || '';
      } catch {}

      return {
        id: item.id,
        naam: he.decode(item.title.rendered),
        slug: item.slug,
        paginaUrl: item.link,
        afbeeldingUrl,
        categorieen: [],
      };
    });

  const eerste = await fetchMetTimeout(paginaUrl(1));
  if (!eerste.ok) {
    throw new Error(`Kon restaurants niet ophalen (server gaf ${eerste.status})`);
  }

  const totaal = parseInt(eerste.headers.get('X-WP-Total') || '0', 10);
  const totaalPaginas = parseInt(eerste.headers.get('X-WP-TotalPages') || '1', 10);
  const restaurants = parseItems(await eerste.json());
  onProgress?.(restaurants.length, totaal);

  if (totaalPaginas > 1) {
    // Overige pagina's parallel: dit is de eigen site en het gaat om ~6 extra
    // requests, dus dit kan prima tegelijk.
    const rest = await Promise.all(
      Array.from({ length: totaalPaginas - 1 }, (_, i) =>
        fetchMetTimeout(paginaUrl(i + 2)).then(resp => {
          if (!resp.ok) {
            throw new Error(`Kon restaurants niet ophalen (server gaf ${resp.status})`);
          }
          return resp.json() as Promise<WPRestaurant[]>;
        })
      )
    );
    for (const pageData of rest) {
      restaurants.push(...parseItems(pageData));
    }
    onProgress?.(restaurants.length, totaal);
  }

  return restaurants;
}

/**
 * Coördinaten van één restaurant, gekoppeld via de slug.
 */
export interface RestaurantLocatie {
  slug: string;
  lat: number;
  lng: number;
}

/**
 * Haal in één request de coördinaten van ALLE restaurants op.
 *
 * De pagina /restaurants/ bevat een ingebedde JS-variabele `restaurantLocations`
 * met per restaurant title/lat/lng/permalink (dit voedt de kaart op de website).
 * Hiermee vermijden we zowel het scrapen van 700 losse pagina's als 700
 * Google Geocoding-calls om de kaart te vullen.
 */
export async function fetchRestaurantLocaties(): Promise<RestaurantLocatie[]> {
  const resp = await fetchMetTimeout(`${BASE_URL}/restaurants/`);
  const html = await resp.text();

  // Pak de array tussen `restaurantLocations=[ ... ]` tot aan het script-einde.
  const match = html.match(/restaurantLocations\s*=\s*(\[[\s\S]*?\])\s*;?\s*<\/script>/);
  if (!match) return [];

  let ruw: Array<{ lat?: number; lng?: number; permalink?: string }>;
  try {
    ruw = JSON.parse(match[1]);
  } catch {
    return [];
  }

  const locaties: RestaurantLocatie[] = [];
  for (const m of ruw) {
    if (typeof m.lat !== 'number' || typeof m.lng !== 'number' || !m.permalink) continue;
    // Slug uit de permalink halen: .../restaurant/<slug>/
    const slugMatch = m.permalink.match(/\/restaurant\/([^/]+)\/?/);
    if (!slugMatch) continue;
    locaties.push({ slug: slugMatch[1], lat: m.lat, lng: m.lng });
  }
  return locaties;
}

/**
 * Parse het sterren-aantal uit een tekst met ster-emoji's.
 */
function telSterren(tekst: string): { sterren: number; sterrenTekst: string } {
  // Match diverse ster-emoji's: \u2b50 (U+2B50), \u2605 (U+2605), \ud83c\udf1f (U+1F31F)
  const volleMatch = tekst.match(/[\u2b50\u2605]\ufe0f?/g);
  const volle = volleMatch ? volleMatch.length : 0;
  const halve = tekst.includes('\u00bd') || tekst.includes('1/2') ? 0.5 : 0;
  const totaal = volle + halve;
  const sterrenTekst = '\u2b50'.repeat(volle) + (halve ? '\u00bd' : '');
  return { sterren: totaal, sterrenTekst };
}

/**
 * Scrape de details van een individuele restaurantpagina.
 * Haalt naam, adres, afbeelding, recensietekst, sterren, en coördinaten op.
 *
 * Naam, adres en foto komen inmiddels al uit de overzichtspagina (één verzoek
 * voor alle restaurants, zie services/lijst.ts). Wat hier nog onmisbaar is, zijn
 * de sterren en de recensietekst: die staan nergens anders dan in de pagina
 * zelf — niet in de REST API, niet in de Yoast-gegevens en niet in de feed.
 *
 * `bestaandeCoords` wordt onveranderd doorgegeven, zodat de aanroeper de
 * coördinaten niet kwijtraakt die hij al had.
 */
export async function fetchRestaurantDetail(
  url: string,
  bestaandeCoords?: { lat: number; lng: number } | null
): Promise<Partial<Restaurant>> {
  const resp = await fetchMetTimeout(url);
  const html = await resp.text();

  // Simpele HTML-parsing zonder DOM (React Native heeft geen DOMParser)
  const result: Partial<Restaurant> = {};

  // Naam
  const naamMatch = html.match(/class="bigTitle"[^>]*>([\s\S]*?)<\//);
  if (naamMatch) result.naam = he.decode(naamMatch[1].trim());

  // Adres
  const adresMatch = html.match(/class="innerAddress"[^>]*>([\s\S]*?)<\//);
  if (adresMatch) {
    result.adres = he.decode(adresMatch[1].trim());
    // Stad extraheren: meestal het laatste deel van het adres na de postcode
    // Bijv. "Straatnaam 1, 1234 AB Amsterdam" → "Amsterdam"
    const stadMatch = result.adres.match(/\d{4}\s*[A-Z]{2}\s+(.+?)$/);
    if (stadMatch) {
      result.stad = stadMatch[1].trim();
    } else {
      // Fallback: laatste woord na komma
      const delen = result.adres.split(',');
      if (delen.length > 1) {
        result.stad = delen[delen.length - 1].trim();
      }
    }
  }

  // Afbeelding
  const imgMatch = html.match(/class="innerImage"[^>]*style="[^"]*url\('([^']+)'\)/);
  if (imgMatch) result.afbeeldingUrl = imgMatch[1];

  // Recensietekst - zoek de .text div (greedy match om geneste divs mee te pakken)
  const tekstMatch = html.match(/class="text"[^>]*>([\s\S]*?)<\/div>\s*<\/div>/);
  if (tekstMatch) {
    const rawText = tekstMatch[1]
      .replace(/<br\s*\/?>/gi, '\n')
      .replace(/<\/p>/gi, '\n\n')
      .replace(/<[^>]+>/g, '')
      .replace(/\n{3,}/g, '\n\n')
      .trim();
    result.tekst = he.decode(rawText);
  }

  // Sterren zoeken: strip tags (met spatie), zoek star-clusters
  const textOnly = he.decode(html.replace(/<[^>]+>/g, ' '));
  const ratings: number[] = [];
  const clusterPattern = /([⭐★]️?\s*){1,5}(½|1\/2)?/g;
  let clusterMatch;
  while ((clusterMatch = clusterPattern.exec(textOnly)) !== null) {
    const { sterren } = telSterren(clusterMatch[0]);
    if (sterren > 0 && sterren <= 5) {
      ratings.push(sterren);
    }
  }

  if (ratings.length > 0) {
    const avg = ratings.reduce((a, b) => a + b, 0) / ratings.length;
    result.sterren = Math.round(avg * 2) / 2;
    const volle = Math.floor(result.sterren);
    const halve = result.sterren % 1 !== 0;
    result.sterrenTekst = '⭐'.repeat(volle) + (halve ? '½' : '');
  }

  // Coördinaten komen in bulk uit de kaartdata op /restaurants/ (zie
  // services/lijst.ts), dus hier geven we alleen door wat we al hadden.
  //
  // Er stond hier een terugval die het adres bij Google liet geocoderen. Die is
  // weg, en wel om twee redenen. De coördinaten van vrijwel alle restaurants
  // komen nu al in één verzoek mee, dus er viel niets te winnen. En de
  // Geocoding API is een webdienst: een sleutel daarvoor kan níet worden
  // beperkt tot een app, alleen tot IP-adressen. Zo'n sleutel in een publieke
  // app is dus per definitie onbeveiligd — en iedereen die hem eruit haalt, kan
  // op jouw rekening geocoderen.
  //
  // Gevolg: een restaurant zonder coördinaten op de site krijgt geen pin. Het
  // staat wel in de lijst, en op de kaart van de site zelf ontbreekt het net zo
  // goed. Dat hoort dus op de site opgelost te worden, niet in de app.
  if (bestaandeCoords && bestaandeCoords.lat && bestaandeCoords.lng) {
    result.latitude = bestaandeCoords.lat;
    result.longitude = bestaandeCoords.lng;
  }

  return result;
}

// De oude fetchCategorieen() stond hier. Die vroeg de taxonomie
// "restaurant-categorie" op, en die bestaat niet: de API geeft 404. De
// categorieën van deze site komen uit de filters op de overzichtspagina —
// zie fetchSiteIndex() in services/lijst.ts.
