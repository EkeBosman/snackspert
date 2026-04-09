import React from 'react';
import { View, Text, StyleSheet } from 'react-native';
import { Colors, FontSize, Spacing } from '../constants/theme';

interface StarRatingProps {
  rating: number;
  maxStars?: number;
  size?: 'sm' | 'md' | 'lg';
  showNumber?: boolean;
}

export function StarRating({ rating, maxStars = 5, size = 'md', showNumber = true }: StarRatingProps) {
  const starSize = size === 'sm' ? 14 : size === 'md' ? 18 : 24;
  const fontSize = size === 'sm' ? FontSize.xs : size === 'md' ? FontSize.sm : FontSize.lg;

  const stars = [];
  for (let i = 1; i <= maxStars; i++) {
    if (i <= Math.floor(rating)) {
      stars.push('★');
    } else if (i - 0.5 <= rating) {
      stars.push('½');
    } else {
      stars.push('☆');
    }
  }

  if (rating === 0) {
    return (
      <Text style={[styles.noRating, { fontSize }]}>Geen beoordeling</Text>
    );
  }

  return (
    <View style={styles.container}>
      <Text style={{ fontSize: starSize }}>
        {stars.map((star, i) => (
          <Text
            key={i}
            style={{ color: star === '☆' ? Colors.starEmpty : Colors.star }}
          >
            {star}
          </Text>
        ))}
      </Text>
      {showNumber && (
        <Text style={[styles.number, { fontSize }]}>{rating}/5</Text>
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
  number: {
    color: Colors.textSecondary,
    marginLeft: Spacing.xs,
  },
  noRating: {
    color: Colors.textLight,
    fontStyle: 'italic',
  },
});
