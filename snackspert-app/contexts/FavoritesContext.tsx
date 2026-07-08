import React, { createContext, useContext, useState, useEffect, useCallback, useRef, ReactNode } from 'react';
import { loadFavorites, saveFavorites, loadVisited, saveVisited } from '../services/favorites';

interface FavoritesContextValue {
  favorites: Set<number>;
  isFavorite: (id: number) => boolean;
  toggleFavorite: (id: number) => void;
  favoriteCount: number;
  visited: Set<number>;
  isVisited: (id: number) => boolean;
  toggleVisited: (id: number) => void;
}

const FavoritesContext = createContext<FavoritesContextValue | null>(null);

export function FavoritesProvider({ children }: { children: ReactNode }) {
  const [favorites, setFavorites] = useState<Set<number>>(new Set());
  const [visited, setVisited] = useState<Set<number>>(new Set());
  const geladen = useRef(false);

  // Bij opstarten inladen vanaf schijf.
  useEffect(() => {
    let geannuleerd = false;
    (async () => {
      const [favIds, visIds] = await Promise.all([loadFavorites(), loadVisited()]);
      if (geannuleerd) return;
      setFavorites(new Set(favIds));
      setVisited(new Set(visIds));
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

  useEffect(() => {
    if (!geladen.current) return;
    saveVisited(Array.from(visited));
  }, [visited]);

  const toggleFavorite = useCallback((id: number) => {
    setFavorites(prev => {
      const next = new Set(prev);
      next.has(id) ? next.delete(id) : next.add(id);
      return next;
    });
  }, []);

  const toggleVisited = useCallback((id: number) => {
    setVisited(prev => {
      const next = new Set(prev);
      next.has(id) ? next.delete(id) : next.add(id);
      return next;
    });
  }, []);

  const isFavorite = useCallback((id: number) => favorites.has(id), [favorites]);
  const isVisited = useCallback((id: number) => visited.has(id), [visited]);

  const value: FavoritesContextValue = {
    favorites,
    isFavorite,
    toggleFavorite,
    favoriteCount: favorites.size,
    visited,
    isVisited,
    toggleVisited,
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
