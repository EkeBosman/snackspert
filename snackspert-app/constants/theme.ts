/**
 * Snackspert huisstijl - kleuren en design tokens
 */

export const Colors = {
  // Primaire kleuren
  primary: '#FF6B00',        // Snackspert oranje
  primaryLight: '#FF8F3F',
  primaryDark: '#CC5500',

  // Achtergronden
  background: '#FFF8F0',     // Warme witte achtergrond
  surface: '#FFFFFF',
  surfaceElevated: '#FFFFFF',

  // Tekst
  text: '#1A1A2E',           // Donker navy
  textSecondary: '#6B7280',
  textLight: '#9CA3AF',
  textOnPrimary: '#FFFFFF',

  // Sterren
  star: '#FFB800',
  starEmpty: '#E5E7EB',

  // Categorieën
  categoryBg: '#FFF0E0',
  categoryText: '#CC5500',
  categoryActiveBg: '#FF6B00',
  categoryActiveText: '#FFFFFF',

  // Status
  success: '#10B981',
  error: '#EF4444',

  // Overig
  border: '#E5E7EB',
  shadow: '#000000',
  mapMarker: '#FF6B00',
};

export const Spacing = {
  xs: 4,
  sm: 8,
  md: 12,
  lg: 16,
  xl: 24,
  xxl: 32,
};

export const BorderRadius = {
  sm: 8,
  md: 12,
  lg: 16,
  xl: 24,
  full: 9999,
};

export const FontSize = {
  xs: 11,
  sm: 13,
  md: 15,
  lg: 17,
  xl: 20,
  xxl: 24,
  title: 28,
};

export const Shadow = {
  sm: {
    shadowColor: Colors.shadow,
    shadowOffset: { width: 0, height: 1 },
    shadowOpacity: 0.08,
    shadowRadius: 2,
    elevation: 1,
  },
  md: {
    shadowColor: Colors.shadow,
    shadowOffset: { width: 0, height: 2 },
    shadowOpacity: 0.12,
    shadowRadius: 6,
    elevation: 3,
  },
  lg: {
    shadowColor: Colors.shadow,
    shadowOffset: { width: 0, height: 4 },
    shadowOpacity: 0.15,
    shadowRadius: 12,
    elevation: 5,
  },
};

// Alle eetcategorieën van snackspert.nl
export const FOOD_CATEGORIES = [
  'Aziatisch',
  'Bakker',
  'Broodjes',
  'Frietpatat',
  'Grieks',
  'Hamburger',
  'Hotdogs',
  'Italiaans',
  'Kroket',
  'Mexicaans',
  'Midden-Oosters',
  'Pizza',
  'Shoarma/döner',
  'Snackbar',
  'Spaans',
  'Spareribs',
  'Wraps',
] as const;

export const DIET_FILTERS = [
  'Vega',
  'Vegan',
] as const;

// Startpositie voor de kaart (centrum Nederland)
export const MAP_INITIAL_REGION = {
  latitude: 52.1326,
  longitude: 5.2913,
  latitudeDelta: 3.0,
  longitudeDelta: 3.0,
};
