import React, { useState, useMemo } from 'react';
import {
  View,
  Text,
  TextInput,
  FlatList,
  TouchableOpacity,
  StyleSheet,
  Modal,
} from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { Colors, Spacing, BorderRadius, FontSize, Shadow } from '../constants/theme';

interface LocationFilterProps {
  value: string;
  onSelect: (locatie: string) => void;
  beschikbareSteden: string[];
}

export function LocationFilter({ value, onSelect, beschikbareSteden }: LocationFilterProps) {
  const [modalVisible, setModalVisible] = useState(false);
  const [zoekterm, setZoekterm] = useState('');

  const gefilterdeSteden = useMemo(() => {
    if (!zoekterm) return beschikbareSteden;
    const term = zoekterm.toLowerCase();
    return beschikbareSteden.filter(s => s.toLowerCase().includes(term));
  }, [beschikbareSteden, zoekterm]);

  const handleSelect = (stad: string) => {
    onSelect(stad);
    setModalVisible(false);
    setZoekterm('');
  };

  const handleClear = () => {
    onSelect('');
    setModalVisible(false);
    setZoekterm('');
  };

  return (
    <>
      <TouchableOpacity
        style={[styles.filterButton, value ? styles.filterButtonActive : null]}
        onPress={() => setModalVisible(true)}
        activeOpacity={0.7}
      >
        <Ionicons
          name="location-outline"
          size={16}
          color={value ? Colors.textOnPrimary : Colors.categoryText}
        />
        <Text style={[styles.filterText, value ? styles.filterTextActive : null]}>
          {value || 'Locatie'}
        </Text>
        {value ? (
          <TouchableOpacity onPress={handleClear} hitSlop={{ top: 8, bottom: 8, left: 8, right: 8 }}>
            <Ionicons name="close-circle" size={16} color={Colors.textOnPrimary} />
          </TouchableOpacity>
        ) : (
          <Ionicons
            name="chevron-down"
            size={14}
            color={Colors.categoryText}
          />
        )}
      </TouchableOpacity>

      <Modal
        visible={modalVisible}
        animationType="slide"
        presentationStyle="pageSheet"
        onRequestClose={() => setModalVisible(false)}
      >
        <View style={styles.modal}>
          <View style={styles.modalHeader}>
            <Text style={styles.modalTitle}>Kies een locatie</Text>
            <TouchableOpacity onPress={() => setModalVisible(false)}>
              <Ionicons name="close" size={24} color={Colors.text} />
            </TouchableOpacity>
          </View>

          <View style={styles.modalSearch}>
            <Ionicons name="search" size={18} color={Colors.textLight} />
            <TextInput
              style={styles.modalSearchInput}
              placeholder="Zoek stad of plaats..."
              placeholderTextColor={Colors.textLight}
              value={zoekterm}
              onChangeText={setZoekterm}
              autoFocus
              autoCapitalize="words"
              clearButtonMode="while-editing"
            />
          </View>

          {value ? (
            <TouchableOpacity style={styles.clearRow} onPress={handleClear}>
              <Ionicons name="close-circle-outline" size={20} color={Colors.error} />
              <Text style={styles.clearText}>Filter wissen</Text>
            </TouchableOpacity>
          ) : null}

          <FlatList
            data={gefilterdeSteden}
            keyExtractor={item => item}
            renderItem={({ item }) => (
              <TouchableOpacity
                style={[styles.stadRow, item === value && styles.stadRowActive]}
                onPress={() => handleSelect(item)}
              >
                <Ionicons
                  name="location"
                  size={18}
                  color={item === value ? Colors.primary : Colors.textLight}
                />
                <Text style={[styles.stadText, item === value && styles.stadTextActive]}>
                  {item}
                </Text>
              </TouchableOpacity>
            )}
            ListEmptyComponent={
              <Text style={styles.emptyText}>
                {beschikbareSteden.length === 0
                  ? 'Locaties worden geladen...'
                  : 'Geen locaties gevonden'}
              </Text>
            }
          />
        </View>
      </Modal>
    </>
  );
}

const styles = StyleSheet.create({
  filterButton: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: Spacing.xs,
    paddingHorizontal: Spacing.md,
    paddingVertical: Spacing.sm,
    borderRadius: BorderRadius.full,
    backgroundColor: Colors.categoryBg,
  },
  filterButtonActive: {
    backgroundColor: Colors.primary,
  },
  filterText: {
    fontSize: FontSize.sm,
    color: Colors.categoryText,
    fontWeight: '500',
  },
  filterTextActive: {
    color: Colors.textOnPrimary,
    fontWeight: '600',
  },
  modal: {
    flex: 1,
    backgroundColor: Colors.background,
  },
  modalHeader: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    paddingHorizontal: Spacing.xl,
    paddingTop: Spacing.xl,
    paddingBottom: Spacing.lg,
  },
  modalTitle: {
    fontSize: FontSize.xl,
    fontWeight: '700',
    color: Colors.text,
  },
  modalSearch: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: Colors.surface,
    marginHorizontal: Spacing.xl,
    marginBottom: Spacing.lg,
    paddingHorizontal: Spacing.lg,
    paddingVertical: Spacing.md,
    borderRadius: BorderRadius.lg,
    gap: Spacing.sm,
    borderWidth: 1,
    borderColor: Colors.border,
    ...Shadow.sm,
  },
  modalSearchInput: {
    flex: 1,
    fontSize: FontSize.md,
    color: Colors.text,
  },
  clearRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: Spacing.sm,
    paddingHorizontal: Spacing.xl,
    paddingVertical: Spacing.md,
    borderBottomWidth: 1,
    borderBottomColor: Colors.border,
  },
  clearText: {
    fontSize: FontSize.md,
    color: Colors.error,
    fontWeight: '500',
  },
  stadRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: Spacing.md,
    paddingHorizontal: Spacing.xl,
    paddingVertical: Spacing.lg,
    borderBottomWidth: StyleSheet.hairlineWidth,
    borderBottomColor: Colors.border,
  },
  stadRowActive: {
    backgroundColor: Colors.categoryBg,
  },
  stadText: {
    fontSize: FontSize.md,
    color: Colors.text,
  },
  stadTextActive: {
    color: Colors.primary,
    fontWeight: '600',
  },
  emptyText: {
    textAlign: 'center',
    color: Colors.textLight,
    fontSize: FontSize.md,
    paddingVertical: Spacing.xxl,
  },
});
