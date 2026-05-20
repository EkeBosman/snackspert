import React, { useState, useCallback } from 'react';
import {
  View,
  Text,
  FlatList,
  TextInput,
  ScrollView,
  TouchableOpacity,
  StyleSheet,
  ActivityIndicator,
  RefreshControl,
} from 'react-native';
import { useRestaurants } from '../../hooks/useRestaurants';
import { RestaurantCard } from '../../components/RestaurantCard';
import { LocationFilter } from '../../components/LocationFilter';
import { Colors, Spacing, BorderRadius, FontSize, Shadow } from '../../constants/theme';
import { FOOD_CATEGORIES, DIET_FILTERS } from '../../constants/theme';
import { Restaurant } from '../../types';

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
    beschikbareCategorieen,
    beschikbareSteden,
    refresh,
  } = useRestaurants();
  const [refreshing, setRefreshing] = useState(false);

  const categories = beschikbareCategorieen.length > 0
    ? beschikbareCategorieen
    : [...FOOD_CATEGORIES, ...DIET_FILTERS];

  const onRefresh = useCallback(async () => {
    setRefreshing(true);
    refresh();
    setRefreshing(false);
  }, [refresh]);

  const renderItem = useCallback(({ item }: { item: Restaurant }) => (
    <RestaurantCard restaurant={item} />
  ), []);

  const keyExtractor = useCallback((item: Restaurant) => item.id.toString(), []);

  const ListEmpty = () => (
    <View style={styles.emptyContainer}>
      {isLoading ? (
        <>
          <ActivityIndicator size="large" color={Colors.primary} />
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
  );

  return (
    <View style={styles.container}>
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

      {/* Categorie chips (inline, geen apart component) */}
      <ScrollView
        horizontal
        showsHorizontalScrollIndicator={false}
        contentContainerStyle={styles.chipRow}
      >
        {categories.map(cat => {
          const isActive = filters.categorieen.includes(cat);
          return (
            <TouchableOpacity
              key={cat}
              style={[
                styles.chip,
                { backgroundColor: isActive ? '#EDAA2D' : '#FFF3DC' },
              ]}
              onPress={() => toggleCategory(cat)}
              activeOpacity={0.7}
            >
              <Text style={{
                fontSize: 13,
                color: isActive ? '#FFFFFF' : '#A67612',
                fontWeight: isActive ? 'bold' : 'normal',
              }}>
                {cat}
              </Text>
            </TouchableOpacity>
          );
        })}
      </ScrollView>

      {/* Sterren-filter */}
      <View style={styles.starFilterRow}>
        {STAR_FILTERS.map(s => {
          const isActive = filters.minimumSterren === s;
          return (
            <TouchableOpacity
              key={s}
              style={[
                styles.chip,
                { backgroundColor: isActive ? '#EDAA2D' : '#FFF3DC' },
              ]}
              onPress={() => setMinimumSterren(s)}
              activeOpacity={0.7}
            >
              <Text style={{
                fontSize: 13,
                color: isActive ? '#FFFFFF' : '#A67612',
                fontWeight: isActive ? 'bold' : 'normal',
              }}>
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

      {/* Restaurant lijst */}
      <FlatList
        data={filteredRestaurants}
        renderItem={renderItem}
        keyExtractor={keyExtractor}
        ListEmptyComponent={ListEmpty}
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
  listContent: {
    paddingBottom: 32,
  },
  searchContainer: {
    paddingHorizontal: 16,
    paddingTop: 16,
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
    paddingVertical: 12,
    fontSize: 15,
    color: '#2D2013',
    borderWidth: 1,
    borderColor: '#E8E0D5',
  },
  chipRow: {
    flexDirection: 'row',
    alignItems: 'center',
    paddingHorizontal: 16,
    paddingVertical: 8,
    gap: 8,
  },
  chip: {
    paddingHorizontal: 12,
    paddingVertical: 8,
    borderRadius: 9999,
  },
  starFilterRow: {
    flexDirection: 'row',
    paddingHorizontal: 16,
    paddingBottom: 8,
    gap: 8,
  },
  resultBar: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    paddingHorizontal: 16,
    paddingVertical: 8,
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
    flex: 1,
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
