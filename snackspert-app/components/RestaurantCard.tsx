import React from 'react';
import {
  View,
  Text,
  Image,
  TouchableOpacity,
  StyleSheet,
} from 'react-native';
import { router } from 'expo-router';
import { Restaurant } from '../types';
import { StarRating } from './StarRating';
import { Colors, Spacing, BorderRadius, FontSize, Shadow } from '../constants/theme';

interface RestaurantCardProps {
  restaurant: Restaurant;
}

export function RestaurantCard({ restaurant }: RestaurantCardProps) {
  const handlePress = () => {
    router.push({
      pathname: '/restaurant/[id]',
      params: { id: restaurant.id.toString() },
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
