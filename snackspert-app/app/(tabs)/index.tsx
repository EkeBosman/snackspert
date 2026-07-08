import React, { useState, useRef, useMemo } from 'react';
import {
  View,
  Text,
  Image,
  StyleSheet,
  ActivityIndicator,
  TouchableOpacity,
} from 'react-native';
import MapView, { Marker, PROVIDER_GOOGLE } from 'react-native-maps';
import { router } from 'expo-router';
import { Ionicons } from '@expo/vector-icons';
import { useRestaurants } from '../../hooks/useRestaurants';
import { useFavorites } from '../../contexts/FavoritesContext';
import { FilterMenu } from '../../components/FilterMenu';
import { StarRating } from '../../components/StarRating';
import { Colors, Spacing, FontSize, BorderRadius, Shadow, MAP_INITIAL_REGION } from '../../constants/theme';
import { Restaurant } from '../../types';

export default function MapScreen() {
  const {
    restaurants,
    filteredRestaurants,
    isLoading,
    isLoadingDetails,
    loadingProgress,
    error,
    filters,
    setFilters,
    beschikbareCategorieen,
    refresh,
  } = useRestaurants();
  const { isFavorite, toggleFavorite, isVisited, toggleVisited } = useFavorites();
  const mapRef = useRef<MapView>(null);
  const [selectedRestaurant, setSelectedRestaurant] = useState<Restaurant | null>(null);

  // Alleen restaurants met coördinaten tonen op de kaart.
  const restaurantsOpKaart = useMemo(
    () => filteredRestaurants.filter(r => r.latitude && r.longitude),
    [filteredRestaurants]
  );

  const handleCalloutPress = (restaurant: Restaurant) => {
    router.push({
      pathname: '/restaurant/[id]',
      params: {
        id: restaurant.id.toString(),
        lat: restaurant.latitude?.toString() ?? '',
        lng: restaurant.longitude?.toString() ?? '',
      },
    });
  };

  const handleZoomToNetherlands = () => {
    mapRef.current?.animateToRegion(MAP_INITIAL_REGION, 500);
  };

  // Volledig laadscherm alleen bij de allereerste keer, zolang er nog geen
  // (gecachte) restaurants zijn om te tonen.
  if (isLoading && filteredRestaurants.length === 0) {
    return (
      <View style={styles.loadingContainer}>
        <ActivityIndicator size="large" color={Colors.primary} />
        <Text style={styles.loadingText}>Restaurants laden...</Text>
      </View>
    );
  }

  // Laden mislukt en niets (uit cache) om te tonen: fout + opnieuw proberen.
  if (error && restaurants.length === 0) {
    return (
      <View style={styles.loadingContainer}>
        <Text style={styles.errorEmoji}>📡</Text>
        <Text style={styles.loadingText}>Laden mislukt</Text>
        <Text style={styles.errorDetail}>{error}</Text>
        <TouchableOpacity style={styles.retryButton} onPress={refresh} activeOpacity={0.8}>
          <Text style={styles.retryText}>Opnieuw proberen</Text>
        </TouchableOpacity>
      </View>
    );
  }

  const favorietGeselecteerd = selectedRestaurant ? isFavorite(selectedRestaurant.id) : false;
  const bezochtGeselecteerd = selectedRestaurant ? isVisited(selectedRestaurant.id) : false;

  return (
    <View style={styles.container}>
      {/* Filter-balk */}
      <View style={styles.filterBar}>
        <FilterMenu
          filters={filters}
          setFilters={setFilters}
          beschikbareCategorieen={beschikbareCategorieen}
        />
        <Text style={styles.infoText}>
          {restaurantsOpKaart.length} op de kaart
        </Text>
        {isLoadingDetails && loadingProgress.total > 0 && (
          <View style={styles.loadingBadge}>
            <ActivityIndicator size="small" color={Colors.primary} />
            <Text style={styles.loadingSmall}>
              {loadingProgress.loaded}/{loadingProgress.total}
            </Text>
          </View>
        )}
      </View>

      {/* Kaart */}
      <MapView
        ref={mapRef}
        provider={PROVIDER_GOOGLE}
        style={styles.map}
        initialRegion={MAP_INITIAL_REGION}
        showsUserLocation
        showsMyLocationButton
        showsCompass
        mapType="standard"
      >
        {restaurantsOpKaart.map(restaurant => (
          <Marker
            key={restaurant.id}
            coordinate={{
              latitude: restaurant.latitude!,
              longitude: restaurant.longitude!,
            }}
            pinColor={isVisited(restaurant.id) ? Colors.success : Colors.mapMarker}
            onPress={() => setSelectedRestaurant(restaurant)}
          />
        ))}
      </MapView>

      {/* Zoom-naar-NL knop */}
      <TouchableOpacity
        style={styles.zoomButton}
        onPress={handleZoomToNetherlands}
        activeOpacity={0.8}
      >
        <Text style={styles.zoomButtonText}>🇳🇱</Text>
      </TouchableOpacity>

      {/* Geselecteerd restaurant preview */}
      {selectedRestaurant && (
        <TouchableOpacity
          style={styles.preview}
          onPress={() => handleCalloutPress(selectedRestaurant)}
          activeOpacity={0.9}
        >
          {selectedRestaurant.afbeeldingUrl ? (
            <Image
              source={{ uri: selectedRestaurant.afbeeldingUrl }}
              style={styles.previewThumb}
              resizeMode="cover"
            />
          ) : (
            <View style={styles.previewThumbPlaceholder}>
              <Text style={styles.previewThumbEmoji}>🍟</Text>
            </View>
          )}

          <View style={styles.previewContent}>
            <Text style={styles.previewNaam} numberOfLines={1}>
              {selectedRestaurant.naam}
            </Text>
            <StarRating rating={selectedRestaurant.sterren} size="sm" />
            {selectedRestaurant.adres ? (
              <Text style={styles.previewAdres} numberOfLines={1}>
                {selectedRestaurant.adres}
              </Text>
            ) : null}
          </View>

          <View style={styles.previewActies}>
            <TouchableOpacity
              onPress={() => toggleVisited(selectedRestaurant.id)}
              hitSlop={{ top: 8, bottom: 8, left: 8, right: 8 }}
              activeOpacity={0.7}
            >
              <Ionicons
                name={bezochtGeselecteerd ? 'checkmark-circle' : 'checkmark-circle-outline'}
                size={26}
                color={bezochtGeselecteerd ? Colors.success : Colors.textLight}
              />
            </TouchableOpacity>
            <TouchableOpacity
              onPress={() => toggleFavorite(selectedRestaurant.id)}
              hitSlop={{ top: 8, bottom: 8, left: 8, right: 8 }}
              activeOpacity={0.7}
            >
              <Ionicons
                name={favorietGeselecteerd ? 'heart' : 'heart-outline'}
                size={26}
                color={favorietGeselecteerd ? Colors.error : Colors.textLight}
              />
            </TouchableOpacity>
          </View>
        </TouchableOpacity>
      )}
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: Colors.background,
  },
  map: {
    flex: 1,
  },
  loadingContainer: {
    flex: 1,
    justifyContent: 'center',
    alignItems: 'center',
    backgroundColor: Colors.background,
    gap: Spacing.lg,
  },
  loadingText: {
    fontSize: FontSize.lg,
    color: Colors.textSecondary,
  },
  errorEmoji: {
    fontSize: 44,
  },
  errorDetail: {
    fontSize: FontSize.sm,
    color: Colors.textLight,
    textAlign: 'center',
    paddingHorizontal: Spacing.xl,
  },
  retryButton: {
    marginTop: Spacing.sm,
    backgroundColor: Colors.primary,
    paddingHorizontal: Spacing.xl,
    paddingVertical: Spacing.md,
    borderRadius: BorderRadius.lg,
  },
  retryText: {
    color: Colors.textOnPrimary,
    fontWeight: '700',
    fontSize: FontSize.md,
  },
  filterBar: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: Spacing.md,
    paddingHorizontal: Spacing.lg,
    paddingVertical: Spacing.sm,
  },
  infoText: {
    fontSize: FontSize.sm,
    color: Colors.textSecondary,
  },
  loadingBadge: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: Spacing.xs,
    marginLeft: 'auto',
  },
  loadingSmall: {
    fontSize: FontSize.xs,
    color: Colors.textLight,
  },
  zoomButton: {
    position: 'absolute',
    bottom: 100,
    right: Spacing.lg,
    width: 48,
    height: 48,
    borderRadius: BorderRadius.full,
    backgroundColor: Colors.surface,
    justifyContent: 'center',
    alignItems: 'center',
    ...Shadow.lg,
  },
  zoomButtonText: {
    fontSize: 24,
  },
  preview: {
    position: 'absolute',
    bottom: Spacing.xl,
    left: Spacing.lg,
    right: Spacing.lg,
    backgroundColor: Colors.surface,
    borderRadius: BorderRadius.lg,
    padding: Spacing.md,
    flexDirection: 'row',
    alignItems: 'center',
    ...Shadow.lg,
  },
  previewThumb: {
    width: 64,
    height: 64,
    borderRadius: BorderRadius.md,
    marginRight: Spacing.md,
  },
  previewThumbPlaceholder: {
    width: 64,
    height: 64,
    borderRadius: BorderRadius.md,
    marginRight: Spacing.md,
    backgroundColor: Colors.categoryBg,
    justifyContent: 'center',
    alignItems: 'center',
  },
  previewThumbEmoji: {
    fontSize: 30,
  },
  previewContent: {
    flex: 1,
    gap: Spacing.xs,
  },
  previewNaam: {
    fontSize: FontSize.lg,
    fontWeight: '700',
    color: Colors.text,
  },
  previewAdres: {
    fontSize: FontSize.sm,
    color: Colors.textSecondary,
  },
  previewActies: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: Spacing.md,
    marginLeft: Spacing.sm,
  },
});
