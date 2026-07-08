import { File, Paths } from 'expo-file-system';

/**
 * Persistente opslag van id-lijsten (favorieten en "geweest"-markeringen).
 */

function getFile(naam: string): File {
  return new File(Paths.document, naam);
}

async function loadIds(naam: string): Promise<number[]> {
  try {
    const file = getFile(naam);
    if (!file.exists) return [];
    const raw = await file.text();
    const parsed = JSON.parse(raw);
    if (!Array.isArray(parsed)) return [];
    return parsed.filter((x): x is number => typeof x === 'number');
  } catch {
    return [];
  }
}

async function saveIds(naam: string, ids: number[]): Promise<void> {
  try {
    const file = getFile(naam);
    if (!file.exists) {
      file.create();
    }
    file.write(JSON.stringify(ids));
  } catch {
    // Best-effort; nooit laten crashen.
  }
}

const FAVORITES_FILE = 'favorites.v1.json';
const VISITED_FILE = 'visited.v1.json';

export const loadFavorites = () => loadIds(FAVORITES_FILE);
export const saveFavorites = (ids: number[]) => saveIds(FAVORITES_FILE, ids);
export const loadVisited = () => loadIds(VISITED_FILE);
export const saveVisited = (ids: number[]) => saveIds(VISITED_FILE, ids);
