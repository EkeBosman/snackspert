import { Tabs, router } from 'expo-router';
import { Image, TouchableOpacity } from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { Colors, FontSize } from '../../constants/theme';
import { RestaurantProvider } from '../../contexts/RestaurantContext';

// Logo in de header (transparant, past op de gouden balk).
const LogoTitel = () => (
  <Image
    source={require('../../assets/SNACKSPERT_LOGO_SB_PIXEL.png')}
    style={{ width: 150, height: 34, resizeMode: 'contain' }}
  />
);

// Info-knop rechtsboven: naar de Over-pagina (socials, website, privacy).
const InfoKnop = () => (
  <TouchableOpacity
    onPress={() => router.push('/over')}
    hitSlop={{ top: 10, bottom: 10, left: 10, right: 10 }}
    activeOpacity={0.7}
    style={{ paddingHorizontal: 4 }}
  >
    <Ionicons name="information-circle-outline" size={26} color={Colors.textOnPrimary} />
  </TouchableOpacity>
);

export default function TabLayout() {
  return (
    <RestaurantProvider>
      <Tabs
        screenOptions={{
          headerStyle: { backgroundColor: Colors.primary },
          headerTintColor: Colors.textOnPrimary,
          headerTitleStyle: { fontWeight: '700', fontSize: FontSize.xl },
          headerRight: () => <InfoKnop />,
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
            headerTitle: () => <LogoTitel />,
            tabBarIcon: ({ color, size }) => (
              <Ionicons name="map" size={size} color={color} />
            ),
          }}
        />
        <Tabs.Screen
          name="lijst"
          options={{
            title: 'Lijst',
            headerTitle: () => <LogoTitel />,
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
