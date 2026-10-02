import { Stack } from 'expo-router';
import { StatusBar } from 'expo-status-bar';
import { SafeAreaProvider } from 'react-native-safe-area-context';
import { Colors } from '../constants/theme';
import { FavoritesProvider } from '../contexts/FavoritesContext';
import { EngagementProvider } from '../contexts/EngagementContext';
import { RestaurantProvider } from '../contexts/RestaurantContext';
import { Foutvanger } from '../components/Foutvanger';
import { startFoutmelding } from '../services/foutmelding';

// Zo vroeg mogelijk, zodat ook fouten tijdens het opstarten gemeld worden.
startFoutmelding();

export default function RootLayout() {
  return (
    <SafeAreaProvider>
      {/* Buitenom alles: een fout in een scherm geeft dan een melding in plaats
          van een wit scherm. */}
      <Foutvanger>
        <EngagementProvider>
          <FavoritesProvider>
            {/* Op rootniveau, zodat ook de detailpagina de al geladen gegevens
                kan gebruiken in plaats van ze opnieuw op te halen. */}
            <RestaurantProvider>
              <StatusBar style="light" />
              <Stack
                screenOptions={{
                  headerStyle: { backgroundColor: Colors.primary },
                  headerTintColor: Colors.textOnPrimary,
                  headerTitleStyle: { fontWeight: '700' },
                  contentStyle: { backgroundColor: Colors.background },
                }}
              >
                <Stack.Screen name="(tabs)" options={{ headerShown: false }} />
                <Stack.Screen
                  name="restaurant/[id]"
                  options={{
                    title: 'Restaurant',
                    presentation: 'card',
                  }}
                />
                <Stack.Screen name="over" options={{ title: 'Over Snackspert' }} />
              </Stack>
            </RestaurantProvider>
          </FavoritesProvider>
        </EngagementProvider>
      </Foutvanger>
    </SafeAreaProvider>
  );
}
