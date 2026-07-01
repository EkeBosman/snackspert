import { File, Paths } from 'expo-file-system';
import { Restaurant } from '../types';

/**
 * Persistente cache voor de volledig geladen restaurantlijst.
 *
 * Doel: de kaart hoeft na de allereerste keer niet opnieuw ~700 pagina's te
 * scrapen en te geocoden. Bij een herstart tonen we direct de cache en
 * verversen we alleen de goedkope summary-lijst om nieuwe/verwijderde
 * restaurants te detecteren.
 */

// Versienummer in de bestandsnaam: bump dit als het Restaurant-formaat wijzigt,
// zodat oude caches automatisch genegeerd worden.
const CACHE_FILE_NAME = 'restaurants-cache.v1.json';

interface CachePayload {
  timestamp: number;
  restaurants: Restaurant[];
}

function getCacheFile(): File {
  return new File(Paths.document, CACHE_FILE_NAME);
}

/**
 * Lees de gecachte restaurants. Geeft null terug als er geen (geldige) cache is.
 */
export async function loadCache(): Promise<CachePayload | null> {
  try {
    const file = getCacheFile();
    if (!file.exists) return null;

    const raw = await file.text();
    const parsed = JSON.parse(raw) as CachePayload;

    if (!parsed || !Array.isArray(parsed.restaurants) || parsed.restaurants.length === 0) {
      return null;
    }
    return parsed;
  } catch {
    // Corrupte of onleesbare cache: negeren alsof er geen cache is.
    return null;
  }
}

/**
 * Sla de volledige restaurantlijst op naar schijf.
 */
export async function saveCache(restaurants: Restaurant[]): Promise<void> {
  try {
    const file = getCacheFile();
    const payload: CachePayload = {
      timestamp: Date.now(),
      restaurants,
    };
    // Maak het bestand expliciet aan als het nog niet bestaat, zodat we niet
    // afhankelijk zijn van impliciet aanmaak-gedrag van write().
    if (!file.exists) {
      file.create();
    }
    file.write(JSON.stringify(payload));
  } catch {
    // Schrijffouten mogen de app nooit laten crashen; cache is best-effort.
  }
}

/**
 * Verwijder de cache (handig voor debuggen of een "harde ververs").
 */
export async function clearCache(): Promise<void> {
  try {
    const file = getCacheFile();
    if (file.exists) file.delete();
  } catch {
    // Negeren.
  }
}
