import React, { useState, useCallback } from 'react';
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
import { RestaurantCard } from '../../components/RestaurantCard';
import { LocationFilter } from '../../components/LocationFilter';
import { FOOD_CATEGORIES, DIET_FILTERS } from '../../constants/theme';
import { Restaurant } from '../../types';

const ALL_CATEGORIES = [...FOOD_CATEGORIES, ...DIET_FILTERS];
const STAR_FILTERS = [3, 4, 5] as const;

export default function LijstScreen() {
  const {
    filteredRestaurants,
    isLoading,
    loadingProgress,
    filters,
    toggleCategory,
    setZoekterm,
    setLocatie,
    setMinimumSterren,
    beschikbareSteden,
    refresh,
  } = useRestaurants();
  const [refreshing, setRefreshing] = useState(false);

  const onRefresh = useCallback(async () => {
    setRefreshing(true);
    refresh();
    setRefreshing(false);
  }, [refresh]);

  const renderItem = useCallback(({ item }: { item: Restaurant }) => (
    <RestaurantCard restaurant={item} />
  ), []);

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

        {/* Locatie filter */}
        <View style={styles.filterRow}>
          <LocationFilter
            value={filters.locatie}
            onSelect={setLocatie}
            beschikbareSteden={beschikbareSteden}
          />
        </View>

        {/* Categorie chips - flexWrap ipv ScrollView */}
        <View style={styles.chipWrap}>
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

        {/* Sterren-filter */}
        <View style={styles.starRow}>
          {STAR_FILTERS.map(s => {
            const isActive = filters.minimumSterren === s;
            return (
              <TouchableOpacity
                key={s}
                onPress={() => setMinimumSterren(s)}
                activeOpacity={0.7}
                style={[styles.chip, isActive && styles.chipActive]}
              >
                <Text style={[styles.chipText, isActive && styles.chipTextActive]}>
                  ⭐ {s}+
                </Text>
              </TouchableOpacity>
            );
          })}
        </View>

        {/* Resultaat telling */}
        <View style={styles.resultBar}>
          <Text style={styles.resultText}>
            {filteredRestaurants.length} restaurants
            {filters.categorieen.length > 0 || filters.zoekterm || filters.locatie || filters.minimumSterren > 0
              ? ' gevonden'
              : ''}
          </Text>
          {isLoading && (
            <View style={styles.loadingBadge}>
              <ActivityIndicator size="small" color="#EDAA2D" />
              <Text style={styles.loadingSmall}>Details laden...</Text>
            </View>
          )}
        </View>
      </ScrollView>

      {/* Restaurant lijst */}
      <FlatList
        data={filteredRestaurants}
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
    maxHeight: 280,
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
    paddingHorizontal: 16,
    paddingBottom: 4,
    gap: 8,
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
  starRow: {
    flexDirection: 'row',
    paddingHorizontal: 16,
    paddingVertical: 6,
    gap: 6,
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
  },
});
