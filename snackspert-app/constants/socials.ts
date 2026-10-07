/**
 * Configuratie voor de "Volg Snackspert"-modal en de Over-pagina.
 *
 * Kanalen zijn bewust een lijst zodat er later eenvoudig een kanaal
 * (bijv. YouTube of een nieuwsbrief) bij kan.
 */

import { Alert, Linking } from 'react-native';
import { meldFout } from '../services/foutmelding';

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

export const WEBSITE_URL = 'https://snackspert.nl';
export const PRIVACY_URL = 'https://snackspert.nl/privacy/';

/**
 * Open een adres, en laat de gebruiker niet in het ongewisse als dat mislukt.
 *
 * Linking.openURL kan weigeren — op een toestel waar geen browser beschikbaar
 * is, of waar webinhoud beperkt is via Schermtijd. Deed de app daar niets mee,
 * dan gebeurde er bij een tik gewoon niets: de gebruiker tikt nog eens, en nog
 * eens, en concludeert dat de app stuk is. Dat is precies wat er gebeurde op de
 * Over-pagina.
 *
 * We vangen het nu af, tonen het adres zodat iemand er alsnog kan komen, en
 * melden het mét de uitkomst van canOpenURL — dan weten we de volgende keer
 * waar het misgaat in plaats van te moeten gissen.
 */
export async function openLink(url: string, waar: string): Promise<void> {
  try {
    await Linking.openURL(url);
    return;
  } catch (fout) {
    let kanOpenen: boolean | string = 'onbekend';
    try {
      kanOpenen = await Linking.canOpenURL(url);
    } catch {}

    meldFout(fout, 'link-openen', { url, waar, kanOpenen });

    Alert.alert(
      'Kon de pagina niet openen',
      `Je kunt hem zelf bezoeken:\n\n${url}`,
      [{ text: 'Oké' }]
    );
  }
}

/**
 * Open een kanaal: eerst de app via deep link, anders de browser.
 * Gedeeld door de volg-modal en de Over-pagina.
 */
export async function openSocialKanaal(k: SocialKanaal): Promise<void> {
  try {
    if (await Linking.canOpenURL(k.app)) {
      await Linking.openURL(k.app);
      return;
    }
  } catch {}
  await openLink(k.web, `social:${k.key}`);
}
