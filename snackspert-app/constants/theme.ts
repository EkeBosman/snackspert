/**
 * Snackspert huisstijl - kleuren en design tokens
 */

export const Colors = {
  // Primaire kleuren (Snackspert huisstijl - warm goud/amber)
  primary: '#EDAA2D',        // Snackspert goud
  primaryLight: '#F2BD55',
  primaryDark: '#D4921A',

  // Achtergronden
  background: '#FFFBF2',     // Warme crème achtergrond
  surface: '#FFFFFF',
  surfaceElevated: '#FFFFFF',

  // Tekst
  text: '#2D2013',           // Donker warm bruin
  textSecondary: '#6B5D4F',
  textLight: '#9C8E80',
  textOnPrimary: '#FFFFFF',

  // Sterren
  star: '#EDAA2D',
  starEmpty: '#E5E0D8',

  // Categorieën
  categoryBg: '#FFF3DC',
  categoryText: '#A67612',
  categoryActiveBg: '#EDAA2D',
  categoryActiveText: '#FFFFFF',

  // Status
  success: '#10B981',
  error: '#EF4444',

  // Overig
  border: '#E8E0D5',
  shadow: '#000000',
  mapMarker: '#EDAA2D',
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
// De categorie-labels zoals ze daadwerkelijk op snackspert.nl staan.
// Dit is alleen de terugvaloptie: zodra de recensies geladen zijn gebruikt de
// app de categorieën die echt in de data voorkomen.
export const FOOD_CATEGORIES = [
  'Aziatisch',
  'Bakker',
  'Borrel',
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
  'Overig',
] as const;

// Label dat op de site als categorie meekomt maar een beoordeling is; dat
// filteren we eruit, want daar is het aparte sterrenfilter voor.
export const GEEN_CATEGORIE_LABELS = ['5 sterren'];

// Startpositie voor de kaart (centrum Nederland)
export const MAP_INITIAL_REGION = {
  latitude: 52.1326,
  longitude: 5.2913,
  latitudeDelta: 3.0,
  longitudeDelta: 3.0,
};
