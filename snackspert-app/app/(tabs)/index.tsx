import React, { useState, useRef, useMemo } from 'react';
import {
  View,
  Text,
  StyleSheet,
  ActivityIndicator,
  TouchableOpacity,
  Dimensions,
} from 'react-native';
import MapView, { Marker, Callout, Region, PROVIDER_GOOGLE } from 'react-native-maps';
import { router } from 'expo-router';
import { useRestaurants } from '../../hooks/useRestaurants';
import { CategoryFilter } from '../../components/CategoryFilter';
import { StarRating } from '../../components/StarRating';
import { Colors, Spacing, FontSize, BorderRadius, Shadow, MAP_INITIAL_REGION } from '../../constants/theme';
import { Restaurant } from '../../types';

export default function MapScreen() {
  const {
    filteredRestaurants,
    isLoading,
    loadingProgress,
    filters,
    toggleCategory,
    beschikbareCategorieen,
  } = useRestaurants();
  const mapRef = useRef<MapView>(null);
  const [selectedRestaurant, setSelectedRestaurant] = useState<Restaurant | null>(null);

  // Alleen restaurants met coördinaten tonen op de kaart
  const restaurantsOpKaart = useMemo(
    () => filteredRestaurants.filter(r => r.latitude && r.longitude),
    [filteredRestaurants]
  );

  const handleMarkerPress = (restaurant: Restaurant) => {
    setSelectedRestaurant(restaurant);
  };

  const handleCalloutPress = (restaurant: Restaurant) => {
    router.push({
      pathname: '/restaurant/[id]',
      params: { id: restaurant.id.toString() },
    });
  };

  const handleZoomToNetherlands = () => {
    mapRef.current?.animateToRegion(MAP_INITIAL_REGION, 500);
  };

  if (isLoading && loadingProgress.total === 0) {
    return (
      <View style={styles.loadingContainer}>
        <ActivityIndicator size="large" color={Colors.primary} />
        <Text style={styles.loadingText}>Restaurants laden...</Text>
      </View>
    );
  }

  return (
    <View style={styles.container}>
      {/* Categorie filter */}
      <CategoryFilter
        selected={filters.categorieen}
        onToggle={toggleCategory}
        beschikbaar={beschikbareCategorieen}
      />

      {/* Info balk */}
      <View style={styles.infoBar}>
        <Text style={styles.infoText}>
          {restaurantsOpKaart.length} restaurants op de kaart
          {filters.categorieen.length > 0 && ` (gefilterd)`}
        </Text>
        {isLoading && (
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
            pinColor={Colors.mapMarker}
            onPress={() => handleMarkerPress(restaurant)}
          >
            <Callout onPress={() => handleCalloutPress(restaurant)}>
              <View style={styles.callout}>
                <Text style={styles.calloutTitle} numberOfLines={1}>
                  {restaurant.naam}
                </Text>
                {restaurant.sterren > 0 && (
                  <StarRating rating={restaurant.sterren} size="sm" />
                )}
                {restaurant.adres ? (
                  <Text style={styles.calloutAdres} numberOfLines={1}>
                    {restaurant.adres}
                  </Text>
                ) : null}
                <Text style={styles.calloutAction}>Tik voor details →</Text>
              </View>
            </Callout>
          </Marker>
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
            {selectedRestaurant.categorieen.length > 0 && (
              <Text style={styles.previewCats} numberOfLines={1}>
                {selectedRestaurant.categorieen.join(' · ')}
              </Text>
            )}
          </View>
          <View style={styles.previewArrow}>
            <Text style={styles.previewArrowText}>→</Text>
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
  infoBar: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    paddingHorizontal: Spacing.lg,
    paddingBottom: Spacing.sm,
  },
  infoText: {
    fontSize: FontSize.sm,
    color: Colors.textSecondary,
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
  callout: {
    width: 200,
    padding: Spacing.sm,
  },
  calloutTitle: {
    fontSize: FontSize.md,
    fontWeight: '700',
    color: Colors.text,
    marginBottom: Spacing.xs,
  },
  calloutAdres: {
    fontSize: FontSize.xs,
    color: Colors.textSecondary,
    marginTop: Spacing.xs,
  },
  calloutAction: {
    fontSize: FontSize.xs,
    color: Colors.primary,
    fontWeight: '600',
    marginTop: Spacing.sm,
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
    padding: Spacing.lg,
    flexDirection: 'row',
    alignItems: 'center',
    ...Shadow.lg,
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
  previewCats: {
    fontSize: FontSize.xs,
    color: Colors.primary,
  },
  previewArrow: {
    width: 40,
    height: 40,
    borderRadius: BorderRadius.full,
    backgroundColor: Colors.primary,
    justifyContent: 'center',
    alignItems: 'center',
    marginLeft: Spacing.md,
  },
  previewArrowText: {
    fontSize: FontSize.lg,
    color: Colors.textOnPrimary,
    fontWeight: '700',
  },
});
