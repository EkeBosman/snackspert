import React, { createContext, useContext, useState, useEffect, useCallback, useMemo, useRef, ReactNode } from 'react';
import { Restaurant, FilterState } from '../types';
import {
  fetchAlleRestaurants,
  fetchRestaurantDetail,
} from '../services/api';
import { fetchSiteIndex, SiteIndex, TermOptie } from '../services/lijst';
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
  toggleDieet: (dieet: string) => void;
  setZoekterm: (term: string) => void;
  setLocatie: (locatie: string) => void;
  setMinimumSterren: (sterren: number) => void;
  beschikbareCategorieen: string[];
  beschikbareDieten: string[];
  beschikbareSteden: string[];
  refresh: () => void;
}

const RestaurantContext = createContext<RestaurantContextValue | null>(null);

const LEGE_FILTERS: FilterState = {
  categorieen: [],
  dieten: [],
  zoekterm: '',
  locatie: '',
  minimumSterren: 0,
};

export function RestaurantProvider({ children }: { children: ReactNode }) {
  const [restaurants, setRestaurants] = useState<Restaurant[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [isLoadingDetails, setIsLoadingDetails] = useState(false);
  const [loadingProgress, setLoadingProgress] = useState({ loaded: 0, total: 0 });
  const [error, setError] = useState<string | null>(null);
  // De filteropties zoals de site ze zelf aanbiedt, in de volgorde van de site.
  const [termen, setTermen] = useState<{ categorieen: TermOptie[]; dieten: TermOptie[] }>({
    categorieen: [],
    dieten: [],
  });
  const stopBackgroundRef = useRef(false);
  const [filters, setFilters] = useState<FilterState>(LEGE_FILTERS);

  /**
   * Zet de overzichtsgegevens om in een volledige restaurantlijst, met
   * hergebruik van wat er al in de cache staat.
   *
   * Uit de index komen adres, stad, land, foto, coördinaten, categorieën en
   * diëten. Uit de cache komen de sterren en de recensietekst, want die zijn
   * alleen door de recensiepagina te lezen.
   */
  const bouwLijst = useCallback((
    index: SiteIndex,
    idsPerSlug: Map<string, { id: number; naam: string; paginaUrl: string; afbeeldingUrl: string }>,
    cachedBySlug: Map<string, Restaurant>
  ): Restaurant[] => {
    return index.items.map(item => {
      const cached = cachedBySlug.get(item.slug);
      const wp = idsPerSlug.get(item.slug);
      const coord = index.coords.get(item.slug);

      let sterren = cached?.sterren ?? 0;
      let sterrenTekst = cached?.sterrenTekst ?? '';
      // De site heeft een categorie "5 sterren". Zit een restaurant daarin, dan
      // weten we zijn beoordeling al zonder de recensie te lezen — dat scheelt
      // ruim honderd pagina's ophalen.
      if (sterren === 0 && index.vijfSterrenSlugs.has(item.slug)) {
        sterren = 5;
        sterrenTekst = '⭐⭐⭐⭐⭐';
      }

      return {
        id: wp?.id ?? cached?.id ?? 0,
        naam: item.naam || wp?.naam || cached?.naam || '',
        slug: item.slug,
        adres: item.adres,
        stad: item.stad,
        land: item.land,
        tekst: cached?.tekst ?? '',
        sterren,
        sterrenTekst,
        afbeeldingUrl: item.afbeeldingUrl || wp?.afbeeldingUrl || cached?.afbeeldingUrl || '',
        paginaUrl: item.paginaUrl || wp?.paginaUrl || cached?.paginaUrl || '',
        categorieen: index.categorieenPerSlug.get(item.slug) ?? [],
        dieten: index.dietenPerSlug.get(item.slug) ?? [],
        latitude: coord?.lat ?? cached?.latitude ?? null,
        longitude: coord?.lng ?? cached?.longitude ?? null,
      };
    });
  }, []);

  /**
   * Kernlogica.
   *
   * Stap 1 levert in een kleine twintig verzoeken alles waar de kaart, de lijst
   * en de filters op draaien. Stap 2 vult op de achtergrond de sterren bij van
   * de restaurants waarvan we die nog niet kennen — doorgaans alleen nieuwe
   * recensies, want de cache houdt ze vast.
   *
   * @param cachedBySlug   Wat we al weten, op slug.
   * @param forceRescrape  Alle recensiepagina's opnieuw lezen (pull-to-refresh),
   *   om gewijzigde beoordelingen op te pikken.
   */
  const loadRestaurants = useCallback(async (
    cachedBySlug: Map<string, Restaurant>,
    forceRescrape = false
  ) => {
    setError(null);
    stopBackgroundRef.current = false;

    const heeftCache = cachedBySlug.size > 0;
    if (!heeftCache) {
      setIsLoading(true);
      setLoadingProgress({ loaded: 0, total: 0 });
    }

    try {
      // Stap 1: de overzichtspagina (alle restaurants, hun adressen, foto's,
      // coördinaten en alle categorieën/diëten) plus de REST-lijst voor de
      // post-id's. Allebei tegelijk.
      const [index, summaries] = await Promise.all([
        fetchSiteIndex((gereed, totaal) => {
          if (!heeftCache) setLoadingProgress({ loaded: gereed, total: totaal });
        }),
        // De id's zijn een nette-maar-niet-essentiële toevoeging; valt dit om,
        // dan werkt de app verder op de slug.
        fetchAlleRestaurants().catch(() => []),
      ]);

      if (stopBackgroundRef.current) return;

      // Een lege lijst betekent vrijwel zeker een storing. Dan laten we staan
      // wat er al is in plaats van een goede cache weg te gooien.
      if (index.items.length === 0) {
        if (!heeftCache) {
          setError('Kon geen restaurants ophalen. Controleer je internetverbinding en probeer opnieuw.');
        }
        setIsLoading(false);
        return;
      }

      if (index.categorieen.length > 0 || index.dieten.length > 0) {
        setTermen({ categorieen: index.categorieen, dieten: index.dieten });
      }

      const idsPerSlug = new Map(summaries.map(s => [s.slug, s]));
      const all = bouwLijst(index, idsPerSlug, cachedBySlug);

      setRestaurants(all);
      setIsLoading(false);

      // De app is nu volledig bruikbaar: kaart, lijst, zoeken en alle filters.
      // Vanaf hier gaat het alleen nog om de sterren.
      await saveCache(all);

      const indexBySlug = new Map(all.map((r, i) => [r.slug, i]));

      // Stap 2: sterren. Alleen waar we ze nog niet hebben — een restaurant met
      // tekst maar zonder sterren is al eens gelezen en heeft er simpelweg geen.
      const teLaden = forceRescrape
        ? all
        : all.filter(r => r.sterren === 0 && !r.tekst);

      if (teLaden.length === 0) return;

      setIsLoadingDetails(true);
      setLoadingProgress({ loaded: 0, total: teLaden.length });

      // Doorlopende werkploeg: CONCURRENCY pagina's tegelijk, zonder gaten
      // tussen batches (elke worker pakt meteen het volgende item op).
      const CONCURRENCY = 16;
      let errorCount = 0;
      let verwerkt = 0;
      let volgende = 0;

      const worker = async () => {
        while (!stopBackgroundRef.current) {
          const i = volgende++;
          if (i >= teLaden.length) return;
          const r = teLaden[i];

          try {
            // Coördinaten kennen we al; meegeven zodat de dure geocoding wordt
            // overgeslagen (alleen terugval als ze ontbreken).
            const bekend = r.latitude && r.longitude
              ? { lat: r.latitude, lng: r.longitude }
              : null;
            const detail = await fetchRestaurantDetail(r.paginaUrl, bekend);
            const idx = indexBySlug.get(r.slug);
            if (idx !== undefined) {
              const huidig = all[idx];
              all[idx] = {
                ...huidig,
                tekst: detail.tekst || huidig.tekst,
                // Een gelezen beoordeling gaat voor op de schatting uit de
                // categorie "5 sterren".
                sterren: detail.sterren ?? huidig.sterren,
                sterrenTekst: detail.sterrenTekst || huidig.sterrenTekst,
                latitude: huidig.latitude ?? detail.latitude ?? null,
                longitude: huidig.longitude ?? detail.longitude ?? null,
              };
            }
          } catch {
            errorCount++;
          }

          verwerkt++;
          if (verwerkt % 8 === 0 || verwerkt === teLaden.length) {
            setRestaurants([...all]);
            setLoadingProgress({ loaded: verwerkt, total: teLaden.length });
          }
          // Tussentijds opslaan zodat een afgesloten app de voortgang behoudt.
          if (verwerkt % 75 === 0) {
            await saveCache(all);
          }
          // Adaptieve rem als de server veel fouten geeft (bijv. Wordfence).
          if (errorCount > 15) {
            await new Promise(res => setTimeout(res, 400));
          }
        }
      };

      await Promise.all(Array.from({ length: CONCURRENCY }, () => worker()));

      setRestaurants([...all]);
      setLoadingProgress({ loaded: teLaden.length, total: teLaden.length });
      await saveCache(all);
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Er ging iets mis bij het laden');
      setIsLoading(false);
    } finally {
      setIsLoadingDetails(false);
    }
  }, [bouwLijst]);

  // Bij opstarten: eerst cache tonen (direct), daarna verversen.
  useEffect(() => {
    let geannuleerd = false;

    (async () => {
      const cache = await loadCache();
      if (geannuleerd) return;

      let cachedBySlug = new Map<string, Restaurant>();
      if (cache) {
        setRestaurants(cache.restaurants);
        setIsLoading(false);
        cachedBySlug = new Map(cache.restaurants.map(r => [r.slug, r]));
      }

      loadRestaurants(cachedBySlug);
    })();

    return () => {
      geannuleerd = true;
      stopBackgroundRef.current = true;
    };
  }, [loadRestaurants]);

  // Pull-to-refresh: alle recensies opnieuw lezen, met hergebruik van bekende
  // coördinaten zodat er niet opnieuw gegeocodeerd wordt.
  const refresh = useCallback(() => {
    const huidigBySlug = new Map(restaurants.map(r => [r.slug, r]));
    loadRestaurants(huidigBySlug, true);
  }, [restaurants, loadRestaurants]);

  const toggleCategory = useCallback((category: string) => {
    setFilters(prev => ({
      ...prev,
      categorieen: prev.categorieen.includes(category)
        ? prev.categorieen.filter(c => c !== category)
        : [...prev.categorieen, category],
    }));
  }, []);

  const toggleDieet = useCallback((dieet: string) => {
    setFilters(prev => ({
      ...prev,
      dieten: prev.dieten.includes(dieet)
        ? prev.dieten.filter(d => d !== dieet)
        : [...prev.dieten, dieet],
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

  /**
   * De categorieën zoals de site ze aanbiedt. Lukt dat niet (geen verbinding
   * bij een koude start), dan vallen we terug op wat er in de geladen
   * restaurants zit, zodat het menu nooit leeg is.
   */
  const beschikbareCategorieen = useMemo(() => {
    if (termen.categorieen.length > 0) return termen.categorieen.map(t => t.label);
    const uit = new Set<string>();
    for (const r of restaurants) for (const c of r.categorieen) uit.add(c);
    return Array.from(uit).sort();
  }, [termen.categorieen, restaurants]);

  const beschikbareDieten = useMemo(() => {
    if (termen.dieten.length > 0) return termen.dieten.map(t => t.label);
    const uit = new Set<string>();
    for (const r of restaurants) for (const d of r.dieten ?? []) uit.add(d);
    return Array.from(uit).sort();
  }, [termen.dieten, restaurants]);

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
      // Dieet is een eis, niet een keuze uit meer: kies je Vega én Vegan, dan
      // wil je zaken die beide bieden.
      if (filters.dieten.length > 0) {
        const eigen = r.dieten ?? [];
        if (!filters.dieten.every(d => eigen.includes(d))) {
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
    toggleDieet,
    setZoekterm,
    setLocatie,
    setMinimumSterren,
    beschikbareCategorieen,
    beschikbareDieten,
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
