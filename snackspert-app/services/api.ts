import he from 'he';
import { Restaurant, RestaurantSummary, WPRestaurant } from '../types';

const BASE_URL = 'https://snackspert.nl';
const API_URL = `${BASE_URL}/wp-json/wp/v2`;

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
    const url = `${API_URL}/restaurant?per_page=100&page=${pagina}`;
    const resp = await fetch(url);

    if (!resp.ok) break;

    const data: WPRestaurant[] = await resp.json();
    if (!data.length) break;

    totaal = parseInt(resp.headers.get('X-WP-Total') || '0', 10);

    for (const item of data) {
      restaurants.push({
        id: item.id,
        naam: he.decode(item.title.rendered),
        slug: item.slug,
        paginaUrl: item.link,
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
  const volleMatch = tekst.match(/\u2b50\ufe0f?/g);
  const volle = volleMatch ? volleMatch.length : 0;
  const halve = tekst.includes('\u00bd') || tekst.includes('1/2') ? 0.5 : 0;
  const totaal = volle + halve;
  const sterrenTekst = '\u2b50'.repeat(volle) + (halve ? '\u00bd' : '');
  return { sterren: totaal, sterrenTekst };
}

/**
 * Scrape de details van een individuele restaurantpagina.
 * Haalt naam, adres, afbeelding, recensietekst, sterren, en coördinaten op.
 */
export async function fetchRestaurantDetail(url: string): Promise<Partial<Restaurant>> {
  const resp = await fetch(url);
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

  // Recensietekst - zoek de .text div
  const tekstMatch = html.match(/class="text"[^>]*>([\s\S]*?)<\/div>/);
  if (tekstMatch) {
    // Verwijder HTML tags, houd tekst over
    const rawText = tekstMatch[1]
      .replace(/<br\s*\/?>/gi, '\n')
      .replace(/<\/p>/gi, '\n\n')
      .replace(/<[^>]+>/g, '')
      .replace(/\n{3,}/g, '\n\n')
      .trim();
    result.tekst = he.decode(rawText);

    // Sterren uit de tekst halen (eerste <p> met sterren)
    const pMatches = tekstMatch[1].match(/<p[^>]*>([\s\S]*?)<\/p>/g);
    if (pMatches) {
      for (const p of pMatches) {
        const pText = p.replace(/<[^>]+>/g, '');
        const { sterren, sterrenTekst } = telSterren(pText);
        if (sterren > 0 && sterren <= 5) {
          result.sterren = sterren;
          result.sterrenTekst = sterrenTekst;
          break;
        }
      }
    }
  }

  // Coördinaten uit restaurantLocations JavaScript variable
  const locMatch = html.match(
    /restaurantLocations\s*=\s*\[([\s\S]*?)\]/
  );
  if (locMatch) {
    const latMatch = locMatch[1].match(/lat:\s*([\d.]+)/);
    const lngMatch = locMatch[1].match(/lng:\s*([\d.]+)/);
    if (latMatch && lngMatch) {
      result.latitude = parseFloat(latMatch[1]);
      result.longitude = parseFloat(lngMatch[1]);
    }
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
 * Haal alle restaurantlocaties op uit de overzichtspagina's.
 * De snackspert.nl site bevat een JS-array met alle coördinaten.
 */
export async function fetchAlleLocaties(): Promise<Map<string, { lat: number; lng: number }>> {
  const locaties = new Map<string, { lat: number; lng: number }>();

  // Probeer de hoofdpagina met alle locaties
  try {
    const resp = await fetch(`${BASE_URL}/restaurant/`);
    const html = await resp.text();

    // restaurantLocations array parsen
    const match = html.match(/restaurantLocations\s*=\s*\[([\s\S]*?)\];/);
    if (match) {
      // Elke entry heeft: { lat: ..., lng: ..., title: "...", url: "..." }
      const entries = match[1].match(/\{[^}]+\}/g);
      if (entries) {
        for (const entry of entries) {
          const lat = entry.match(/lat:\s*([\d.-]+)/);
          const lng = entry.match(/lng:\s*([\d.-]+)/);
          const urlMatch = entry.match(/url:\s*['"]([^'"]+)['"]/);
          const titleMatch = entry.match(/title:\s*['"]([^'"]+)['"]/);

          if (lat && lng && (urlMatch || titleMatch)) {
            const key = urlMatch ? urlMatch[1] : titleMatch![1];
            locaties.set(key, {
              lat: parseFloat(lat[1]),
              lng: parseFloat(lng[1]),
            });
          }
        }
      }
    }
  } catch (e) {
    console.warn('Kon locaties niet ophalen van overzichtspagina:', e);
  }

  return locaties;
}

/**
 * Haal categorieën op via de WordPress REST API taxonomy endpoint.
 */
export async function fetchCategorieen(): Promise<string[]> {
  try {
    // Probeer de custom taxonomy
    const resp = await fetch(`${API_URL}/restaurant-categorie?per_page=100`);
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
