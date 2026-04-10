/**
 * TypeScript types voor de Snackspert app
 */

export interface Restaurant {
  id: number;
  naam: string;
  slug: string;
  adres: string;
  stad: string;
  tekst: string;
  sterren: number;
  sterrenTekst: string;
  afbeeldingUrl: string;
  paginaUrl: string;
  categorieen: string[];
  latitude: number | null;
  longitude: number | null;
}

export interface RestaurantSummary {
  id: number;
  naam: string;
  slug: string;
  paginaUrl: string;
  categorieen: string[];
}

export interface WPRestaurant {
  id: number;
  title: { rendered: string };
  slug: string;
  link: string;
  content: { rendered: string };
  featured_media: number;
  // Custom taxonomy terms (indien beschikbaar)
  'restaurant-categorie'?: number[];
  // ACF fields (indien beschikbaar)
  acf?: {
    locatie?: {
      lat?: number;
      lng?: number;
      address?: string;
    };
    adres?: string;
    sterren?: number;
    [key: string]: unknown;
  };
}

export interface WPTaxonomyTerm {
  id: number;
  name: string;
  slug: string;
  count: number;
}

export type FoodCategory = typeof import('../constants/theme').FOOD_CATEGORIES[number];
export type DietFilter = typeof import('../constants/theme').DIET_FILTERS[number];

export interface FilterState {
  categorieen: string[];
  zoekterm: string;
  locatie: string;
  minimumSterren: number;
}
