import React, { useEffect, useMemo, useCallback } from 'react';
import { View, Text, FlatList, StyleSheet } from 'react-native';
import { useRestaurants } from '../../hooks/useRestaurants';
import { useFavorites } from '../../contexts/FavoritesContext';
import { useUserLocation } from '../../hooks/useUserLocation';
import { afstandKm } from '../../utils/afstand';
import { RestaurantCard } from '../../components/RestaurantCard';
import { Restaurant } from '../../types';

export default function OpgeslagenScreen() {
  const { restaurants } = useRestaurants();
  const { favorites } = useFavorites();
  const { coords, request } = useUserLocation();

  // Locatie opvragen zodra dit scherm voor het eerst gebruikt wordt.
  useEffect(() => {
    request();
  }, [request]);

  // Afstand per favoriet (als de locatie bekend is).
  const afstanden = useMemo(() => {
    if (!coords) return null;
    const m = new Map<number, number>();
    for (const r of restaurants) {
      if (favorites.has(r.id) && r.latitude && r.longitude) {
        m.set(r.id, afstandKm(coords.latitude, coords.longitude, r.latitude, r.longitude));
      }
    }
    return m;
  }, [coords, restaurants, favorites]);

  // Favorieten, gesorteerd op afstand (dichtstbij eerst) als die bekend is.
  const opgeslagen = useMemo(() => {
    const lijst = restaurants.filter(r => favorites.has(r.id));
    if (afstanden) {
      lijst.sort(
        (a, b) => (afstanden.get(a.id) ?? Infinity) - (afstanden.get(b.id) ?? Infinity)
      );
    }
    return lijst;
  }, [restaurants, favorites, afstanden]);

  const renderItem = useCallback(({ item }: { item: Restaurant }) => (
    <RestaurantCard restaurant={item} afstandKm={afstanden?.get(item.id) ?? null} />
  ), [afstanden]);

  return (
    <View style={styles.container}>
      <FlatList
        data={opgeslagen}
        renderItem={renderItem}
        keyExtractor={item => item.id.toString()}
        contentContainerStyle={styles.listContent}
        ListEmptyComponent={() => (
          <View style={styles.empty}>
            <Text style={styles.emptyEmoji}>🔖</Text>
            <Text style={styles.emptyText}>Nog niets opgeslagen</Text>
            <Text style={styles.emptySubtext}>
              Tik op het hartje bij een restaurant om het hier te bewaren. Je opgeslagen
              plekken staan hier gesorteerd op afstand.
            </Text>
          </View>
        )}
      />
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: '#FFFBF2',
  },
  listContent: {
    paddingVertical: 8,
    paddingBottom: 32,
    flexGrow: 1,
  },
  empty: {
    flex: 1,
    justifyContent: 'center',
    alignItems: 'center',
    paddingHorizontal: 32,
    paddingTop: 80,
    gap: 12,
  },
  emptyEmoji: {
    fontSize: 48,
  },
  emptyText: {
    fontSize: 17,
    fontWeight: '700',
    color: '#2D2013',
    textAlign: 'center',
  },
  emptySubtext: {
    fontSize: 13,
    color: '#9C8E80',
    textAlign: 'center',
    lineHeight: 20,
  },
});
