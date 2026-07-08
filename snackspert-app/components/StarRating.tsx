import React from 'react';
import { View, Text, StyleSheet } from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { Colors, FontSize, Spacing } from '../constants/theme';

interface StarRatingProps {
  rating: number;
  maxStars?: number;
  size?: 'sm' | 'md' | 'lg';
  showNumber?: boolean;
}

export function StarRating({ rating, maxStars = 5, size = 'md', showNumber = true }: StarRatingProps) {
  const starSize = size === 'sm' ? 15 : size === 'md' ? 18 : 24;
  const fontSize = size === 'sm' ? FontSize.xs : size === 'md' ? FontSize.sm : FontSize.lg;

  if (rating === 0) {
    return <Text style={[styles.noRating, { fontSize }]}>Geen beoordeling</Text>;
  }

  // Per positie bepalen: vol, half of leeg.
  const icons: Array<'star' | 'star-half' | 'star-outline'> = [];
  for (let i = 1; i <= maxStars; i++) {
    if (i <= Math.floor(rating)) {
      icons.push('star');
    } else if (i - 0.5 <= rating) {
      icons.push('star-half');
    } else {
      icons.push('star-outline');
    }
  }

  return (
    <View style={styles.container}>
      <View style={styles.stars}>
        {icons.map((naam, i) => (
          <Ionicons
            key={i}
            name={naam}
            size={starSize}
            color={naam === 'star-outline' ? Colors.starEmpty : Colors.star}
          />
        ))}
      </View>
      {showNumber && (
        <Text style={[styles.number, { fontSize }]}>
          {rating.toString().replace('.', ',')}/{maxStars}
        </Text>
      )}
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: Spacing.xs,
  },
  stars: {
    flexDirection: 'row',
  },
  number: {
    color: Colors.textSecondary,
    marginLeft: Spacing.xs,
  },
  noRating: {
    color: Colors.textLight,
    fontStyle: 'italic',
  },
});
