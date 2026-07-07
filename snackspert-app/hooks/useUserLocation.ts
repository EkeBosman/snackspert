import { useState, useCallback } from 'react';
import * as Location from 'expo-location';

export interface Coords {
  latitude: number;
  longitude: number;
}

export type LocatieStatus = 'idle' | 'loading' | 'granted' | 'denied';

/**
 * Vraagt (op verzoek) de locatie van de gebruiker op. De permissie wordt pas
 * gevraagd wanneer `request()` wordt aangeroepen, niet bij het opstarten.
 */
export function useUserLocation() {
  const [coords, setCoords] = useState<Coords | null>(null);
  const [status, setStatus] = useState<LocatieStatus>('idle');

  const request = useCallback(async (): Promise<Coords | null> => {
    setStatus('loading');
    try {
      const { status: perm } = await Location.requestForegroundPermissionsAsync();
      if (perm !== 'granted') {
        setStatus('denied');
        return null;
      }
      const pos = await Location.getCurrentPositionAsync({
        accuracy: Location.Accuracy.Balanced,
      });
      const c = { latitude: pos.coords.latitude, longitude: pos.coords.longitude };
      setCoords(c);
      setStatus('granted');
      return c;
    } catch {
      setStatus('denied');
      return null;
    }
  }, []);

  return { coords, status, request };
}
