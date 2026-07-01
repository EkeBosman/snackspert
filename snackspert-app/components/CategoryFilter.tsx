import React from 'react';
import {
  View,
  Text,
  ScrollView,
  TouchableOpacity,
  StyleSheet,
} from 'react-native';
import { Colors, Spacing, BorderRadius, FontSize } from '../constants/theme';
import { FOOD_CATEGORIES, DIET_FILTERS } from '../constants/theme';

interface CategoryFilterProps {
  selected: string[];
  onToggle: (category: string) => void;
  beschikbaar?: string[];
}

export function CategoryFilter({ selected, onToggle, beschikbaar }: CategoryFilterProps) {
  // Gebruik beschikbare categorieën als die er zijn, anders de standaard lijst
  const categories = beschikbaar && beschikbaar.length > 0
    ? beschikbaar
    : [...FOOD_CATEGORIES, ...DIET_FILTERS];

  return (
    <ScrollView
      style={styles.scroll}
      showsVerticalScrollIndicator={false}
      contentContainerStyle={styles.container}
    >
      {categories.map(cat => {
        const isActive = selected.includes(cat);
        return (
          <TouchableOpacity
            key={cat}
            style={[styles.chip, isActive && styles.chipActive]}
            onPress={() => onToggle(cat)}
            activeOpacity={0.7}
          >
            <Text style={[styles.chipText, isActive && styles.chipTextActive]}>
              {cat}
            </Text>
          </TouchableOpacity>
        );
      })}
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  scroll: {
    maxHeight: 92,
    flexGrow: 0,
  },
  container: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    paddingHorizontal: Spacing.lg,
    paddingVertical: Spacing.xs,
    gap: Spacing.sm,
  },
  chip: {
    paddingHorizontal: Spacing.md,
    paddingVertical: Spacing.sm,
    borderRadius: BorderRadius.full,
    backgroundColor: Colors.categoryBg,
    borderWidth: 1,
    borderColor: 'transparent',
  },
  chipActive: {
    backgroundColor: Colors.categoryActiveBg,
    borderColor: Colors.primaryDark,
  },
  chipText: {
    fontSize: FontSize.sm,
    color: Colors.categoryText,
    fontWeight: '500',
  },
  chipTextActive: {
    color: Colors.categoryActiveText,
    fontWeight: '600',
  },
});
