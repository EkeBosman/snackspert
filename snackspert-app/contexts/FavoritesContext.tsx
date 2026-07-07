import React, { createContext, useContext, useState, useEffect, useCallback, useRef, ReactNode } from 'react';
import { loadFavorites, saveFavorites } from '../services/favorites';

interface FavoritesContextValue {
  favorites: Set<number>;
  isFavorite: (id: number) => boolean;
  toggleFavorite: (id: number) => void;
  count: number;
}

const FavoritesContext = createContext<FavoritesContextValue | null>(null);

export function FavoritesProvider({ children }: { children: ReactNode }) {
  const [favorites, setFavorites] = useState<Set<number>>(new Set());
  const geladen = useRef(false);

  // Bij opstarten inladen vanaf schijf.
  useEffect(() => {
    let geannuleerd = false;
    (async () => {
      const ids = await loadFavorites();
      if (geannuleerd) return;
      setFavorites(new Set(ids));
      geladen.current = true;
    })();
    return () => { geannuleerd = true; };
  }, []);

  // Persist bij elke wijziging (pas nadat de initiële lading binnen is,
  // anders zou een vroege render de opgeslagen lijst met leeg overschrijven).
  useEffect(() => {
    if (!geladen.current) return;
    saveFavorites(Array.from(favorites));
  }, [favorites]);

  const toggleFavorite = useCallback((id: number) => {
    setFavorites(prev => {
      const next = new Set(prev);
      if (next.has(id)) {
        next.delete(id);
      } else {
        next.add(id);
      }
      return next;
    });
  }, []);

  const isFavorite = useCallback((id: number) => favorites.has(id), [favorites]);

  const value: FavoritesContextValue = {
    favorites,
    isFavorite,
    toggleFavorite,
    count: favorites.size,
  };

  return (
    <FavoritesContext.Provider value={value}>
      {children}
    </FavoritesContext.Provider>
  );
}

export function useFavorites() {
  const ctx = useContext(FavoritesContext);
  if (!ctx) throw new Error('useFavorites must be used within FavoritesProvider');
  return ctx;
}
