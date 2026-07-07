import React, { useState, useRef, useMemo } from 'react';
import {
  View,
  Text,
  Image,
  StyleSheet,
  ActivityIndicator,
  TouchableOpacity,
} from 'react-native';
import MapView, { Marker, Region, PROVIDER_GOOGLE } from 'react-native-maps';
import Supercluster from 'supercluster';
import { router } from 'expo-router';
import { Ionicons } from '@expo/vector-icons';
import { useRestaurants } from '../../hooks/useRestaurants';
import { useFavorites } from '../../contexts/FavoritesContext';
import { CategoryFilter } from '../../components/CategoryFilter';
import { StarRating } from '../../components/StarRating';
import { Colors, Spacing, FontSize, BorderRadius, Shadow, MAP_INITIAL_REGION } from '../../constants/theme';
import { Restaurant } from '../../types';

type PuntData = { restaurantId: number };

export default function MapScreen() {
  const {
    restaurants,
    filteredRestaurants,
    isLoading,
    isLoadingDetails,
    loadingProgress,
    error,
    filters,
    toggleCategory,
    beschikbareCategorieen,
    refresh,
  } = useRestaurants();
  const { isFavorite, toggleFavorite } = useFavorites();
  const mapRef = useRef<MapView>(null);
  const [selectedRestaurant, setSelectedRestaurant] = useState<Restaurant | null>(null);
  const [region, setRegion] = useState<Region>(MAP_INITIAL_REGION);

  // Alleen restaurants met coördinaten tonen op de kaart.
  const restaurantsOpKaart = useMemo(
    () => filteredRestaurants.filter(r => r.latitude && r.longitude),
    [filteredRestaurants]
  );

  const restaurantById = useMemo(() => {
    const m = new Map<number, Restaurant>();
    for (const r of restaurantsOpKaart) m.set(r.id, r);
    return m;
  }, [restaurantsOpKaart]);

  // Supercluster-index opbouwen uit de zichtbare restaurants.
  const clusterIndex = useMemo(() => {
    const sc = new Supercluster<PuntData>({ radius: 55, maxZoom: 18 });
    sc.load(
      restaurantsOpKaart.map(r => ({
        type: 'Feature' as const,
        properties: { restaurantId: r.id },
        geometry: {
          type: 'Point' as const,
          coordinates: [r.longitude!, r.latitude!],
        },
      }))
    );
    return sc;
  }, [restaurantsOpKaart]);

  // Clusters/punten berekenen voor de huidige kaartuitsnede.
  const clusters = useMemo(() => {
    const bbox: [number, number, number, number] = [
      region.longitude - region.longitudeDelta / 2,
      region.latitude - region.latitudeDelta / 2,
      region.longitude + region.longitudeDelta / 2,
      region.latitude + region.latitudeDelta / 2,
    ];
    const zoom = Math.round(Math.log2(360 / region.longitudeDelta));
    return clusterIndex.getClusters(bbox, Math.max(1, Math.min(20, zoom)));
  }, [clusterIndex, region]);

  const handleMarkerPress = (restaurant: Restaurant) => {
    setSelectedRestaurant(restaurant);
  };

  const handleClusterPress = (clusterId: number, lat: number, lng: number) => {
    const expansionZoom = Math.min(clusterIndex.getClusterExpansionZoom(clusterId), 18);
    const delta = 360 / Math.pow(2, expansionZoom);
    mapRef.current?.animateToRegion(
      { latitude: lat, longitude: lng, latitudeDelta: delta, longitudeDelta: delta },
      350
    );
  };

  const handleCalloutPress = (restaurant: Restaurant) => {
    router.push({
      pathname: '/restaurant/[id]',
      params: {
        id: restaurant.id.toString(),
        // Coördinaten meegeven zodat het detailscherm niet opnieuw hoeft te geocoderen.
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
        onRegionChangeComplete={setRegion}
        showsUserLocation
        showsMyLocationButton
        showsCompass
        mapType="standard"
      >
        {clusters.map(punt => {
          const [lng, lat] = punt.geometry.coordinates;
          const props = punt.properties as Supercluster.ClusterProperties & PuntData;

          if ('cluster' in props && props.cluster) {
            const aantal = props.point_count;
            const grootte = aantal < 10 ? 44 : aantal < 50 ? 54 : aantal < 200 ? 64 : 74;
            return (
              <Marker
                key={`cluster-${props.cluster_id}`}
                coordinate={{ latitude: lat, longitude: lng }}
                onPress={() => handleClusterPress(props.cluster_id, lat, lng)}
              >
                <View style={[styles.cluster, { width: grootte, height: grootte, borderRadius: grootte / 2 }]}>
                  <Text style={styles.clusterText}>{aantal}</Text>
                </View>
              </Marker>
            );
          }

          const r = restaurantById.get(props.restaurantId);
          if (!r) return null;
          return (
            <Marker
              key={`r-${r.id}`}
              coordinate={{ latitude: lat, longitude: lng }}
              pinColor={Colors.mapMarker}
              onPress={() => handleMarkerPress(r)}
            />
          );
        })}
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
            {selectedRestaurant.categorieen.length > 0 && (
              <Text style={styles.previewCats} numberOfLines={1}>
                {selectedRestaurant.categorieen.join(' · ')}
              </Text>
            )}
          </View>

          <TouchableOpacity
            style={styles.previewHeart}
            onPress={() => toggleFavorite(selectedRestaurant.id)}
            hitSlop={{ top: 10, bottom: 10, left: 10, right: 10 }}
            activeOpacity={0.7}
          >
            <Ionicons
              name={favorietGeselecteerd ? 'heart' : 'heart-outline'}
              size={24}
              color={favorietGeselecteerd ? Colors.error : Colors.textLight}
            />
          </TouchableOpacity>
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
  cluster: {
    backgroundColor: Colors.primary,
    justifyContent: 'center',
    alignItems: 'center',
    borderWidth: 3,
    borderColor: '#FFFFFF',
    ...Shadow.md,
  },
  clusterText: {
    color: Colors.textOnPrimary,
    fontWeight: '800',
    fontSize: FontSize.md,
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
  previewCats: {
    fontSize: FontSize.xs,
    color: Colors.primary,
  },
  previewHeart: {
    width: 40,
    height: 40,
    justifyContent: 'center',
    alignItems: 'center',
    marginLeft: Spacing.sm,
  },
});
