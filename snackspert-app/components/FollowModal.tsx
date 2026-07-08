import React, { useEffect, useRef } from 'react';
import {
  View,
  Text,
  Modal,
  StyleSheet,
  TouchableOpacity,
  TouchableWithoutFeedback,
  Animated,
  Easing,
} from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { SOCIAL_KANALEN, VOLG_MODAL_TEKST, SocialKanaal } from '../constants/socials';
import { Colors, Spacing, BorderRadius, FontSize, Shadow } from '../constants/theme';

interface FollowModalProps {
  visible: boolean;
  onKies: (kanaal: SocialKanaal) => void;
  onDismiss: () => void;
}

export function FollowModal({ visible, onKies, onDismiss }: FollowModalProps) {
  const anim = useRef(new Animated.Value(0)).current;

  useEffect(() => {
    if (visible) {
      anim.setValue(0);
      Animated.timing(anim, {
        toValue: 1,
        duration: 240,
        easing: Easing.out(Easing.cubic),
        useNativeDriver: true,
      }).start();
    }
  }, [visible, anim]);

  const scale = anim.interpolate({ inputRange: [0, 1], outputRange: [0.92, 1] });

  return (
    <Modal visible={visible} transparent animationType="none" onRequestClose={onDismiss} statusBarTranslucent>
      <TouchableWithoutFeedback onPress={onDismiss}>
        <Animated.View style={[styles.backdrop, { opacity: anim }]} />
      </TouchableWithoutFeedback>

      <View style={styles.center} pointerEvents="box-none">
        <Animated.View style={[styles.card, { opacity: anim, transform: [{ scale }] }]}>
          <Text style={styles.titel}>{VOLG_MODAL_TEKST.titel}</Text>
          <Text style={styles.omschrijving}>{VOLG_MODAL_TEKST.omschrijving}</Text>

          <View style={styles.knoppen}>
            {SOCIAL_KANALEN.map(kanaal => {
              const donker = kanaal.stijl === 'donker';
              return (
                <TouchableOpacity
                  key={kanaal.key}
                  style={[styles.knop, donker ? styles.knopDonker : styles.knopPrimary]}
                  onPress={() => onKies(kanaal)}
                  activeOpacity={0.85}
                >
                  <Ionicons name={kanaal.icon} size={20} color={Colors.textOnPrimary} />
                  <Text style={styles.knopText}>{kanaal.label}</Text>
                </TouchableOpacity>
              );
            })}
          </View>

          <View style={styles.subregelRij}>
            <Ionicons name="restaurant" size={13} color={Colors.textLight} />
            <Text style={styles.subregel}>{VOLG_MODAL_TEKST.subregel}</Text>
          </View>

          <TouchableOpacity onPress={onDismiss} activeOpacity={0.6} style={styles.nietNuKnop}>
            <Text style={styles.nietNu}>{VOLG_MODAL_TEKST.nietNu}</Text>
          </TouchableOpacity>
        </Animated.View>
      </View>
    </Modal>
  );
}

const styles = StyleSheet.create({
  backdrop: {
    ...StyleSheet.absoluteFillObject,
    backgroundColor: 'rgba(20, 15, 8, 0.55)',
  },
  center: {
    ...StyleSheet.absoluteFillObject,
    justifyContent: 'center',
    alignItems: 'center',
    padding: Spacing.xl,
  },
  card: {
    width: '100%',
    maxWidth: 420,
    backgroundColor: Colors.surface,
    borderRadius: BorderRadius.xl,
    padding: Spacing.xl,
    ...Shadow.lg,
  },
  titel: {
    fontSize: FontSize.xxl,
    fontWeight: '800',
    color: Colors.text,
    marginBottom: Spacing.md,
  },
  omschrijving: {
    fontSize: FontSize.md,
    lineHeight: 22,
    color: Colors.textSecondary,
    marginBottom: Spacing.xl,
  },
  knoppen: {
    gap: Spacing.md,
  },
  knop: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    gap: Spacing.sm,
    paddingVertical: Spacing.lg,
    borderRadius: BorderRadius.lg,
    ...Shadow.sm,
  },
  knopPrimary: {
    backgroundColor: Colors.primary,
  },
  knopDonker: {
    backgroundColor: '#222222',
  },
  knopText: {
    fontSize: FontSize.md,
    fontWeight: '700',
    color: Colors.textOnPrimary,
  },
  subregelRij: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    gap: 5,
    marginTop: Spacing.lg,
  },
  subregel: {
    fontSize: FontSize.xs,
    color: Colors.textLight,
  },
  nietNuKnop: {
    alignSelf: 'center',
    paddingVertical: Spacing.md,
    marginTop: Spacing.xs,
  },
  nietNu: {
    fontSize: FontSize.sm,
    color: Colors.textLight,
    fontWeight: '600',
  },
});
