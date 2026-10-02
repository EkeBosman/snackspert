/**
 * De Sentry-DSN — het adres waar foutmeldingen naartoe gaan.
 *
 * Waarom hier en niet in app.json: de runtimeversie van de app is een
 * vingerafdruk over alles wat de native build bepaalt, en app.json hoort daar
 * helemaal bij — inclusief het `extra`-veld. Zet je de DSN daar, dan verandert
 * de vingerafdruk, en weigert een bestaande app de update. De DSN zou dan
 * alleen met een nieuwe build in de app te krijgen zijn.
 *
 * Een gewoon codebestand zit niet in die vingerafdruk. Dus kan deze waarde met
 * `eas update` naar een app die al geïnstalleerd is, zonder opnieuw te bouwen.
 *
 * Leeg laten betekent: geen foutmeldingen, en de app doet niets extra.
 */
export const SENTRY_DSN = '';
