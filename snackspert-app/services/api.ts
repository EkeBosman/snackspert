import he from 'he';
import { Restaurant, RestaurantSummary, WPRestaurant } from '../types';

const BASE_URL = 'https://snackspert.nl';
const API_URL = `${BASE_URL}/wp-json/wp/v2`;
const GOOGLE_MAPS_API_KEY = 'AIzaSyASmO1Ml_6yLt3JPInfd_5CJhA5eKMI9bg';
const FETCH_TIMEOUT = 15000;

/**
 * Fetch met timeout - voorkomt eindeloos wachten.
 */
async function fetchMetTimeout(url: string, timeout = FETCH_TIMEOUT): Promise<Response> {
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
 * Geeft een callback per pagina zodat we voortgang kunnen tonen.
 */
export async function fetchAlleRestaurants(
  onProgress?: (loaded: number, total: number) => void
): Promise<RestaurantSummary[]> {
  const restaurants: RestaurantSummary[] = [];
  let pagina = 1;
  let totaal = 0;

  while (true) {
    const url = `${API_URL}/restaurant?per_page=100&page=${pagina}&_embed=wp:featuredmedia`;
    const resp = await fetchMetTimeout(url);

    if (!resp.ok) break;

    const data = await resp.json();
    if (!data.length) break;

    totaal = parseInt(resp.headers.get('X-WP-Total') || '0', 10);

    for (const item of data) {
      // Afbeelding ophalen uit _embedded data
      let afbeeldingUrl = '';
      try {
        const media = item._embedded?.['wp:featuredmedia']?.[0];
        afbeeldingUrl = media?.source_url || media?.media_details?.sizes?.medium?.source_url || '';
      } catch {}

      restaurants.push({
        id: item.id,
        naam: he.decode(item.title.rendered),
        slug: item.slug,
        paginaUrl: item.link,
        afbeeldingUrl,
        categorieen: [],
      });
    }

    onProgress?.(restaurants.length, totaal);

    const totaalPaginas = parseInt(resp.headers.get('X-WP-TotalPages') || '0', 10);
    if (pagina >= totaalPaginas) break;

    pagina++;
    // Korte pauze om de server niet te overbelasten
    await new Promise(r => setTimeout(r, 200));
  }

  return restaurants;
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
 * Als `bestaandeCoords` wordt meegegeven (bijv. uit de cache), slaan we de
 * dure Google Geocoding-call over. Coördinaten van een adres veranderen immers
 * nooit, dus die hoeven we maar één keer ooit op te halen.
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

  // Coördinaten: hergebruik bekende coords (uit cache) om geocoding te sparen,
  // anders via Google Geocoding API op basis van het adres.
  if (bestaandeCoords && bestaandeCoords.lat && bestaandeCoords.lng) {
    result.latitude = bestaandeCoords.lat;
    result.longitude = bestaandeCoords.lng;
  } else if (result.adres) {
    try {
      const coords = await geocodeAdres(result.adres);
      if (coords) {
        result.latitude = coords.lat;
        result.longitude = coords.lng;
      }
    } catch {}
  }

  // Categorieën uit de HTML (vaak als class of data-attribuut)
  const catMatches = html.match(/class="catLabel"[^>]*>([\s\S]*?)<\//g);
  if (catMatches) {
    result.categorieen = catMatches.map(m => {
      const text = m.replace(/<[^>]+>/g, '').replace(/class="catLabel"[^>]*>/, '').trim();
      return he.decode(text);
    }).filter(Boolean);
  }

  return result;
}

/**
 * Geocodeer een adres naar coördinaten via Google Geocoding API.
 */
async function geocodeAdres(adres: string): Promise<{ lat: number; lng: number } | null> {
  try {
    const encoded = encodeURIComponent(adres);
    const url = `https://maps.googleapis.com/maps/api/geocode/json?address=${encoded}&key=${GOOGLE_MAPS_API_KEY}`;
    const resp = await fetchMetTimeout(url, 5000);
    const data = await resp.json();
    if (data.status === 'OK' && data.results?.[0]) {
      const loc = data.results[0].geometry.location;
      return { lat: loc.lat, lng: loc.lng };
    }
  } catch {}
  return null;
}

/**
 * Haal categorieën op via de WordPress REST API taxonomy endpoint.
 */
export async function fetchCategorieen(): Promise<string[]> {
  try {
    // Probeer de custom taxonomy
    const resp = await fetchMetTimeout(`${API_URL}/restaurant-categorie?per_page=100`);
    if (resp.ok) {
      const terms = await resp.json();
      return terms.map((t: { name: string }) => he.decode(t.name));
    }
  } catch (e) {
    // Taxonomy bestaat misschien niet, gebruik standaard lijst
  }

  // Fallback naar de bekende categorieën
  return [
    'Aziatisch', 'Bakker', 'Broodjes', 'Frietpatat', 'Grieks',
    'Hamburger', 'Hotdogs', 'Italiaans', 'Kroket', 'Mexicaans',
    'Midden-Oosters', 'Pizza', 'Shoarma/döner', 'Snackbar',
    'Spaans', 'Spareribs', 'Wraps',
  ];
}
