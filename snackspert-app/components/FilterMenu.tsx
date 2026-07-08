import React, { useState } from 'react';
import {
  View,
  Text,
  TouchableOpacity,
  StyleSheet,
  Modal,
  ScrollView,
} from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { FilterState } from '../types';
import { useEngagement } from '../contexts/EngagementContext';
import { FOOD_CATEGORIES, DIET_FILTERS, Colors, Spacing, BorderRadius, FontSize, Shadow } from '../constants/theme';

const ALL_CATEGORIES = [...FOOD_CATEGORIES, ...DIET_FILTERS];
const STER_OPTIES = [
  { label: 'Alles', waarde: 0 },
  { label: '⭐ 4+', waarde: 4 },
  { label: '⭐ 5', waarde: 5 },
];

interface FilterMenuProps {
  filters: FilterState;
  setFilters: (f: FilterState) => void;
  beschikbareCategorieen?: string[];
}

export function FilterMenu({ filters, setFilters, beschikbareCategorieen }: FilterMenuProps) {
  const [open, setOpen] = useState(false);
  const { markActie } = useEngagement();

  const categorieen =
    beschikbareCategorieen && beschikbareCategorieen.length > 0
      ? beschikbareCategorieen
      : ALL_CATEGORIES;

  const actief = filters.categorieen.length + (filters.minimumSterren > 0 ? 1 : 0);

  const toggleCategorie = (cat: string) => {
    const nieuw = filters.categorieen.includes(cat)
      ? filters.categorieen.filter(c => c !== cat)
      : [...filters.categorieen, cat];
    setFilters({ ...filters, categorieen: nieuw });
    markActie();
  };

  const zetSterren = (waarde: number) => {
    setFilters({ ...filters, minimumSterren: waarde });
    markActie();
  };

  const wissen = () => {
    setFilters({ ...filters, categorieen: [], minimumSterren: 0 });
  };

  return (
    <>
      <TouchableOpacity
        style={[styles.knop, actief > 0 && styles.knopActief]}
        onPress={() => setOpen(true)}
        activeOpacity={0.7}
      >
        <Ionicons
          name="options-outline"
          size={16}
          color={actief > 0 ? Colors.textOnPrimary : Colors.categoryText}
        />
        <Text style={[styles.knopText, actief > 0 && styles.knopTextActief]}>Filter</Text>
        {actief > 0 && (
          <View style={styles.badge}>
            <Text style={styles.badgeText}>{actief}</Text>
          </View>
        )}
      </TouchableOpacity>

      <Modal
        visible={open}
        animationType="slide"
        presentationStyle="pageSheet"
        onRequestClose={() => setOpen(false)}
      >
        <View style={styles.modal}>
          <View style={styles.header}>
            <Text style={styles.titel}>Filter</Text>
            <TouchableOpacity onPress={() => setOpen(false)}>
              <Ionicons name="close" size={26} color={Colors.text} />
            </TouchableOpacity>
          </View>

          <ScrollView contentContainerStyle={styles.body}>
            {/* Beoordeling */}
            <Text style={styles.sectie}>Beoordeling</Text>
            <View style={styles.rij}>
              {STER_OPTIES.map(opt => {
                const isActief = filters.minimumSterren === opt.waarde;
                return (
                  <TouchableOpacity
                    key={opt.waarde}
                    style={[styles.chip, isActief && styles.chipActief]}
                    onPress={() => zetSterren(opt.waarde)}
                    activeOpacity={0.7}
                  >
                    <Text style={[styles.chipText, isActief && styles.chipTextActief]}>
                      {opt.label}
                    </Text>
                  </TouchableOpacity>
                );
              })}
            </View>

            {/* Categorieën */}
            <Text style={[styles.sectie, { marginTop: Spacing.xl }]}>Categorie</Text>
            <View style={styles.rijWrap}>
              {categorieen.map(cat => {
                const isActief = filters.categorieen.includes(cat);
                return (
                  <TouchableOpacity
                    key={cat}
                    style={[styles.chip, isActief && styles.chipActief]}
                    onPress={() => toggleCategorie(cat)}
                    activeOpacity={0.7}
                  >
                    <Text style={[styles.chipText, isActief && styles.chipTextActief]}>
                      {cat}
                    </Text>
                  </TouchableOpacity>
                );
              })}
            </View>
          </ScrollView>

          <View style={styles.voet}>
            <TouchableOpacity style={styles.wisKnop} onPress={wissen} activeOpacity={0.7}>
              <Text style={styles.wisText}>Wissen</Text>
            </TouchableOpacity>
            <TouchableOpacity
              style={styles.klaarKnop}
              onPress={() => setOpen(false)}
              activeOpacity={0.8}
            >
              <Text style={styles.klaarText}>Toon resultaten</Text>
            </TouchableOpacity>
          </View>
        </View>
      </Modal>
    </>
  );
}

const styles = StyleSheet.create({
  knop: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: Spacing.xs,
    paddingHorizontal: Spacing.md,
    paddingVertical: Spacing.sm,
    borderRadius: BorderRadius.full,
    backgroundColor: Colors.categoryBg,
  },
  knopActief: {
    backgroundColor: Colors.primary,
  },
  knopText: {
    fontSize: FontSize.sm,
    color: Colors.categoryText,
    fontWeight: '600',
  },
  knopTextActief: {
    color: Colors.textOnPrimary,
  },
  badge: {
    minWidth: 18,
    height: 18,
    borderRadius: 9,
    backgroundColor: '#FFFFFF',
    justifyContent: 'center',
    alignItems: 'center',
    paddingHorizontal: 4,
  },
  badgeText: {
    fontSize: 11,
    fontWeight: '800',
    color: Colors.primary,
  },
  modal: {
    flex: 1,
    backgroundColor: Colors.background,
  },
  header: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    paddingHorizontal: Spacing.xl,
    paddingTop: Spacing.xl,
    paddingBottom: Spacing.lg,
  },
  titel: {
    fontSize: FontSize.xl,
    fontWeight: '700',
    color: Colors.text,
  },
  body: {
    paddingHorizontal: Spacing.xl,
    paddingBottom: Spacing.xl,
  },
  sectie: {
    fontSize: FontSize.md,
    fontWeight: '700',
    color: Colors.text,
    marginBottom: Spacing.md,
  },
  rij: {
    flexDirection: 'row',
    gap: Spacing.sm,
  },
  rijWrap: {
    flexDirection: 'row',
    flexWrap: 'wrap',
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
  chipActief: {
    backgroundColor: Colors.primary,
    borderColor: Colors.primaryDark,
  },
  chipText: {
    fontSize: FontSize.sm,
    color: Colors.categoryText,
    fontWeight: '600',
  },
  chipTextActief: {
    color: Colors.textOnPrimary,
  },
  voet: {
    flexDirection: 'row',
    gap: Spacing.md,
    paddingHorizontal: Spacing.xl,
    paddingTop: Spacing.md,
    paddingBottom: Spacing.xxl,
    borderTopWidth: StyleSheet.hairlineWidth,
    borderTopColor: Colors.border,
  },
  wisKnop: {
    paddingHorizontal: Spacing.xl,
    paddingVertical: Spacing.lg,
    borderRadius: BorderRadius.lg,
    backgroundColor: Colors.surface,
    borderWidth: 2,
    borderColor: Colors.border,
    justifyContent: 'center',
  },
  wisText: {
    fontSize: FontSize.md,
    fontWeight: '700',
    color: Colors.textSecondary,
  },
  klaarKnop: {
    flex: 1,
    paddingVertical: Spacing.lg,
    borderRadius: BorderRadius.lg,
    backgroundColor: Colors.primary,
    alignItems: 'center',
    justifyContent: 'center',
    ...Shadow.md,
  },
  klaarText: {
    fontSize: FontSize.md,
    fontWeight: '700',
    color: Colors.textOnPrimary,
  },
});
