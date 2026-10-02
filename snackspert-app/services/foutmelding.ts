import Constants from 'expo-constants';
import * as Sentry from '@sentry/react-native';
import { SENTRY_DSN } from '../constants/sentry';

/**
 * Foutmeldingen die bij Eke terechtkomen in plaats van bij niemand.
 *
 * Zonder dit hoor je een crash alleen als een gebruiker hem zelf meldt, en de
 * meeste mensen melden niets — ze verwijderen de app.
 *
 * De DSN staat in constants/sentry.ts. Is die leeg, dan doet dit bestand niets:
 * geen verbinding, geen vertraging, geen fout. Zo kan de app ook draaien zonder
 * dat er een Sentry-project achter hangt.
 *
 * app.json wordt nog als terugval gelezen, maar is niet de plek om hem te
 * zetten: dat veld zit in de vingerafdruk van de build, dus een wijziging daar
 * komt nooit via een update binnen. Zie constants/sentry.ts.
 */

const UIT_APP_JSON: string =
  (Constants.expoConfig?.extra as { sentryDsn?: string })?.sentryDsn || '';

const DSN: string = SENTRY_DSN || UIT_APP_JSON;

export const FOUTMELDING_AAN = DSN.length > 0;

let gestart = false;

/** Zet de foutmelding aan. Eén keer aanroepen, zo vroeg mogelijk. */
export function startFoutmelding(): void {
  if (!FOUTMELDING_AAN || gestart) return;
  gestart = true;

  Sentry.init({
    dsn: DSN,
    // Alleen fouten, geen prestatiemetingen: dat laatste stuurt voortdurend
    // gegevens en dat is hier nergens voor nodig.
    tracesSampleRate: 0,
    // In de simulator/ontwikkelserver niets versturen — dan is je overzicht
    // gevuld met je eigen gerommel in plaats van met echte gebruikers.
    enabled: !__DEV__,
    // Geen namen, e-mailadressen of IP-adressen meesturen. Dat scheelt een
    // categorie in de privacyvragenlijst van de App Store, en we hebben het
    // niet nodig om een fout te begrijpen.
    sendDefaultPii: false,
    // De app heeft geen accounts, maar laat ook geen toevallige
    // identificatiegegevens door.
    beforeSend(event) {
      delete event.user;
      delete event.server_name;
      return event;
    },
  });
}

/**
 * Meld een fout waar de app zelf van herstelt.
 *
 * Gebruik dit alleen voor dingen die je wil weten. Een mislukte
 * netwerkaanvraag omdat iemand in de trein zit, is geen fout.
 */
export function meldFout(fout: unknown, waar: string, extra?: Record<string, unknown>): void {
  if (!FOUTMELDING_AAN) return;
  Sentry.captureException(fout instanceof Error ? fout : new Error(String(fout)), {
    tags: { waar },
    extra,
  });
}
