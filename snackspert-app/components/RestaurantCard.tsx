import React from 'react';
import {
  View,
  Text,
  Image,
  TouchableOpacity,
  StyleSheet,
} from 'react-native';
import { router } from 'expo-router';
import { Ionicons } from '@expo/vector-icons';
import { Restaurant } from '../types';
import { StarRating } from './StarRating';
import { useFavorites } from '../contexts/FavoritesContext';
import { Colors, Spacing, BorderRadius, FontSize, Shadow } from '../constants/theme';

interface RestaurantCardProps {
  restaurant: Restaurant;
  afstandKm?: number | null;
}

/** Formatteer een afstand in km netjes (bijv. "850 m" of "3,4 km"). */
function formatAfstand(km: number): string {
  if (km < 1) return `${Math.round(km * 1000)} m`;
  return `${km.toFixed(1).replace('.', ',')} km`;
}

export function RestaurantCard({ restaurant, afstandKm }: RestaurantCardProps) {
  const { isFavorite, toggleFavorite } = useFavorites();
  const favoriet = isFavorite(restaurant.id);

  const handlePress = () => {
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

  return (
    <TouchableOpacity
      style={styles.card}
      onPress={handlePress}
      activeOpacity={0.8}
    >
      {restaurant.afbeeldingUrl ? (
        <Image
          source={{ uri: restaurant.afbeeldingUrl }}
          style={styles.image}
          resizeMode="cover"
        />
      ) : (
        <View style={styles.imagePlaceholder}>
          <Text style={styles.placeholderEmoji}>🍟</Text>
        </View>
      )}

      <TouchableOpacity
        style={styles.heart}
        onPress={() => toggleFavorite(restaurant.id)}
        hitSlop={{ top: 10, bottom: 10, left: 10, right: 10 }}
        activeOpacity={0.7}
      >
        <Ionicons
          name={favoriet ? 'heart' : 'heart-outline'}
          size={22}
          color={favoriet ? Colors.error : Colors.textOnPrimary}
        />
      </TouchableOpacity>

      {afstandKm != null && (
        <View style={styles.afstandBadge}>
          <Ionicons name="location" size={12} color={Colors.textOnPrimary} />
          <Text style={styles.afstandText}>{formatAfstand(afstandKm)}</Text>
        </View>
      )}

      <View style={styles.content}>
        <Text style={styles.naam} numberOfLines={1}>
          {restaurant.naam}
        </Text>

        {restaurant.adres ? (
          <Text style={styles.adres} numberOfLines={1}>
            {restaurant.adres}
          </Text>
        ) : null}

        <View style={styles.footer}>
          <StarRating rating={restaurant.sterren} size="sm" />

          {restaurant.categorieen.length > 0 && (
            <View style={styles.tags}>
              {restaurant.categorieen.slice(0, 2).map(cat => (
                <View key={cat} style={styles.tag}>
                  <Text style={styles.tagText}>{cat}</Text>
                </View>
              ))}
              {restaurant.categorieen.length > 2 && (
                <Text style={styles.moreTag}>
                  +{restaurant.categorieen.length - 2}
                </Text>
              )}
            </View>
          )}
        </View>
      </View>
    </TouchableOpacity>
  );
}

const styles = StyleSheet.create({
  card: {
    backgroundColor: Colors.surface,
    borderRadius: BorderRadius.lg,
    marginHorizontal: Spacing.lg,
    marginVertical: Spacing.sm,
    overflow: 'hidden',
    ...Shadow.md,
  },
  image: {
    width: '100%',
    height: 160,
  },
  imagePlaceholder: {
    width: '100%',
    height: 160,
    backgroundColor: Colors.categoryBg,
    justifyContent: 'center',
    alignItems: 'center',
  },
  heart: {
    position: 'absolute',
    top: Spacing.sm,
    right: Spacing.sm,
    width: 38,
    height: 38,
    borderRadius: BorderRadius.full,
    backgroundColor: 'rgba(0,0,0,0.35)',
    justifyContent: 'center',
    alignItems: 'center',
  },
  afstandBadge: {
    position: 'absolute',
    top: Spacing.sm,
    left: Spacing.sm,
    flexDirection: 'row',
    alignItems: 'center',
    gap: 2,
    paddingHorizontal: Spacing.sm,
    paddingVertical: 3,
    borderRadius: BorderRadius.full,
    backgroundColor: 'rgba(0,0,0,0.45)',
  },
  afstandText: {
    fontSize: FontSize.xs,
    color: Colors.textOnPrimary,
    fontWeight: '600',
  },
  placeholderEmoji: {
    fontSize: 48,
  },
  content: {
    padding: Spacing.lg,
  },
  naam: {
    fontSize: FontSize.lg,
    fontWeight: '700',
    color: Colors.text,
    marginBottom: Spacing.xs,
  },
  adres: {
    fontSize: FontSize.sm,
    color: Colors.textSecondary,
    marginBottom: Spacing.sm,
  },
  footer: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginTop: Spacing.xs,
  },
  tags: {
    flexDirection: 'row',
    gap: Spacing.xs,
    alignItems: 'center',
  },
  tag: {
    backgroundColor: Colors.categoryBg,
    paddingHorizontal: Spacing.sm,
    paddingVertical: 2,
    borderRadius: BorderRadius.sm,
  },
  tagText: {
    fontSize: FontSize.xs,
    color: Colors.categoryText,
    fontWeight: '500',
  },
  moreTag: {
    fontSize: FontSize.xs,
    color: Colors.textLight,
  },
});
