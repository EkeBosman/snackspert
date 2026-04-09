import React, { useEffect, useState } from 'react';
import {
  View,
  Text,
  Image,
  ScrollView,
  StyleSheet,
  ActivityIndicator,
  Linking,
  TouchableOpacity,
  Dimensions,
} from 'react-native';
import { useLocalSearchParams, Stack } from 'expo-router';
import MapView, { Marker } from 'react-native-maps';
import { Restaurant } from '../../types';
import { fetchRestaurantDetail } from '../../services/api';
import { StarRating } from '../../components/StarRating';
import { Colors, Spacing, BorderRadius, FontSize, Shadow } from '../../constants/theme';

const { width: SCREEN_WIDTH } = Dimensions.get('window');

export default function RestaurantDetailScreen() {
  const { id } = useLocalSearchParams<{ id: string }>();
  const [restaurant, setRestaurant] = useState<Restaurant | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    loadDetail();
  }, [id]);

  async function loadDetail() {
    setIsLoading(true);
    try {
      // Haal eerst de basis-URL op via de WP REST API
      const resp = await fetch(
        `https://snackspert.nl/wp-json/wp/v2/restaurant/${id}`
      );
      if (!resp.ok) throw new Error('Restaurant niet gevonden');

      const wpData = await resp.json();
      const paginaUrl = wpData.link;

      // Scrape de detailpagina
      const detail = await fetchRestaurantDetail(paginaUrl);

      setRestaurant({
        id: parseInt(id!, 10),
        naam: detail.naam || wpData.title.rendered,
        slug: wpData.slug,
        adres: detail.adres || '',
        tekst: detail.tekst || '',
        sterren: detail.sterren || 0,
        sterrenTekst: detail.sterrenTekst || '',
        afbeeldingUrl: detail.afbeeldingUrl || '',
        paginaUrl,
        categorieen: detail.categorieen || [],
        latitude: detail.latitude || null,
        longitude: detail.longitude || null,
      });
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Kon restaurant niet laden');
    } finally {
      setIsLoading(false);
    }
  }

  const openWebsite = () => {
    if (restaurant?.paginaUrl) {
      Linking.openURL(restaurant.paginaUrl);
    }
  };

  const openMaps = () => {
    if (restaurant?.latitude && restaurant?.longitude) {
      const url = `https://maps.apple.com/?q=${encodeURIComponent(restaurant.naam)}&ll=${restaurant.latitude},${restaurant.longitude}`;
      Linking.openURL(url);
    } else if (restaurant?.adres) {
      const url = `https://maps.apple.com/?q=${encodeURIComponent(restaurant.adres)}`;
      Linking.openURL(url);
    }
  };

  if (isLoading) {
    return (
      <View style={styles.loadingContainer}>
        <ActivityIndicator size="large" color={Colors.primary} />
        <Text style={styles.loadingText}>Restaurant laden...</Text>
      </View>
    );
  }

  if (error || !restaurant) {
    return (
      <View style={styles.errorContainer}>
        <Text style={styles.errorEmoji}>😕</Text>
        <Text style={styles.errorText}>{error || 'Restaurant niet gevonden'}</Text>
      </View>
    );
  }

  return (
    <>
      <Stack.Screen options={{ title: restaurant.naam }} />
      <ScrollView style={styles.container} bounces={false}>
        {/* Hero afbeelding */}
        {restaurant.afbeeldingUrl ? (
          <Image
            source={{ uri: restaurant.afbeeldingUrl }}
            style={styles.heroImage}
            resizeMode="cover"
          />
        ) : (
          <View style={styles.heroPlaceholder}>
            <Text style={styles.heroEmoji}>🍟</Text>
          </View>
        )}

        {/* Content */}
        <View style={styles.content}>
          {/* Naam en beoordeling */}
          <Text style={styles.naam}>{restaurant.naam}</Text>
          <View style={styles.ratingRow}>
            <StarRating rating={restaurant.sterren} size="lg" />
          </View>

          {/* Categorieën */}
          {restaurant.categorieen.length > 0 && (
            <View style={styles.categories}>
              {restaurant.categorieen.map(cat => (
                <View key={cat} style={styles.categoryChip}>
                  <Text style={styles.categoryText}>{cat}</Text>
                </View>
              ))}
            </View>
          )}

          {/* Adres */}
          {restaurant.adres ? (
            <TouchableOpacity onPress={openMaps} activeOpacity={0.7}>
              <View style={styles.infoCard}>
                <Text style={styles.infoLabel}>Adres</Text>
                <Text style={styles.infoValue}>{restaurant.adres}</Text>
                <Text style={styles.infoAction}>Open in Kaarten →</Text>
              </View>
            </TouchableOpacity>
          ) : null}

          {/* Mini-kaart */}
          {restaurant.latitude && restaurant.longitude && (
            <TouchableOpacity onPress={openMaps} activeOpacity={0.9}>
              <View style={styles.miniMapContainer}>
                <MapView
                  style={styles.miniMap}
                  initialRegion={{
                    latitude: restaurant.latitude,
                    longitude: restaurant.longitude,
                    latitudeDelta: 0.01,
                    longitudeDelta: 0.01,
                  }}
                  scrollEnabled={false}
                  zoomEnabled={false}
                  rotateEnabled={false}
                  pitchEnabled={false}
                >
                  <Marker
                    coordinate={{
                      latitude: restaurant.latitude,
                      longitude: restaurant.longitude,
                    }}
                    pinColor={Colors.mapMarker}
                  />
                </MapView>
              </View>
            </TouchableOpacity>
          )}

          {/* Recensie */}
          {restaurant.tekst ? (
            <View style={styles.reviewSection}>
              <Text style={styles.sectionTitle}>Recensie</Text>
              <Text style={styles.reviewText}>{restaurant.tekst}</Text>
            </View>
          ) : null}

          {/* Knoppen */}
          <View style={styles.actions}>
            <TouchableOpacity
              style={styles.primaryButton}
              onPress={openWebsite}
              activeOpacity={0.8}
            >
              <Text style={styles.primaryButtonText}>
                Bekijk op Snackspert.nl
              </Text>
            </TouchableOpacity>

            {(restaurant.adres || restaurant.latitude) && (
              <TouchableOpacity
                style={styles.secondaryButton}
                onPress={openMaps}
                activeOpacity={0.8}
              >
                <Text style={styles.secondaryButtonText}>
                  Navigeer erheen
                </Text>
              </TouchableOpacity>
            )}
          </View>
        </View>
      </ScrollView>
    </>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: Colors.background,
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
  errorContainer: {
    flex: 1,
    justifyContent: 'center',
    alignItems: 'center',
    backgroundColor: Colors.background,
    gap: Spacing.md,
    padding: Spacing.xl,
  },
  errorEmoji: {
    fontSize: 48,
  },
  errorText: {
    fontSize: FontSize.lg,
    color: Colors.textSecondary,
    textAlign: 'center',
  },
  heroImage: {
    width: SCREEN_WIDTH,
    height: 250,
  },
  heroPlaceholder: {
    width: SCREEN_WIDTH,
    height: 200,
    backgroundColor: Colors.categoryBg,
    justifyContent: 'center',
    alignItems: 'center',
  },
  heroEmoji: {
    fontSize: 64,
  },
  content: {
    padding: Spacing.xl,
    gap: Spacing.lg,
  },
  naam: {
    fontSize: FontSize.title,
    fontWeight: '800',
    color: Colors.text,
  },
  ratingRow: {
    flexDirection: 'row',
    alignItems: 'center',
  },
  categories: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    gap: Spacing.sm,
  },
  categoryChip: {
    backgroundColor: Colors.categoryBg,
    paddingHorizontal: Spacing.md,
    paddingVertical: Spacing.xs,
    borderRadius: BorderRadius.full,
  },
  categoryText: {
    fontSize: FontSize.sm,
    color: Colors.categoryText,
    fontWeight: '600',
  },
  infoCard: {
    backgroundColor: Colors.surface,
    borderRadius: BorderRadius.md,
    padding: Spacing.lg,
    ...Shadow.sm,
  },
  infoLabel: {
    fontSize: FontSize.xs,
    color: Colors.textLight,
    fontWeight: '600',
    textTransform: 'uppercase',
    letterSpacing: 0.5,
    marginBottom: Spacing.xs,
  },
  infoValue: {
    fontSize: FontSize.md,
    color: Colors.text,
    lineHeight: 22,
  },
  infoAction: {
    fontSize: FontSize.sm,
    color: Colors.primary,
    fontWeight: '600',
    marginTop: Spacing.sm,
  },
  miniMapContainer: {
    borderRadius: BorderRadius.lg,
    overflow: 'hidden',
    ...Shadow.md,
  },
  miniMap: {
    width: '100%',
    height: 160,
  },
  reviewSection: {
    gap: Spacing.sm,
  },
  sectionTitle: {
    fontSize: FontSize.xl,
    fontWeight: '700',
    color: Colors.text,
  },
  reviewText: {
    fontSize: FontSize.md,
    color: Colors.text,
    lineHeight: 24,
  },
  actions: {
    gap: Spacing.md,
    marginTop: Spacing.lg,
    marginBottom: Spacing.xxl,
  },
  primaryButton: {
    backgroundColor: Colors.primary,
    borderRadius: BorderRadius.lg,
    paddingVertical: Spacing.lg,
    alignItems: 'center',
    ...Shadow.md,
  },
  primaryButtonText: {
    fontSize: FontSize.lg,
    fontWeight: '700',
    color: Colors.textOnPrimary,
  },
  secondaryButton: {
    backgroundColor: Colors.surface,
    borderRadius: BorderRadius.lg,
    paddingVertical: Spacing.lg,
    alignItems: 'center',
    borderWidth: 2,
    borderColor: Colors.primary,
  },
  secondaryButtonText: {
    fontSize: FontSize.lg,
    fontWeight: '700',
    color: Colors.primary,
  },
});
