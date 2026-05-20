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
} from 'react-native';
import { useRestaurants } from '../../hooks/useRestaurants';
import { RestaurantCard } from '../../components/RestaurantCard';
import { CategoryFilter } from '../../components/CategoryFilter';
import { LocationFilter } from '../../components/LocationFilter';
import { Colors, Spacing, BorderRadius, FontSize, Shadow } from '../../constants/theme';
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
      {/* Vaste filters bovenaan (scrollen niet mee) */}
      <View style={styles.searchContainer}>
        <TextInput
          style={styles.searchInput}
          placeholder="Zoek restaurant of adres..."
          placeholderTextColor={Colors.textLight}
          value={filters.zoekterm}
          onChangeText={setZoekterm}
          autoCapitalize="none"
          autoCorrect={false}
          clearButtonMode="while-editing"
        />
      </View>

      <View style={styles.filterRow}>
        <LocationFilter
          value={filters.locatie}
          onSelect={setLocatie}
          beschikbareSteden={beschikbareSteden}
        />
      </View>

      <CategoryFilter
        selected={filters.categorieen}
        onToggle={toggleCategory}
        beschikbaar={beschikbareCategorieen}
      />

      {/* Sterren-filter */}
      <View style={styles.starFilterRow}>
        {STAR_FILTERS.map(s => {
          const isActive = filters.minimumSterren === s;
          return (
            <TouchableOpacity
              key={s}
              style={[styles.starChip, isActive && styles.starChipActive]}
              onPress={() => setMinimumSterren(s)}
              activeOpacity={0.7}
            >
              <Text style={[styles.starChipText, isActive && styles.starChipTextActive]}>
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
            <ActivityIndicator size="small" color={Colors.primary} />
            <Text style={styles.loadingSmall}>Details laden...</Text>
          </View>
        )}
      </View>

      {/* Alleen de lijst scrollt */}
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
            tintColor={Colors.primary}
            colors={[Colors.primary]}
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
    backgroundColor: Colors.background,
  },
  listContent: {
    paddingBottom: Spacing.xxl,
  },
  searchContainer: {
    paddingHorizontal: Spacing.lg,
    paddingTop: Spacing.lg,
    paddingBottom: Spacing.sm,
  },
  filterRow: {
    flexDirection: 'row',
    paddingHorizontal: Spacing.lg,
    paddingBottom: Spacing.xs,
    gap: Spacing.sm,
  },
  searchInput: {
    backgroundColor: Colors.surface,
    borderRadius: BorderRadius.lg,
    paddingHorizontal: Spacing.lg,
    paddingVertical: Spacing.md,
    fontSize: FontSize.md,
    color: Colors.text,
    borderWidth: 1,
    borderColor: Colors.border,
    ...Shadow.sm,
  },
  starFilterRow: {
    flexDirection: 'row',
    paddingHorizontal: Spacing.lg,
    paddingBottom: Spacing.sm,
    gap: Spacing.sm,
  },
  starChip: {
    paddingHorizontal: Spacing.md,
    paddingVertical: Spacing.xs,
    borderRadius: BorderRadius.full,
    backgroundColor: Colors.categoryBg,
  },
  starChipActive: {
    backgroundColor: Colors.primary,
  },
  starChipText: {
    fontSize: FontSize.sm,
    color: Colors.categoryText,
    fontWeight: '500',
  },
  starChipTextActive: {
    color: Colors.textOnPrimary,
    fontWeight: '600',
  },
  resultBar: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    paddingHorizontal: Spacing.lg,
    paddingVertical: Spacing.sm,
  },
  resultText: {
    fontSize: FontSize.sm,
    color: Colors.textSecondary,
    fontWeight: '500',
  },
  loadingBadge: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: Spacing.xs,
  },
  loadingSmall: {
    fontSize: FontSize.xs,
    color: Colors.textLight,
  },
  emptyContainer: {
    flex: 1,
    justifyContent: 'center',
    alignItems: 'center',
    paddingVertical: 80,
    gap: Spacing.md,
  },
  emptyEmoji: {
    fontSize: 48,
  },
  emptyText: {
    fontSize: FontSize.lg,
    color: Colors.textSecondary,
    textAlign: 'center',
  },
  emptySubtext: {
    fontSize: FontSize.sm,
    color: Colors.textLight,
    textAlign: 'center',
  },
});
