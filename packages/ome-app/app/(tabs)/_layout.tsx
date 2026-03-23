/**
 * Tab layout — progressive unlock based on bond level.
 *
 * Day 0:  对话 + 灵境 (2 tabs)
 * Day 7:  + 记忆 (3 tabs, when memories accumulate)
 * Day 14: + 成长 (4 tabs, when achievements exist)
 * Day 30: + 广场 (5 tabs, OmeTown agent network)
 *
 * Settings accessible via gear icon in headers, not a tab.
 */
import { useEffect, useState } from "react";
import { Tabs } from "expo-router";
import { Ionicons } from "@expo/vector-icons";
import AsyncStorage from "@react-native-async-storage/async-storage";
import { colors, fontSize } from "../../lib/theme";

export default function TabLayout() {
  const [bondLevel, setBondLevel] = useState(0);

  useEffect(() => {
    // Load cached bond level for progressive unlock
    AsyncStorage.getItem("ome_bond_level").then((v) => {
      if (v) setBondLevel(parseInt(v, 10));
    });
  }, []);

  return (
    <Tabs
      screenOptions={{
        headerShown: false,
        tabBarStyle: {
          backgroundColor: colors.bgCard,
          borderTopColor: colors.border,
          borderTopWidth: 1,
          height: 85,
          paddingBottom: 20,
          paddingTop: 8,
        },
        tabBarActiveTintColor: colors.accent,
        tabBarInactiveTintColor: colors.textMuted,
        tabBarLabelStyle: { fontSize: fontSize.xs },
      }}
    >
      {/* Always visible: Chat (primary action) */}
      <Tabs.Screen
        name="chat"
        options={{
          title: "对话",
          tabBarIcon: ({ color, size }) => (
            <Ionicons name="chatbubbles-outline" size={size} color={color} />
          ),
        }}
      />

      {/* Always visible: Soulscape home */}
      <Tabs.Screen
        name="index"
        options={{
          title: "灵境",
          tabBarIcon: ({ color, size }) => (
            <Ionicons name="leaf-outline" size={size} color={color} />
          ),
        }}
      />

      {/* Unlock at bond level 1+ (has some memories) */}
      <Tabs.Screen
        name="memory"
        options={{
          title: "记忆",
          tabBarIcon: ({ color, size }) => (
            <Ionicons name="cube-outline" size={size} color={color} />
          ),
          href: bondLevel >= 1 ? undefined : null,
        }}
      />

      {/* Unlock at bond level 2+ (has achievements) */}
      <Tabs.Screen
        name="life"
        options={{
          title: "成长",
          tabBarIcon: ({ color, size }) => (
            <Ionicons name="trophy-outline" size={size} color={color} />
          ),
          href: bondLevel >= 2 ? undefined : null,
        }}
      />

      {/* Unlock at bond level 3+ (OmeTown agent network) */}
      <Tabs.Screen
        name="agents"
        options={{
          title: "广场",
          tabBarIcon: ({ color, size }) => (
            <Ionicons name="people-outline" size={size} color={color} />
          ),
          href: bondLevel >= 3 ? undefined : null,
        }}
      />

      {/* Settings — always available */}
      <Tabs.Screen
        name="settings"
        options={{
          title: "设置",
          tabBarIcon: ({ color, size }) => (
            <Ionicons name="settings-outline" size={size} color={color} />
          ),
        }}
      />
    </Tabs>
  );
}
