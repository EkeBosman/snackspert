import React from 'react';
import { View, Text, TouchableOpacity, StyleSheet, Image } from 'react-native';
import { clearCache } from '../services/cache';
import { meldFout } from '../services/foutmelding';
import { Colors, Spacing, BorderRadius, FontSize } from '../constants/theme';

/**
 * Vangt fouten op die anders een wit scherm geven.
 *
 * Gaat er iets mis tijdens het tekenen van een scherm, dan haalt React de hele
 * app weg en houd je niets over — precies het witte scherm dat we tijdens het
 * bouwen een paar keer hebben gezien. Dit zet er een leesbare melding neer,
 * stuurt de fout door, en geeft twee uitwegen.
 *
 * De tweede uitweg is de belangrijkste: is de opgeslagen lijst beschadigd, dan
 * crasht de app bij élke start opnieuw en komt de gebruiker er nooit meer in.
 * Door de cache te wissen is dat een eenmalig ongemak in plaats van een app die
 * voorgoed stuk is.
 */

interface Props {
  children: React.ReactNode;
}

interface State {
  fout: Error | null;
  bezig: boolean;
}

export class Foutvanger extends React.Component<Props, State> {
  state: State = { fout: null, bezig: false };

  static getDerivedStateFromError(fout: Error): Partial<State> {
    return { fout };
  }

  componentDidCatch(fout: Error, info: React.ErrorInfo) {
    meldFout(fout, 'scherm-crash', { componentStack: info.componentStack });
  }

  opnieuw = () => {
    this.setState({ fout: null, bezig: false });
  };

  opnieuwEnWissen = async () => {
    this.setState({ bezig: true });
    try {
      await clearCache();
    } catch {
      // Lukt het wissen niet, dan proberen we het alsnog zonder.
    }
    this.setState({ fout: null, bezig: false });
  };

  render() {
    if (!this.state.fout) return this.props.children;

    return (
      <View style={styles.container}>
        <Image
          source={require('../assets/SNACKSPERT_LOGO_SB_PIXEL.png')}
          style={styles.logo}
        />
        <Text style={styles.titel}>Hier ging iets mis</Text>
        <Text style={styles.uitleg}>
          Er is een storing in de app. De melding is doorgestuurd, dus we kunnen
          het oplossen.
        </Text>

        <TouchableOpacity style={styles.knop} onPress={this.opnieuw} activeOpacity={0.8}>
          <Text style={styles.knopText}>Probeer opnieuw</Text>
        </TouchableOpacity>

        <TouchableOpacity
          style={styles.tweedeKnop}
          onPress={this.opnieuwEnWissen}
          activeOpacity={0.7}
          disabled={this.state.bezig}
        >
          <Text style={styles.tweedeKnopText}>
            {this.state.bezig ? 'Bezig…' : 'Blijft het misgaan? Gegevens opnieuw ophalen'}
          </Text>
        </TouchableOpacity>
      </View>
    );
  }
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    alignItems: 'center',
    justifyContent: 'center',
    padding: Spacing.xl,
    backgroundColor: Colors.background,
  },
  logo: {
    width: 180,
    height: 40,
    resizeMode: 'contain',
    marginBottom: Spacing.xl,
  },
  titel: {
    fontSize: FontSize.xl,
    fontWeight: '700',
    color: Colors.text,
    marginBottom: Spacing.sm,
  },
  uitleg: {
    fontSize: FontSize.md,
    color: Colors.textSecondary,
    textAlign: 'center',
    lineHeight: 22,
    marginBottom: Spacing.xl,
  },
  knop: {
    paddingHorizontal: Spacing.xl,
    paddingVertical: Spacing.md,
    borderRadius: BorderRadius.full,
    backgroundColor: Colors.primary,
  },
  knopText: {
    fontSize: FontSize.md,
    fontWeight: '700',
    color: Colors.textOnPrimary,
  },
  tweedeKnop: {
    marginTop: Spacing.lg,
    paddingHorizontal: Spacing.md,
    paddingVertical: Spacing.sm,
  },
  tweedeKnopText: {
    fontSize: FontSize.sm,
    color: Colors.textSecondary,
    textDecorationLine: 'underline',
  },
});
