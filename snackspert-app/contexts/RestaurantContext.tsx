import React, { createContext, useContext, useState, useEffect, useCallback, useMemo, useRef, ReactNode } from 'react';
import { Restaurant, FilterState } from '../types';
import { fetchAlleRestaurants, fetchRestaurantDetail } from '../services/api';
import { loadCache, saveCache } from '../services/cache';

interface RestaurantContextValue {
  restaurants: Restaurant[];
  filteredRestaurants: Restaurant[];
  isLoading: boolean;
  isLoadingDetails: boolean;
  loadingProgress: { loaded: number; total: number };
  error: string | null;
  filters: FilterState;
  setFilters: (filters: FilterState) => void;
  toggleCategory: (category: string) => void;
  setZoekterm: (term: string) => void;
  setLocatie: (locatie: string) => void;
  setMinimumSterren: (sterren: number) => void;
  beschikbareCategorieen: string[];
  beschikbareSteden: string[];
  refresh: () => void;
}

const RestaurantContext = createContext<RestaurantContextValue | null>(null);

/** Maak een leeg Restaurant-object op basis van een summary. */
function summaryNaarRestaurant(s: {
  id: number;
  naam: string;
  slug: string;
  paginaUrl: string;
  afbeeldingUrl: string;
  categorieen: string[];
}): Restaurant {
  return {
    id: s.id,
    naam: s.naam,
    slug: s.slug,
    adres: '',
    stad: '',
    tekst: '',
    sterren: 0,
    sterrenTekst: '',
    afbeeldingUrl: s.afbeeldingUrl || '',
    paginaUrl: s.paginaUrl,
    categorieen: s.categorieen,
    latitude: null,
    longitude: null,
  };
}

export function RestaurantProvider({ children }: { children: ReactNode }) {
  const [restaurants, setRestaurants] = useState<Restaurant[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [isLoadingDetails, setIsLoadingDetails] = useState(false);
  const [loadingProgress, setLoadingProgress] = useState({ loaded: 0, total: 0 });
  const [error, setError] = useState<string | null>(null);
  const stopBackgroundRef = useRef(false);
  const [filters, setFilters] = useState<FilterState>({
    categorieen: [],
    zoekterm: '',
    locatie: '',
    minimumSterren: 0,
  });

  /**
   * Kernlogica: haal de (goedkope) summary-lijst op, hergebruik alles wat al
   * in de cache zit, en scrape/geocode alleen wat nog ontbreekt.
   *
   * @param cachedById  Reeds bekende restaurants (uit de cache), op id.
   * @param forceRescrape  Bij true worden ook bekende restaurants opnieuw
   *   gescraped (om nieuwe recensies/sterren op te halen), maar met hergebruik
   *   van bekende coördinaten zodat er niet opnieuw gegeocodeerd wordt.
   */
  const loadRestaurants = useCallback(async (
    cachedById: Map<number, Restaurant>,
    forceRescrape = false
  ) => {
    setError(null);
    stopBackgroundRef.current = false;

    const heeftCache = cachedById.size > 0;
    // Alleen het volledige laadscherm tonen als er nog niks te zien is.
    if (!heeftCache) {
      setIsLoading(true);
      setLoadingProgress({ loaded: 0, total: 0 });
    }

    try {
      // Stap 1: summary-lijst ophalen (goedkoop, ~7 calls).
      const summaries = await fetchAlleRestaurants((loaded, total) => {
        if (!heeftCache) setLoadingProgress({ loaded, total });
      });

      if (stopBackgroundRef.current) return;

      // Stap 2: samenvoegen met cache. Bekende restaurants hergebruiken we,
      // nieuwe krijgen een lege basis. Verwijderde restaurants vallen vanzelf
      // weg (we volgen de verse summary-lijst).
      const all: Restaurant[] = summaries.map(s => {
        const cached = cachedById.get(s.id);
        if (cached) {
          return {
            ...cached,
            slug: s.slug,
            paginaUrl: s.paginaUrl,
            afbeeldingUrl: cached.afbeeldingUrl || s.afbeeldingUrl,
          };
        }
        return summaryNaarRestaurant(s);
      });

      setRestaurants(all);
      setIsLoading(false);

      const indexById = new Map(all.map((r, i) => [r.id, i]));

      // Stap 3: bepalen wat gescraped moet worden.
      // - Normaal: alleen restaurants zonder coördinaten (nieuw of eerder mislukt).
      // - forceRescrape: alles (maar met hergebruik van bekende coords).
      const teLaden = forceRescrape
        ? all
        : all.filter(r => !r.latitude || !r.longitude);

      if (teLaden.length === 0) {
        // Niets te doen: cache dekt alles. Toch opslaan om verwijderde
        // restaurants uit de cache te schonen.
        await saveCache(all);
        return;
      }

      setIsLoadingDetails(true);
      setLoadingProgress({ loaded: 0, total: teLaden.length });

      const batchSize = 15;
      let errorCount = 0;
      let verwerkt = 0;

      for (let i = 0; i < teLaden.length; i += batchSize) {
        if (stopBackgroundRef.current) break;

        const batch = teLaden.slice(i, i + batchSize);
        const details = await Promise.allSettled(
          batch.map(r => {
            const bekend = forceRescrape && r.latitude && r.longitude
              ? { lat: r.latitude, lng: r.longitude }
              : null;
            return fetchRestaurantDetail(r.paginaUrl, bekend);
          })
        );

        let batchErrors = 0;
        for (let j = 0; j < batch.length; j++) {
          const result = details[j];
          if (result.status === 'fulfilled') {
            const idx = indexById.get(batch[j].id);
            if (idx !== undefined) {
              all[idx] = {
                ...all[idx],
                ...result.value,
                naam: result.value.naam || all[idx].naam,
                latitude: result.value.latitude ?? all[idx].latitude,
                longitude: result.value.longitude ?? all[idx].longitude,
              };
            }
          } else {
            batchErrors++;
          }
        }

        verwerkt += batch.length;
        setRestaurants([...all]);
        setLoadingProgress({ loaded: verwerkt, total: teLaden.length });

        errorCount += batchErrors;
        const delay = errorCount > 10 ? 2000 : 200;
        await new Promise(r => setTimeout(r, delay));
      }

      // Stap 4: definitieve lijst wegschrijven naar de cache.
      await saveCache(all);
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Er ging iets mis bij het laden');
      setIsLoading(false);
    } finally {
      setIsLoadingDetails(false);
    }
  }, []);

  // Bij opstarten: eerst cache tonen (direct), daarna slim verversen.
  useEffect(() => {
    let geannuleerd = false;

    (async () => {
      const cache = await loadCache();
      if (geannuleerd) return;

      let cachedById = new Map<number, Restaurant>();
      if (cache) {
        setRestaurants(cache.restaurants);
        setIsLoading(false);
        cachedById = new Map(cache.restaurants.map(r => [r.id, r]));
      }

      loadRestaurants(cachedById);
    })();

    return () => {
      geannuleerd = true;
      stopBackgroundRef.current = true;
    };
  }, [loadRestaurants]);

  // Pull-to-refresh: volledige herscrape (nieuwe recensies/sterren), maar met
  // hergebruik van bekende coördinaten zodat er niet opnieuw gegeocodeerd wordt.
  const refresh = useCallback(() => {
    const huidigById = new Map(restaurants.map(r => [r.id, r]));
    loadRestaurants(huidigById, true);
  }, [restaurants, loadRestaurants]);

  const toggleCategory = useCallback((category: string) => {
    setFilters(prev => ({
      ...prev,
      categorieen: prev.categorieen.includes(category)
        ? prev.categorieen.filter(c => c !== category)
        : [...prev.categorieen, category],
    }));
  }, []);

  const setZoekterm = useCallback((term: string) => {
    setFilters(prev => ({ ...prev, zoekterm: term }));
  }, []);

  const setLocatie = useCallback((locatie: string) => {
    setFilters(prev => ({ ...prev, locatie }));
  }, []);

  const setMinimumSterren = useCallback((sterren: number) => {
    setFilters(prev => ({
      ...prev,
      minimumSterren: prev.minimumSterren === sterren ? 0 : sterren,
    }));
  }, []);

  const beschikbareCategorieen = useMemo(() => {
    const cats = new Set<string>();
    for (const r of restaurants) {
      for (const c of r.categorieen) {
        cats.add(c);
      }
    }
    return Array.from(cats).sort();
  }, [restaurants]);

  const beschikbareSteden = useMemo(() => {
    const stadCount = new Map<string, number>();
    for (const r of restaurants) {
      if (r.stad) {
        stadCount.set(r.stad, (stadCount.get(r.stad) || 0) + 1);
      }
    }
    return Array.from(stadCount.entries())
      .sort((a, b) => b[1] - a[1])
      .map(([stad]) => stad);
  }, [restaurants]);

  const filteredRestaurants = useMemo(() => {
    return restaurants.filter(r => {
      if (filters.zoekterm) {
        const term = filters.zoekterm.toLowerCase();
        if (!r.naam.toLowerCase().includes(term) && !r.adres.toLowerCase().includes(term)) {
          return false;
        }
      }
      if (filters.locatie) {
        const loc = filters.locatie.toLowerCase();
        if (!r.stad.toLowerCase().includes(loc) && !r.adres.toLowerCase().includes(loc)) {
          return false;
        }
      }
      if (filters.categorieen.length > 0) {
        if (!filters.categorieen.some(c => r.categorieen.includes(c))) {
          return false;
        }
      }
      if (filters.minimumSterren > 0 && r.sterren < filters.minimumSterren) {
        return false;
      }
      return true;
    });
  }, [restaurants, filters]);

  const value: RestaurantContextValue = {
    restaurants,
    filteredRestaurants,
    isLoading,
    isLoadingDetails,
    loadingProgress,
    error,
    filters,
    setFilters,
    toggleCategory,
    setZoekterm,
    setLocatie,
    setMinimumSterren,
    beschikbareCategorieen,
    beschikbareSteden,
    refresh,
  };

  return (
    <RestaurantContext.Provider value={value}>
      {children}
    </RestaurantContext.Provider>
  );
}

export function useRestaurants() {
  const ctx = useContext(RestaurantContext);
  if (!ctx) throw new Error('useRestaurants must be used within RestaurantProvider');
  return ctx;
}
