import React, { useState, useRef, useMemo } from 'react';
import {
  View,
  Text,
  Image,
  StyleSheet,
  ActivityIndicator,
  TouchableOpacity,
  Modal,
  FlatList,
} from 'react-native';
import MapView, { Marker, PROVIDER_GOOGLE } from 'react-native-maps';
import { router } from 'expo-router';
import { Ionicons } from '@expo/vector-icons';
import { useRestaurants } from '../../hooks/useRestaurants';
import { useFavorites } from '../../contexts/FavoritesContext';
import { useUserLocation } from '../../hooks/useUserLocation';
import { FilterMenu } from '../../components/FilterMenu';
import { StarRating } from '../../components/StarRating';
import { bepaalLand, LAND_VLAGGEN } from '../../utils/land';
import { Colors, Spacing, FontSize, BorderRadius, Shadow, MAP_INITIAL_REGION } from '../../constants/theme';
import { Restaurant } from '../../types';

interface LandGroep {
  naam: string;
  vlag: string;
  restaurants: Restaurant[];
}

const PIN_DONKER = '#2D2013';

/**
 * Custom kaart-pin, opgebouwd uit vaste vormen (geen transparant gaatje):
 * een ronde kop met witte rand + een puntje eronder, met een klein stipje.
 * Standaard donker met gouden stip; afgevinkt ('geweest') omgekeerd.
 */
function MapPin({ bezocht }: { bezocht: boolean }) {
  const body = bezocht ? Colors.primary : PIN_DONKER;
  const stip = bezocht ? PIN_DONKER : Colors.primary;
  return (
    <View style={styles.pinWrap}>
      <View style={[styles.pinKop, { backgroundColor: body }]}>
        <View style={[styles.pinStip, { backgroundColor: stip }]} />
      </View>
      <View style={[styles.pinPunt, { borderTopColor: body }]} />
    </View>
  );
}

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
  const { request: vraagLocatie } = useUserLocation();
  const mapRef = useRef<MapView>(null);
  const [selectedRestaurant, setSelectedRestaurant] = useState<Restaurant | null>(null);
  const [landMenuOpen, setLandMenuOpen] = useState(false);

  // Alleen restaurants met coördinaten tonen op de kaart.
  const restaurantsOpKaart = useMemo(
    () => filteredRestaurants.filter(r => r.latitude && r.longitude),
    [filteredRestaurants]
  );

  // Restaurants groeperen per land (voor het landen-menu).
  const landen = useMemo(() => {
    const map = new Map<string, LandGroep>();
    for (const r of restaurantsOpKaart) {
      const naam = bepaalLand(r.adres, r.latitude, r.longitude);
      if (!naam) continue;
      if (!map.has(naam)) {
        map.set(naam, { naam, vlag: LAND_VLAGGEN[naam] ?? '🌍', restaurants: [] });
      }
      map.get(naam)!.restaurants.push(r);
    }
    return Array.from(map.values()).sort((a, b) => b.restaurants.length - a.restaurants.length);
  }, [restaurantsOpKaart]);

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

  const handleSelectLand = (groep: LandGroep) => {
    setLandMenuOpen(false);
    setSelectedRestaurant(null);
    const coords = groep.restaurants
      .filter(r => r.latitude && r.longitude)
      .map(r => ({ latitude: r.latitude!, longitude: r.longitude! }));
    if (coords.length === 0) return;
    if (coords.length === 1) {
      mapRef.current?.animateToRegion(
        { ...coords[0], latitudeDelta: 0.05, longitudeDelta: 0.05 },
        500
      );
    } else {
      mapRef.current?.fitToCoordinates(coords, {
        edgePadding: { top: 80, right: 60, bottom: 180, left: 60 },
        animated: true,
      });
    }
  };

  const handleMyLocation = async () => {
    const c = await vraagLocatie();
    if (c) {
      mapRef.current?.animateToRegion(
        { latitude: c.latitude, longitude: c.longitude, latitudeDelta: 0.08, longitudeDelta: 0.08 },
        500
      );
    }
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
        showsMyLocationButton={false}
        showsCompass
        mapType="standard"
      >
        {restaurantsOpKaart.map(restaurant => {
          const bezocht = isVisited(restaurant.id);
          return (
            <Marker
              key={`${restaurant.id}-${bezocht ? 'v' : 'n'}`}
              coordinate={{
                latitude: restaurant.latitude!,
                longitude: restaurant.longitude!,
              }}
              anchor={{ x: 0.5, y: 1 }}
              tracksViewChanges={false}
              onPress={() => setSelectedRestaurant(restaurant)}
            >
              <MapPin bezocht={bezocht} />
            </Marker>
          );
        })}
      </MapView>

      {/* Zwevende knoppen (verspringen naar boven als de popup open is) */}
      <View style={[styles.controls, { bottom: selectedRestaurant ? 150 : 30 }]}>
        <TouchableOpacity style={styles.controlKnop} onPress={handleMyLocation} activeOpacity={0.8}>
          <Ionicons name="locate" size={22} color={Colors.primary} />
        </TouchableOpacity>
        <TouchableOpacity
          style={styles.controlKnop}
          onPress={() => setLandMenuOpen(true)}
          activeOpacity={0.8}
        >
          <Ionicons name="earth" size={22} color={Colors.primary} />
        </TouchableOpacity>
      </View>

      {/* Landen-menu */}
      <Modal
        visible={landMenuOpen}
        animationType="slide"
        presentationStyle="pageSheet"
        onRequestClose={() => setLandMenuOpen(false)}
      >
        <View style={styles.landModal}>
          <View style={styles.landHeader}>
            <Text style={styles.landTitel}>Landen</Text>
            <TouchableOpacity onPress={() => setLandMenuOpen(false)}>
              <Ionicons name="close" size={26} color={Colors.text} />
            </TouchableOpacity>
          </View>
          <FlatList
            data={landen}
            keyExtractor={item => item.naam}
            renderItem={({ item }) => (
              <TouchableOpacity
                style={styles.landRij}
                onPress={() => handleSelectLand(item)}
                activeOpacity={0.7}
              >
                <Text style={styles.landVlag}>{item.vlag}</Text>
                <Text style={styles.landNaam}>{item.naam}</Text>
                <Text style={styles.landAantal}>{item.restaurants.length}</Text>
                <Ionicons name="chevron-forward" size={18} color={Colors.textLight} />
              </TouchableOpacity>
            )}
            ListEmptyComponent={
              <Text style={styles.landLeeg}>Landen worden geladen...</Text>
            }
          />
        </View>
      </Modal>

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
  pinWrap: {
    width: 28,
    alignItems: 'center',
  },
  pinKop: {
    width: 24,
    height: 24,
    borderRadius: 12,
    alignItems: 'center',
    justifyContent: 'center',
    ...Shadow.sm,
  },
  pinStip: {
    width: 8,
    height: 8,
    borderRadius: 4,
  },
  pinPunt: {
    width: 0,
    height: 0,
    marginTop: -3,
    borderLeftWidth: 6,
    borderRightWidth: 6,
    borderTopWidth: 10,
    borderLeftColor: 'transparent',
    borderRightColor: 'transparent',
  },
  controls: {
    position: 'absolute',
    right: Spacing.lg,
    gap: Spacing.md,
  },
  controlKnop: {
    width: 48,
    height: 48,
    borderRadius: BorderRadius.full,
    backgroundColor: Colors.surface,
    justifyContent: 'center',
    alignItems: 'center',
    ...Shadow.lg,
  },
  landModal: {
    flex: 1,
    backgroundColor: Colors.background,
  },
  landHeader: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    paddingHorizontal: Spacing.xl,
    paddingTop: Spacing.xl,
    paddingBottom: Spacing.lg,
  },
  landTitel: {
    fontSize: FontSize.xl,
    fontWeight: '700',
    color: Colors.text,
  },
  landRij: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: Spacing.md,
    paddingHorizontal: Spacing.xl,
    paddingVertical: Spacing.lg,
    borderBottomWidth: StyleSheet.hairlineWidth,
    borderBottomColor: Colors.border,
  },
  landVlag: {
    fontSize: 26,
  },
  landNaam: {
    flex: 1,
    fontSize: FontSize.md,
    color: Colors.text,
    fontWeight: '600',
  },
  landAantal: {
    fontSize: FontSize.sm,
    color: Colors.textLight,
    fontWeight: '600',
  },
  landLeeg: {
    textAlign: 'center',
    color: Colors.textLight,
    paddingVertical: Spacing.xxl,
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
