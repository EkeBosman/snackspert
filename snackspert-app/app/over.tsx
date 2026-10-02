import React from 'react';
import {
  View,
  Text,
  Image,
  ScrollView,
  TouchableOpacity,
  StyleSheet,
  Linking,
} from 'react-native';
import { Stack } from 'expo-router';
import { Ionicons } from '@expo/vector-icons';
import {
  SOCIAL_KANALEN,
  WEBSITE_URL,
  PRIVACY_URL,
  openSocialKanaal,
} from '../constants/socials';
import { Colors, Spacing, BorderRadius, FontSize, Shadow } from '../constants/theme';

export default function OverScreen() {
  return (
    <>
      <Stack.Screen options={{ title: 'Over Snackspert', headerBackTitle: 'Terug' }} />
      <ScrollView style={styles.container} contentContainerStyle={styles.content}>
        <View style={styles.logoVak}>
          <Image
            source={require('../assets/SNACKSPERT_LOGO_SB_PIXEL.png')}
            style={styles.logo}
            resizeMode="contain"
          />
        </View>

        <Text style={styles.intro}>
          Snackspert is een onafhankelijke gids voor snackbars, cafetaria's en alles
          daartussenin. Alle recensies in deze app zijn zelf getest en geschreven —
          geen advertenties, geen gesponsorde plekken.
        </Text>

        <View style={styles.statVak}>
          <Text style={styles.statGetal}>750+</Text>
          <Text style={styles.statLabel}>snackreviews verzameld</Text>
        </View>

        {/* Volgen */}
        <Text style={styles.sectie}>Volg Snackspert</Text>
        <Text style={styles.sectieTekst}>
          Op Instagram en TikTok verschijnen vrijwel dagelijks nieuwe reviews,
          smaaktests en lijstjes.
        </Text>
        <View style={styles.knoppen}>
          {SOCIAL_KANALEN.map(kanaal => {
            const donker = kanaal.stijl === 'donker';
            return (
              <TouchableOpacity
                key={kanaal.key}
                style={[styles.knop, donker ? styles.knopDonker : styles.knopPrimary]}
                onPress={() => openSocialKanaal(kanaal)}
                activeOpacity={0.85}
              >
                <Ionicons name={kanaal.icon} size={20} color={Colors.textOnPrimary} />
                <Text style={styles.knopText}>{kanaal.label}</Text>
              </TouchableOpacity>
            );
          })}
        </View>

        {/* Links */}
        <Text style={[styles.sectie, { marginTop: Spacing.xl }]}>Meer</Text>
        <TouchableOpacity
          style={styles.rij}
          onPress={() => Linking.openURL(WEBSITE_URL)}
          activeOpacity={0.7}
        >
          <Ionicons name="globe-outline" size={20} color={Colors.primary} />
          <Text style={styles.rijText}>snackspert.nl</Text>
          <Ionicons name="open-outline" size={16} color={Colors.textLight} />
        </TouchableOpacity>
        <TouchableOpacity
          style={styles.rij}
          onPress={() => Linking.openURL(PRIVACY_URL)}
          activeOpacity={0.7}
        >
          <Ionicons name="lock-closed-outline" size={20} color={Colors.primary} />
          <Text style={styles.rijText}>Privacyverklaring</Text>
          <Ionicons name="open-outline" size={16} color={Colors.textLight} />
        </TouchableOpacity>

        <Text style={styles.voet}>
          Deze app verzamelt geen persoonsgegevens. Je favorieten en afgevinkte
          plekken blijven op je eigen toestel.
        </Text>
      </ScrollView>
    </>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: Colors.background,
  },
  content: {
    padding: Spacing.xl,
    paddingBottom: Spacing.xxl,
  },
  logoVak: {
    backgroundColor: '#1A1512',
    borderRadius: BorderRadius.lg,
    paddingVertical: Spacing.xl,
    alignItems: 'center',
    marginBottom: Spacing.xl,
    ...Shadow.sm,
  },
  logo: {
    width: '80%',
    height: 56,
  },
  intro: {
    fontSize: FontSize.md,
    lineHeight: 23,
    color: Colors.textSecondary,
  },
  statVak: {
    alignItems: 'center',
    backgroundColor: Colors.categoryBg,
    borderRadius: BorderRadius.lg,
    paddingVertical: Spacing.lg,
    marginTop: Spacing.xl,
  },
  statGetal: {
    fontSize: FontSize.title,
    fontWeight: '800',
    color: Colors.categoryText,
  },
  statLabel: {
    fontSize: FontSize.sm,
    color: Colors.categoryText,
  },
  sectie: {
    fontSize: FontSize.lg,
    fontWeight: '700',
    color: Colors.text,
    marginTop: Spacing.xxl,
    marginBottom: Spacing.xs,
  },
  sectieTekst: {
    fontSize: FontSize.sm,
    color: Colors.textSecondary,
    lineHeight: 20,
    marginBottom: Spacing.lg,
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
  rij: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: Spacing.md,
    backgroundColor: Colors.surface,
    borderRadius: BorderRadius.md,
    paddingHorizontal: Spacing.lg,
    paddingVertical: Spacing.lg,
    marginBottom: Spacing.sm,
    ...Shadow.sm,
  },
  rijText: {
    flex: 1,
    fontSize: FontSize.md,
    color: Colors.text,
    fontWeight: '600',
  },
  voet: {
    fontSize: FontSize.xs,
    color: Colors.textLight,
    lineHeight: 18,
    marginTop: Spacing.xl,
    textAlign: 'center',
  },
});
