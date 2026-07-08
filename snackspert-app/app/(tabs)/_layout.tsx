import { Tabs } from 'expo-router';
import { Ionicons } from '@expo/vector-icons';
import { Colors, FontSize } from '../../constants/theme';
import { RestaurantProvider } from '../../contexts/RestaurantContext';

export default function TabLayout() {
  return (
    <RestaurantProvider>
      <Tabs
        screenOptions={{
          headerStyle: { backgroundColor: Colors.primary },
          headerTintColor: Colors.textOnPrimary,
          headerTitleStyle: { fontWeight: '700', fontSize: FontSize.xl },
          tabBarActiveTintColor: Colors.primary,
          tabBarInactiveTintColor: Colors.textLight,
          tabBarStyle: {
            backgroundColor: Colors.surface,
            borderTopColor: Colors.border,
          },
          tabBarLabelStyle: {
            fontSize: FontSize.xs,
            fontWeight: '600',
          },
        }}
      >
        <Tabs.Screen
          name="index"
          options={{
            title: 'Kaart',
            headerTitle: 'Snackspert',
            tabBarIcon: ({ color, size }) => (
              <Ionicons name="map" size={size} color={color} />
            ),
          }}
        />
        <Tabs.Screen
          name="lijst"
          options={{
            title: 'Lijst',
            headerTitle: 'Snackspert',
            tabBarIcon: ({ color, size }) => (
              <Ionicons name="list" size={size} color={color} />
            ),
          }}
        />
        <Tabs.Screen
          name="opgeslagen"
          options={{
            title: 'Opgeslagen',
            headerTitle: 'Opgeslagen',
            tabBarIcon: ({ color, size }) => (
              <Ionicons name="bookmark" size={size} color={color} />
            ),
          }}
        />
      </Tabs>
    </RestaurantProvider>
  );
}
