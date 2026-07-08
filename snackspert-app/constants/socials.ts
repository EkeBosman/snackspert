/**
 * Configuratie voor de "Volg Snackspert"-modal.
 *
 * Kanalen zijn bewust een lijst zodat er later eenvoudig een kanaal
 * (bijv. YouTube of een nieuwsbrief) bij kan.
 */

export interface SocialKanaal {
  key: string;
  label: string;
  icon: 'logo-instagram' | 'logo-tiktok' | 'logo-youtube' | 'mail';
  /** Deep link naar de app (wordt geprobeerd als de app geïnstalleerd is). */
  app: string;
  /** Fallback-URL in de browser. */
  web: string;
  /** Knopstijl binnen de huisstijl. */
  stijl: 'primary' | 'donker';
}

export const SOCIAL_KANALEN: SocialKanaal[] = [
  {
    key: 'instagram',
    label: 'Volg op Instagram',
    icon: 'logo-instagram',
    app: 'instagram://user?username=snackspert',
    web: 'https://www.instagram.com/snackspert/',
    stijl: 'primary',
  },
  {
    key: 'tiktok',
    label: 'Volg op TikTok',
    icon: 'logo-tiktok',
    app: 'https://www.tiktok.com/@snackspert',
    web: 'https://www.tiktok.com/@snackspert',
    stijl: 'donker',
  },
];

export const VOLG_MODAL_TEKST = {
  titel: '🍟 Wil je nóg meer Snackspert?',
  omschrijving:
    'In deze app vind je alle verzamelde recensies. Op Instagram en TikTok verschijnen vrijwel dagelijks nieuwe reviews van snackbars, supermarktproducten, smaaktests, lijstjes en andere snackcontent.',
  subregel: 'Meer dan 750 snackreviews verzameld.',
  nietNu: 'Niet nu',
};
