import React, { useState, useCallback } from 'react';
import {
  View,
  Text,
  FlatList,
  TextInput,
  StyleSheet,
  ActivityIndicator,
  RefreshControl,
} from 'react-native';
import { useRestaurants } from '../../hooks/useRestaurants';
import { RestaurantCard } from '../../components/RestaurantCard';
import { CategoryFilter } from '../../components/CategoryFilter';
import { Colors, Spacing, BorderRadius, FontSize, Shadow } from '../../constants/theme';
import { Restaurant } from '../../types';

export default function LijstScreen() {
  const {
    filteredRestaurants,
    isLoading,
    loadingProgress,
    filters,
    toggleCategory,
    setZoekterm,
    beschikbareCategorieen,
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

  const ListHeader = () => (
    <View>
      {/* Zoekbalk */}
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

      {/* Categorie filters */}
      <CategoryFilter
        selected={filters.categorieen}
        onToggle={toggleCategory}
        beschikbaar={beschikbareCategorieen}
      />

      {/* Resultaat telling */}
      <View style={styles.resultBar}>
        <Text style={styles.resultText}>
          {filteredRestaurants.length} restaurants
          {filters.categorieen.length > 0 || filters.zoekterm
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
    </View>
  );

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
          <Text style={styles.emptyText}>
            Geen restaurants gevonden
          </Text>
          <Text style={styles.emptySubtext}>
            Probeer andere zoektermen of filters
          </Text>
        </>
      )}
    </View>
  );

  return (
    <View style={styles.container}>
      <FlatList
        data={filteredRestaurants}
        renderItem={renderItem}
        keyExtractor={keyExtractor}
        ListHeaderComponent={ListHeader}
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
