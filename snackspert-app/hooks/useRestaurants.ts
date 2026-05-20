import { useState, useEffect, useCallback, useMemo } from 'react';
import { Restaurant, RestaurantSummary, FilterState } from '../types';
import { fetchAlleRestaurants, fetchAlleLocaties } from '../services/api';

interface UseRestaurantsReturn {
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
  beschikbareCategorieen: string[];
  beschikbareSteden: string[];
  refresh: () => void;
}

export function useRestaurants(): UseRestaurantsReturn {
  const [restaurants, setRestaurants] = useState<Restaurant[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [loadingProgress, setLoadingProgress] = useState({ loaded: 0, total: 0 });
  const [error, setError] = useState<string | null>(null);
  const [filters, setFilters] = useState<FilterState>({
    categorieen: [],
    zoekterm: '',
    locatie: '',
    minimumSterren: 0,
  });

  const loadRestaurants = useCallback(async () => {
    setIsLoading(true);
    setError(null);

    try {
      // Stap 1: Haal de lijst op via REST API (snel: ~8 requests)
      const summaries = await fetchAlleRestaurants((loaded, total) => {
        setLoadingProgress({ loaded, total });
      });

      // Stap 2: Haal alle locaties op van de overzichtspagina (1 request)
      const locaties = await fetchAlleLocaties();

      // Stap 3: Combineer data - locaties matchen op URL
      const fullRestaurants: Restaurant[] = summaries.map(summary => {
        let lat: number | null = null;
        let lng: number | null = null;

        for (const [key, loc] of locaties.entries()) {
          if (key.includes(summary.slug) || summary.paginaUrl.includes(key)) {
            lat = loc.lat;
            lng = loc.lng;
            break;
          }
        }

        return {
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
          latitude: lat,
          longitude: lng,
        };
      });

      setRestaurants(fullRestaurants);

      // Details worden NIET meer bij opstarten geladen.
      // Pas als de gebruiker op een restaurant tikt, wordt de
      // detailpagina opgehaald (in het [id].tsx scherm).
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Er ging iets mis bij het laden');
    } finally {
      setIsLoading(false);
    }
  }, []);

  useEffect(() => {
    loadRestaurants();
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

  // Alle unieke categorieën uit de data
  const beschikbareCategorieen = useMemo(() => {
    const cats = new Set<string>();
    for (const r of restaurants) {
      for (const c of r.categorieen) {
        cats.add(c);
      }
    }
    return Array.from(cats).sort();
  }, [restaurants]);

  // Alle unieke steden uit de data (gesorteerd op aantal restaurants)
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

  // Gefilterde restaurants
  const filteredRestaurants = useMemo(() => {
    return restaurants.filter(r => {
      // Zoekterm filter
      if (filters.zoekterm) {
        const term = filters.zoekterm.toLowerCase();
        if (
          !r.naam.toLowerCase().includes(term) &&
          !r.adres.toLowerCase().includes(term)
        ) {
          return false;
        }
      }

      // Locatie filter
      if (filters.locatie) {
        const loc = filters.locatie.toLowerCase();
        if (
          !r.stad.toLowerCase().includes(loc) &&
          !r.adres.toLowerCase().includes(loc)
        ) {
          return false;
        }
      }

      // Categorie filter (restaurant moet minstens 1 geselecteerde categorie hebben)
      if (filters.categorieen.length > 0) {
        if (!filters.categorieen.some(c => r.categorieen.includes(c))) {
          return false;
        }
      }

      // Sterren filter
      if (filters.minimumSterren > 0 && r.sterren < filters.minimumSterren) {
        return false;
      }

      return true;
    });
  }, [restaurants, filters]);

  return {
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
    beschikbareCategorieen,
    beschikbareSteden,
    refresh: loadRestaurants,
  };
}
