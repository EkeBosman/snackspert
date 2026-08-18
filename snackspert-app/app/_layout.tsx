import { Stack } from 'expo-router';
import { StatusBar } from 'expo-status-bar';
import { SafeAreaProvider } from 'react-native-safe-area-context';
import { Colors } from '../constants/theme';
import { FavoritesProvider } from '../contexts/FavoritesContext';
import { EngagementProvider } from '../contexts/EngagementContext';

export default function RootLayout() {
  return (
    <SafeAreaProvider>
      <EngagementProvider>
        <FavoritesProvider>
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
          </Stack>
        </FavoritesProvider>
      </EngagementProvider>
    </SafeAreaProvider>
  );
}
