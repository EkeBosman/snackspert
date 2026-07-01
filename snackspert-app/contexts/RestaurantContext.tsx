import React, { createContext, useContext, useState, useEffect, useCallback, useMemo, useRef, ReactNode } from 'react';
import { Restaurant, FilterState } from '../types';
import { fetchAlleRestaurants, fetchRestaurantDetail } from '../services/api';

interface RestaurantContextValue {
  restaurants: Restaurant[];
  filteredRestaurants: Restaurant[];
  isLoading: boolean;
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

export function RestaurantProvider({ children }: { children: ReactNode }) {
  const [restaurants, setRestaurants] = useState<Restaurant[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [loadingProgress, setLoadingProgress] = useState({ loaded: 0, total: 0 });
  const [error, setError] = useState<string | null>(null);
  const stopBackgroundRef = useRef(false);
  const [filters, setFilters] = useState<FilterState>({
    categorieen: [],
    zoekterm: '',
    locatie: '',
    minimumSterren: 0,
  });

  const loadRestaurants = useCallback(async () => {
    setIsLoading(true);
    setError(null);
    stopBackgroundRef.current = false;

    try {
      const summaries = await fetchAlleRestaurants((loaded, total) => {
        setLoadingProgress({ loaded, total });
      });

      const fullRestaurants: Restaurant[] = summaries.map(summary => ({
        id: summary.id,
        naam: summary.naam,
        slug: summary.slug,
        adres: '',
        stad: '',
        tekst: '',
        sterren: 0,
        sterrenTekst: '',
        afbeeldingUrl: summary.afbeeldingUrl || '',
        paginaUrl: summary.paginaUrl,
        categorieen: summary.categorieen,
        latitude: null,
        longitude: null,
      }));

      setRestaurants(fullRestaurants);
      setIsLoading(false);

      const batchSize = 15;
      let errorCount = 0;
      for (let i = 0; i < fullRestaurants.length; i += batchSize) {
        if (stopBackgroundRef.current) break;

        const batch = fullRestaurants.slice(i, i + batchSize);
        const details = await Promise.allSettled(
          batch.map(r => fetchRestaurantDetail(r.paginaUrl))
        );

        let batchErrors = 0;
        setRestaurants(prev => {
          const updated = [...prev];
          for (let j = 0; j < batch.length; j++) {
            const result = details[j];
            if (result.status === 'fulfilled') {
              const idx = updated.findIndex(r => r.id === batch[j].id);
              if (idx >= 0) {
                updated[idx] = {
                  ...updated[idx],
                  ...result.value,
                  naam: result.value.naam || updated[idx].naam,
                  latitude: result.value.latitude || updated[idx].latitude,
                  longitude: result.value.longitude || updated[idx].longitude,
                };
              }
            } else {
              batchErrors++;
            }
          }
          return updated;
        });

        errorCount += batchErrors;
        const delay = errorCount > 10 ? 2000 : 200;
        await new Promise(r => setTimeout(r, delay));
      }
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Er ging iets mis bij het laden');
      setIsLoading(false);
    }
  }, []);

  useEffect(() => {
    loadRestaurants();
    return () => { stopBackgroundRef.current = true; };
  }, [loadRestaurants]);

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
    refresh: loadRestaurants,
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
