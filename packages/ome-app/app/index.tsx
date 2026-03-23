/**
 * Entry point — routes to the right screen based on auth state.
 *
 * Key design: NEW users go straight to first-chat (zero registration).
 * Returning registered users go to the tab home.
 */
import { useEffect, useState } from "react";
import { Redirect } from "expo-router";
import { View, ActivityIndicator } from "react-native";
import { isLoggedIn } from "../lib/api";
import { colors } from "../lib/theme";

export default function Index() {
  const [loading, setLoading] = useState(true);
  const [loggedIn, setLoggedIn] = useState(false);

  useEffect(() => {
    isLoggedIn().then((v) => {
      setLoggedIn(v);
      setLoading(false);
    });
  }, []);

  if (loading) {
    return (
      <View
        style={{
          flex: 1,
          justifyContent: "center",
          alignItems: "center",
          backgroundColor: colors.bg,
        }}
      >
        <ActivityIndicator size="large" color={colors.accent} />
      </View>
    );
  }

  // Registered user → tab home
  if (loggedIn) {
    return <Redirect href="/(tabs)" />;
  }

  // New user → first chat (zero registration, immediate value)
  return <Redirect href="/first-chat" />;
}
