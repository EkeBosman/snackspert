/**
 * Bepaal het land van een restaurant, volledig offline.
 *
 * 1. Nederlandse adressen herkennen we aan de postcode (4 cijfers + 2 letters);
 *    dat is een betrouwbaar en goedkoop signaal (geen API-call nodig).
 * 2. Voor de rest gebruiken we een grove bounding-box per land op basis van de
 *    coördinaten. De boxen overlappen bij grenzen, dus de volgorde is van klein/
 *    specifiek naar groot.
 */

interface LandBox {
  naam: string;
  vlag: string;
  minLat: number;
  maxLat: number;
  minLng: number;
  maxLng: number;
}

// Volgorde = prioriteit (kleine/specifieke landen eerst).
const LAND_BOXEN: LandBox[] = [
  { naam: 'Luxemburg', vlag: '🇱🇺', minLat: 49.44, maxLat: 50.19, minLng: 5.73, maxLng: 6.53 },
  { naam: 'België', vlag: '🇧🇪', minLat: 49.50, maxLat: 51.51, minLng: 2.54, maxLng: 6.41 },
  { naam: 'Nederland', vlag: '🇳🇱', minLat: 50.75, maxLat: 53.68, minLng: 3.36, maxLng: 7.23 },
  { naam: 'Verenigd Koninkrijk', vlag: '🇬🇧', minLat: 49.86, maxLat: 60.86, minLng: -8.65, maxLng: 1.77 },
  { naam: 'Portugal', vlag: '🇵🇹', minLat: 36.96, maxLat: 42.15, minLng: -9.53, maxLng: -6.19 },
  { naam: 'Spanje', vlag: '🇪🇸', minLat: 35.95, maxLat: 43.79, minLng: -9.30, maxLng: 4.33 },
  { naam: 'Italië', vlag: '🇮🇹', minLat: 35.49, maxLat: 47.09, minLng: 6.62, maxLng: 18.52 },
  { naam: 'Frankrijk', vlag: '🇫🇷', minLat: 41.33, maxLat: 51.09, minLng: -5.15, maxLng: 9.56 },
  { naam: 'Duitsland', vlag: '🇩🇪', minLat: 47.27, maxLat: 55.10, minLng: 5.86, maxLng: 15.05 },
  { naam: 'Verenigde Staten', vlag: '🇺🇸', minLat: 24.40, maxLat: 49.40, minLng: -125.0, maxLng: -66.90 },
  { naam: 'Canada', vlag: '🇨🇦', minLat: 41.68, maxLat: 83.11, minLng: -141.0, maxLng: -52.60 },
];

const NL_POSTCODE = /\d{4}\s*[A-Z]{2}\b/;

export const LAND_VLAGGEN: Record<string, string> = {
  ...Object.fromEntries(LAND_BOXEN.map(l => [l.naam, l.vlag])),
  Overig: '🌍',
};

/**
 * Geeft de landnaam terug, of null als er (nog) te weinig gegevens zijn.
 */
export function bepaalLand(
  adres: string | undefined,
  lat: number | null,
  lng: number | null
): string | null {
  if (adres && NL_POSTCODE.test(adres)) return 'Nederland';
  if (lat == null || lng == null) return null;

  for (const box of LAND_BOXEN) {
    if (lat >= box.minLat && lat <= box.maxLat && lng >= box.minLng && lng <= box.maxLng) {
      return box.naam;
    }
  }
  return 'Overig';
}
