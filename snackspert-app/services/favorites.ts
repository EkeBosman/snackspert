import { File, Paths } from 'expo-file-system';

/**
 * Persistente opslag van favoriete restaurants (op restaurant-id).
 */

const FAVORITES_FILE_NAME = 'favorites.v1.json';

function getFile(): File {
  return new File(Paths.document, FAVORITES_FILE_NAME);
}

/** Lees de opgeslagen favoriet-ids. */
export async function loadFavorites(): Promise<number[]> {
  try {
    const file = getFile();
    if (!file.exists) return [];
    const raw = await file.text();
    const parsed = JSON.parse(raw);
    if (!Array.isArray(parsed)) return [];
    return parsed.filter((x): x is number => typeof x === 'number');
  } catch {
    return [];
  }
}

/** Sla de favoriet-ids op. */
export async function saveFavorites(ids: number[]): Promise<void> {
  try {
    const file = getFile();
    if (!file.exists) {
      file.create();
    }
    file.write(JSON.stringify(ids));
  } catch {
    // Best-effort; nooit laten crashen.
  }
}
