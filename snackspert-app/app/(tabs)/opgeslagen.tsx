import React, { useEffect, useMemo, useCallback, useState } from 'react';
import { View, Text, FlatList, TouchableOpacity, StyleSheet } from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { useRestaurants } from '../../hooks/useRestaurants';
import { useFavorites } from '../../contexts/FavoritesContext';
import { useUserLocation } from '../../hooks/useUserLocation';
import { afstandKm } from '../../utils/afstand';
import { RestaurantCard } from '../../components/RestaurantCard';
import { Restaurant } from '../../types';

type Weergave = 'favorieten' | 'geweest';

export default function OpgeslagenScreen() {
  const { restaurants } = useRestaurants();
  const { favorites, visited } = useFavorites();
  const { coords, request } = useUserLocation();
  const [weergave, setWeergave] = useState<Weergave>('favorieten');

  // Locatie opvragen zodra dit scherm voor het eerst gebruikt wordt.
  useEffect(() => {
    request();
  }, [request]);

  const ids = weergave === 'favorieten' ? favorites : visited;

  // Afstand per restaurant (als de locatie bekend is).
  const afstanden = useMemo(() => {
    if (!coords) return null;
    const m = new Map<number, number>();
    for (const r of restaurants) {
      if (ids.has(r.id) && r.latitude && r.longitude) {
        m.set(r.id, afstandKm(coords.latitude, coords.longitude, r.latitude, r.longitude));
      }
    }
    return m;
  }, [coords, restaurants, ids]);

  // Gekozen lijst, gesorteerd op afstand (dichtstbij eerst) als die bekend is.
  const lijst = useMemo(() => {
    const l = restaurants.filter(r => ids.has(r.id));
    if (afstanden) {
      l.sort((a, b) => (afstanden.get(a.id) ?? Infinity) - (afstanden.get(b.id) ?? Infinity));
    }
    return l;
  }, [restaurants, ids, afstanden]);

  const renderItem = useCallback(({ item }: { item: Restaurant }) => (
    <RestaurantCard restaurant={item} afstandKm={afstanden?.get(item.id) ?? null} />
  ), [afstanden]);

  const leeg = weergave === 'favorieten'
    ? {
        emoji: '🔖',
        titel: 'Nog niets opgeslagen',
        tekst: 'Tik op het hartje bij een restaurant om het hier te bewaren. Je opgeslagen plekken staan hier gesorteerd op afstand.',
      }
    : {
        emoji: '✅',
        titel: 'Nog niets afgevinkt',
        tekst: 'Tik op het vinkje bij een restaurant als je er geweest bent. Afgevinkte plekken verzamel je hier.',
      };

  return (
    <View style={styles.container}>
      {/* Schakelaar tussen favorieten en afgevinkt */}
      <View style={styles.schakelaar}>
        {([
          { key: 'favorieten', label: 'Favorieten', icon: 'heart', aantal: favorites.size },
          { key: 'geweest', label: 'Geweest', icon: 'checkmark-circle', aantal: visited.size },
        ] as const).map(opt => {
          const actief = weergave === opt.key;
          return (
            <TouchableOpacity
              key={opt.key}
              style={[styles.knop, actief && styles.knopActief]}
              onPress={() => setWeergave(opt.key)}
              activeOpacity={0.7}
            >
              <Ionicons
                name={opt.icon}
                size={16}
                color={actief ? '#FFFFFF' : '#A67612'}
              />
              <Text style={[styles.knopText, actief && styles.knopTextActief]}>
                {opt.label} ({opt.aantal})
              </Text>
            </TouchableOpacity>
          );
        })}
      </View>

      <FlatList
        data={lijst}
        renderItem={renderItem}
        keyExtractor={item => item.id.toString()}
        contentContainerStyle={styles.listContent}
        ListEmptyComponent={() => (
          <View style={styles.empty}>
            <Text style={styles.emptyEmoji}>{leeg.emoji}</Text>
            <Text style={styles.emptyText}>{leeg.titel}</Text>
            <Text style={styles.emptySubtext}>{leeg.tekst}</Text>
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
  schakelaar: {
    flexDirection: 'row',
    gap: 8,
    paddingHorizontal: 16,
    paddingTop: 12,
    paddingBottom: 4,
  },
  knop: {
    flex: 1,
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    gap: 6,
    paddingVertical: 10,
    borderRadius: 9999,
    backgroundColor: '#FFF3DC',
  },
  knopActief: {
    backgroundColor: '#EDAA2D',
  },
  knopText: {
    fontSize: 13,
    fontWeight: '700',
    color: '#A67612',
  },
  knopTextActief: {
    color: '#FFFFFF',
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
