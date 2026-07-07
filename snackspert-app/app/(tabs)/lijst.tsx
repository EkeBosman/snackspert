import React, { useState, useCallback, useMemo } from 'react';
import {
  View,
  Text,
  FlatList,
  TextInput,
  TouchableOpacity,
  StyleSheet,
  ActivityIndicator,
  RefreshControl,
  ScrollView,
} from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { useRestaurants } from '../../hooks/useRestaurants';
import { useFavorites } from '../../contexts/FavoritesContext';
import { useUserLocation } from '../../hooks/useUserLocation';
import { afstandKm } from '../../utils/afstand';
import { RestaurantCard } from '../../components/RestaurantCard';
import { LocationFilter } from '../../components/LocationFilter';
import { FOOD_CATEGORIES, DIET_FILTERS } from '../../constants/theme';
import { Restaurant } from '../../types';

const ALL_CATEGORIES = [...FOOD_CATEGORIES, ...DIET_FILTERS];
const STAR_FILTERS = [5] as const;

type Sortering = 'standaard' | 'sterren' | 'afstand';

export default function LijstScreen() {
  const {
    restaurants,
    filteredRestaurants,
    isLoading,
    isLoadingDetails,
    loadingProgress,
    error,
    filters,
    toggleCategory,
    setZoekterm,
    setLocatie,
    setMinimumSterren,
    beschikbareSteden,
    refresh,
  } = useRestaurants();
  const { isFavorite } = useFavorites();
  const { coords, status: locatieStatus, request: vraagLocatie } = useUserLocation();
  const [refreshing, setRefreshing] = useState(false);
  const [sortering, setSortering] = useState<Sortering>('standaard');
  const [alleenFavorieten, setAlleenFavorieten] = useState(false);

  const onRefresh = useCallback(async () => {
    setRefreshing(true);
    refresh();
    setRefreshing(false);
  }, [refresh]);

  // Afstand per restaurant (alleen als de locatie bekend is).
  const afstanden = useMemo(() => {
    if (!coords) return null;
    const m = new Map<number, number>();
    for (const r of filteredRestaurants) {
      if (r.latitude && r.longitude) {
        m.set(r.id, afstandKm(coords.latitude, coords.longitude, r.latitude, r.longitude));
      }
    }
    return m;
  }, [coords, filteredRestaurants]);

  // Toon-lijst: favorieten-filter + gekozen sortering toepassen.
  const weergaveLijst = useMemo(() => {
    let list = alleenFavorieten
      ? filteredRestaurants.filter(r => isFavorite(r.id))
      : [...filteredRestaurants];

    if (sortering === 'sterren') {
      list.sort((a, b) => b.sterren - a.sterren);
    } else if (sortering === 'afstand' && afstanden) {
      list.sort(
        (a, b) => (afstanden.get(a.id) ?? Infinity) - (afstanden.get(b.id) ?? Infinity)
      );
    }
    return list;
  }, [filteredRestaurants, alleenFavorieten, isFavorite, sortering, afstanden]);

  // "Dichtbij" kiezen: vraag zo nodig eerst de locatie op.
  const kiesDichtbij = useCallback(async () => {
    if (sortering === 'afstand') {
      setSortering('standaard');
      return;
    }
    let c = coords;
    if (!c) c = await vraagLocatie();
    if (c) setSortering('afstand');
  }, [sortering, coords, vraagLocatie]);

  const renderItem = useCallback(({ item }: { item: Restaurant }) => (
    <RestaurantCard restaurant={item} afstandKm={afstanden?.get(item.id) ?? null} />
  ), [afstanden]);

  const keyExtractor = useCallback((item: Restaurant) => item.id.toString(), []);

  return (
    <View style={styles.container}>
      {/* Vaste header met filters */}
      <ScrollView style={styles.filterSection} nestedScrollEnabled>
        {/* Zoekbalk */}
        <View style={styles.searchContainer}>
          <TextInput
            style={styles.searchInput}
            placeholder="Zoek restaurant of adres..."
            placeholderTextColor="#9C8E80"
            value={filters.zoekterm}
            onChangeText={setZoekterm}
            autoCapitalize="none"
            autoCorrect={false}
            clearButtonMode="while-editing"
          />
        </View>

        {/* Locatie filter + favorieten */}
        <View style={styles.filterRow}>
          <LocationFilter
            value={filters.locatie}
            onSelect={setLocatie}
            beschikbareSteden={beschikbareSteden}
          />
          <TouchableOpacity
            style={[styles.favChip, alleenFavorieten && styles.favChipActive]}
            onPress={() => setAlleenFavorieten(v => !v)}
            activeOpacity={0.7}
          >
            <Ionicons
              name={alleenFavorieten ? 'heart' : 'heart-outline'}
              size={16}
              color={alleenFavorieten ? '#FFFFFF' : '#D32F2F'}
            />
            <Text style={[styles.favChipText, alleenFavorieten && styles.favChipTextActive]}>
              Favorieten
            </Text>
          </TouchableOpacity>
        </View>

        {/* Sorteeropties */}
        <View style={styles.sorteerRow}>
          <TouchableOpacity
            style={[styles.sorteerChip, sortering === 'standaard' && styles.sorteerChipActive]}
            onPress={() => setSortering('standaard')}
            activeOpacity={0.7}
          >
            <Text style={[styles.sorteerText, sortering === 'standaard' && styles.sorteerTextActive]}>
              Relevantie
            </Text>
          </TouchableOpacity>
          <TouchableOpacity
            style={[styles.sorteerChip, sortering === 'sterren' && styles.sorteerChipActive]}
            onPress={() => setSortering('sterren')}
            activeOpacity={0.7}
          >
            <Text style={[styles.sorteerText, sortering === 'sterren' && styles.sorteerTextActive]}>
              ⭐ Beste
            </Text>
          </TouchableOpacity>
          <TouchableOpacity
            style={[styles.sorteerChip, sortering === 'afstand' && styles.sorteerChipActive]}
            onPress={kiesDichtbij}
            activeOpacity={0.7}
          >
            {locatieStatus === 'loading' ? (
              <ActivityIndicator size="small" color="#A67612" />
            ) : (
              <Text style={[styles.sorteerText, sortering === 'afstand' && styles.sorteerTextActive]}>
                📍 Dichtbij
              </Text>
            )}
          </TouchableOpacity>
        </View>
        {locatieStatus === 'denied' && (
          <Text style={styles.locatieWaarschuwing}>
            Locatie niet beschikbaar — sta locatietoegang toe (Instellingen → Snackspert) om op afstand te sorteren.
          </Text>
        )}

        {/* Sterren-filter + categorie chips samen */}
        <View style={styles.chipWrap}>
          {STAR_FILTERS.map(s => {
            const isActive = filters.minimumSterren === s;
            return (
              <TouchableOpacity
                key={`star-${s}`}
                onPress={() => setMinimumSterren(s)}
                activeOpacity={0.7}
                style={[styles.chip, isActive && styles.chipActive]}
              >
                <Text style={[styles.chipText, isActive && styles.chipTextActive]}>
                  ⭐ {s} sterren
                </Text>
              </TouchableOpacity>
            );
          })}
          {ALL_CATEGORIES.map(cat => {
            const isActive = filters.categorieen.includes(cat);
            return (
              <TouchableOpacity
                key={cat}
                onPress={() => toggleCategory(cat)}
                activeOpacity={0.7}
                style={[styles.chip, isActive && styles.chipActive]}
              >
                <Text style={[styles.chipText, isActive && styles.chipTextActive]}>
                  {cat}
                </Text>
              </TouchableOpacity>
            );
          })}
        </View>

        {/* Resultaat telling */}
        <View style={styles.resultBar}>
          <Text style={styles.resultText}>
            {weergaveLijst.length} {alleenFavorieten ? 'favorieten' : 'restaurants'}
            {!alleenFavorieten &&
            (filters.categorieen.length > 0 || filters.zoekterm || filters.locatie || filters.minimumSterren > 0)
              ? ' gevonden'
              : ''}
          </Text>
          {isLoadingDetails && (
            <View style={styles.loadingBadge}>
              <ActivityIndicator size="small" color="#EDAA2D" />
              <Text style={styles.loadingSmall}>
                {loadingProgress.total > 0
                  ? `Details laden... ${loadingProgress.loaded}/${loadingProgress.total}`
                  : 'Details laden...'}
              </Text>
            </View>
          )}
        </View>
      </ScrollView>

      {/* Restaurant lijst */}
      <FlatList
        data={weergaveLijst}
        renderItem={renderItem}
        keyExtractor={keyExtractor}
        ListEmptyComponent={() => (
          <View style={styles.emptyContainer}>
            {isLoading ? (
              <>
                <ActivityIndicator size="large" color="#EDAA2D" />
                <Text style={styles.emptyText}>
                  Restaurants laden... ({loadingProgress.loaded}/{loadingProgress.total})
                </Text>
              </>
            ) : alleenFavorieten ? (
              <>
                <Text style={styles.emptyEmoji}>🤍</Text>
                <Text style={styles.emptyText}>Nog geen favorieten</Text>
                <Text style={styles.emptySubtext}>Tik op het hartje bij een restaurant om het hier te bewaren</Text>
              </>
            ) : error && restaurants.length === 0 ? (
              <>
                <Text style={styles.emptyEmoji}>📡</Text>
                <Text style={styles.emptyText}>Laden mislukt</Text>
                <Text style={styles.emptySubtext}>{error}</Text>
                <TouchableOpacity style={styles.retryButton} onPress={refresh} activeOpacity={0.8}>
                  <Text style={styles.retryText}>Opnieuw proberen</Text>
                </TouchableOpacity>
              </>
            ) : (
              <>
                <Text style={styles.emptyEmoji}>🔍</Text>
                <Text style={styles.emptyText}>Geen restaurants gevonden</Text>
                <Text style={styles.emptySubtext}>Probeer andere zoektermen of filters</Text>
              </>
            )}
          </View>
        )}
        contentContainerStyle={styles.listContent}
        refreshControl={
          <RefreshControl
            refreshing={refreshing}
            onRefresh={onRefresh}
            tintColor="#EDAA2D"
            colors={['#EDAA2D']}
          />
        }
        initialNumToRender={10}
        maxToRenderPerBatch={10}
        windowSize={5}
        removeClippedSubviews
      />
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: '#FFFBF2',
  },
  filterSection: {
    maxHeight: 330,
    flexGrow: 0,
  },
  listContent: {
    paddingBottom: 32,
  },
  searchContainer: {
    paddingHorizontal: 16,
    paddingTop: 12,
    paddingBottom: 8,
  },
  filterRow: {
    flexDirection: 'row',
    alignItems: 'center',
    paddingHorizontal: 16,
    paddingBottom: 4,
    gap: 8,
  },
  favChip: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 4,
    paddingHorizontal: 12,
    paddingVertical: 8,
    borderRadius: 9999,
    backgroundColor: '#FFF3DC',
  },
  favChipActive: {
    backgroundColor: '#D32F2F',
  },
  favChipText: {
    fontSize: 13,
    color: '#A67612',
    fontWeight: '600',
  },
  favChipTextActive: {
    color: '#FFFFFF',
  },
  sorteerRow: {
    flexDirection: 'row',
    paddingHorizontal: 16,
    paddingTop: 4,
    paddingBottom: 2,
    gap: 8,
  },
  sorteerChip: {
    paddingHorizontal: 14,
    paddingVertical: 7,
    borderRadius: 9999,
    backgroundColor: '#FFF3DC',
    minWidth: 84,
    alignItems: 'center',
  },
  sorteerChipActive: {
    backgroundColor: '#EDAA2D',
  },
  sorteerText: {
    fontSize: 13,
    color: '#A67612',
    fontWeight: '600',
  },
  sorteerTextActive: {
    color: '#FFFFFF',
  },
  locatieWaarschuwing: {
    paddingHorizontal: 16,
    paddingTop: 2,
    fontSize: 12,
    color: '#9C8E80',
  },
  searchInput: {
    backgroundColor: '#FFFFFF',
    borderRadius: 16,
    paddingHorizontal: 16,
    paddingVertical: 10,
    fontSize: 15,
    color: '#2D2013',
    borderWidth: 1,
    borderColor: '#E8E0D5',
  },
  chipWrap: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    paddingHorizontal: 16,
    paddingVertical: 6,
    gap: 6,
  },
  chip: {
    paddingHorizontal: 10,
    paddingVertical: 6,
    borderRadius: 9999,
    backgroundColor: '#FFF3DC',
  },
  chipActive: {
    backgroundColor: '#EDAA2D',
  },
  chipText: {
    fontSize: 12,
    color: '#A67612',
    fontWeight: '600',
  },
  chipTextActive: {
    color: '#FFFFFF',
  },
  resultBar: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    paddingHorizontal: 16,
    paddingVertical: 6,
  },
  resultText: {
    fontSize: 13,
    color: '#6B5D4F',
    fontWeight: '500',
  },
  loadingBadge: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 4,
  },
  loadingSmall: {
    fontSize: 11,
    color: '#9C8E80',
  },
  emptyContainer: {
    justifyContent: 'center',
    alignItems: 'center',
    paddingVertical: 80,
    gap: 12,
  },
  emptyEmoji: {
    fontSize: 48,
  },
  emptyText: {
    fontSize: 17,
    color: '#6B5D4F',
    textAlign: 'center',
  },
  emptySubtext: {
    fontSize: 13,
    color: '#9C8E80',
    textAlign: 'center',
    paddingHorizontal: 24,
  },
  retryButton: {
    marginTop: 8,
    backgroundColor: '#EDAA2D',
    paddingHorizontal: 24,
    paddingVertical: 12,
    borderRadius: 16,
  },
  retryText: {
    color: '#FFFFFF',
    fontWeight: '700',
    fontSize: 15,
  },
});
