import { File, Paths } from 'expo-file-system';

/**
 * Persistente opslag voor de "Volg Snackspert"-modal: hoe vaak de app is
 * geopend, of er een betekenisvolle actie is geweest, wanneer de modal voor
 * het laatst is getoond, en of de gebruiker al is gaan volgen.
 */

export interface EngagementState {
  opens: number;
  heeftActie: boolean;
  laatstGetoond: number; // ms timestamp, 0 = nooit
  gevolgd: boolean;
}

const FILE_NAME = 'engagement.v1.json';

const LEEG: EngagementState = {
  opens: 0,
  heeftActie: false,
  laatstGetoond: 0,
  gevolgd: false,
};

function getFile(): File {
  return new File(Paths.document, FILE_NAME);
}

export async function loadEngagement(): Promise<EngagementState> {
  try {
    const file = getFile();
    if (!file.exists) return { ...LEEG };
    const parsed = JSON.parse(await file.text());
    return {
      opens: typeof parsed.opens === 'number' ? parsed.opens : 0,
      heeftActie: !!parsed.heeftActie,
      laatstGetoond: typeof parsed.laatstGetoond === 'number' ? parsed.laatstGetoond : 0,
      gevolgd: !!parsed.gevolgd,
    };
  } catch {
    return { ...LEEG };
  }
}

export async function saveEngagement(state: EngagementState): Promise<void> {
  try {
    const file = getFile();
    if (!file.exists) file.create();
    file.write(JSON.stringify(state));
  } catch {
    // Best-effort.
  }
}
