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
import { useRestaurants } from '../../hooks/useRestaurants';
import { useUserLocation } from '../../hooks/useUserLocation';
import { afstandKm } from '../../utils/afstand';
import { RestaurantCard } from '../../components/RestaurantCard';
import { LocationFilter } from '../../components/LocationFilter';
import { FilterMenu } from '../../components/FilterMenu';
import { Restaurant } from '../../types';

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
    setFilters,
    setZoekterm,
    setLocatie,
    beschikbareCategorieen,
    beschikbareSteden,
    refresh,
  } = useRestaurants();
  const { coords, status: locatieStatus, request: vraagLocatie } = useUserLocation();
  const [refreshing, setRefreshing] = useState(false);
  const [sortering, setSortering] = useState<Sortering>('standaard');

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

  // Toon-lijst: gekozen sortering toepassen.
  const weergaveLijst = useMemo(() => {
    const list = [...filteredRestaurants];
    if (sortering === 'sterren') {
      list.sort((a, b) => b.sterren - a.sterren);
    } else if (sortering === 'afstand' && afstanden) {
      list.sort(
        (a, b) => (afstanden.get(a.id) ?? Infinity) - (afstanden.get(b.id) ?? Infinity)
      );
    }
    return list;
  }, [filteredRestaurants, sortering, afstanden]);

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

        {/* Filter + locatie */}
        <View style={styles.filterRow}>
          <FilterMenu
            filters={filters}
            setFilters={setFilters}
            beschikbareCategorieen={beschikbareCategorieen}
          />
          <LocationFilter
            value={filters.locatie}
            onSelect={setLocatie}
            beschikbareSteden={beschikbareSteden}
          />
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

        {/* Resultaat telling */}
        <View style={styles.resultBar}>
          <Text style={styles.resultText}>
            {weergaveLijst.length} restaurants
            {filters.categorieen.length > 0 || filters.zoekterm || filters.locatie || filters.minimumSterren > 0
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
