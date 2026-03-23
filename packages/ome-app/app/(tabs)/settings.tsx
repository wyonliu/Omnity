import { useState, useCallback } from "react";
import {
  View,
  Text,
  StyleSheet,
  ScrollView,
  TouchableOpacity,
  TextInput,
  Alert,
  Switch,
} from "react-native";
import { router, useFocusEffect } from "expo-router";
import AsyncStorage from "@react-native-async-storage/async-storage";
import { getProfile, getStatus, clearToken } from "../../lib/api";
import { colors, spacing, fontSize, borderRadius } from "../../lib/theme";

const AUTONOMY_LEVELS = [
  {
    level: 0,
    name: "观察者",
    desc: "Ome 只观察不主动行动",
    emoji: "👁️",
  },
  {
    level: 1,
    name: "助手",
    desc: "Ome 可以提建议、写草稿",
    emoji: "🤝",
  },
  {
    level: 2,
    name: "代理人",
    desc: "Ome 可以代你执行操作",
    emoji: "🚀",
  },
];

export default function SettingsScreen() {
  const [profile, setProfile] = useState<any>(null);
  const [status, setStatus] = useState<any>(null);
  const [name, setName] = useState("");
  const [autonomyLevel, setAutonomyLevel] = useState(0);
  const [notificationsEnabled, setNotificationsEnabled] = useState(true);

  const load = useCallback(async () => {
    try {
      const [p, s, storedName] = await Promise.all([
        getProfile(),
        getStatus(),
        AsyncStorage.getItem("ome_name"),
      ]);
      setProfile(p);
      setStatus(s);
      if (storedName) setName(storedName);
      if (p?.autonomy?.level !== undefined) {
        setAutonomyLevel(p.autonomy.level);
      }
    } catch (err) {
      console.log("Settings load error:", err);
    }
  }, []);

  useFocusEffect(
    useCallback(() => {
      load();
    }, [load])
  );

  const handleLogout = () => {
    Alert.alert("退出登录", "确定要退出吗？Ome 的记忆不会丢失。", [
      { text: "取消", style: "cancel" },
      {
        text: "退出",
        style: "destructive",
        onPress: async () => {
          await clearToken();
          await AsyncStorage.removeItem("ome_user_id");
          await AsyncStorage.removeItem("ome_name");
          router.replace("/onboarding");
        },
      },
    ]);
  };

  const version = status?.version ?? "0.4.0";
  const bondLevel = profile?.bond?.level ?? 0;
  const totalMemories = profile?.total_memories ?? 0;
  const totalInteractions = profile?.bond?.total_interactions ?? 0;

  return (
    <ScrollView
      style={styles.container}
      contentContainerStyle={styles.content}
    >
      {/* Header */}
      <View style={styles.header}>
        <Text style={styles.headerTitle}>⚙️ 设置</Text>
      </View>

      {/* Profile summary */}
      <View style={styles.profileCard}>
        <View style={styles.profileRow}>
          <View style={styles.avatar}>
            <Text style={styles.avatarText}>
              {name.slice(0, 1).toUpperCase() || "O"}
            </Text>
          </View>
          <View style={styles.profileInfo}>
            <Text style={styles.profileName}>{name || "Ome"}</Text>
            <Text style={styles.profileSub}>
              Lv.{bondLevel} · {totalInteractions} 次对话 · {totalMemories}{" "}
              条记忆
            </Text>
          </View>
        </View>
      </View>

      {/* Autonomy level */}
      <View style={styles.section}>
        <Text style={styles.sectionTitle}>自治等级</Text>
        <Text style={styles.sectionDesc}>
          决定 Ome 可以自主做多少事情
        </Text>
        {AUTONOMY_LEVELS.map((al) => (
          <TouchableOpacity
            key={al.level}
            style={[
              styles.autonomyCard,
              autonomyLevel === al.level && styles.autonomyCardActive,
            ]}
            onPress={() => setAutonomyLevel(al.level)}
          >
            <Text style={styles.autonomyEmoji}>{al.emoji}</Text>
            <View style={styles.autonomyInfo}>
              <Text
                style={[
                  styles.autonomyName,
                  autonomyLevel === al.level && styles.autonomyNameActive,
                ]}
              >
                {al.name}
              </Text>
              <Text style={styles.autonomyDesc}>{al.desc}</Text>
            </View>
            {autonomyLevel === al.level && (
              <Text style={styles.checkMark}>✓</Text>
            )}
          </TouchableOpacity>
        ))}
      </View>

      {/* Notifications */}
      <View style={styles.section}>
        <Text style={styles.sectionTitle}>通知</Text>
        <View style={styles.settingRow}>
          <View>
            <Text style={styles.settingLabel}>Ome 消息推送</Text>
            <Text style={styles.settingDesc}>
              主动关怀、事件提醒、成就解锁
            </Text>
          </View>
          <Switch
            value={notificationsEnabled}
            onValueChange={setNotificationsEnabled}
            trackColor={{ false: colors.bgInput, true: colors.accent }}
            thumbColor={colors.textPrimary}
          />
        </View>
      </View>

      {/* About */}
      <View style={styles.section}>
        <Text style={styles.sectionTitle}>关于</Text>
        <View style={styles.aboutRow}>
          <Text style={styles.aboutLabel}>版本</Text>
          <Text style={styles.aboutValue}>Ome v{version}</Text>
        </View>
        <View style={styles.aboutRow}>
          <Text style={styles.aboutLabel}>引擎</Text>
          <Text style={styles.aboutValue}>
            Mindos v{status?.mindos_version ?? "0.4.0"}
          </Text>
        </View>
        <View style={styles.aboutRow}>
          <Text style={styles.aboutLabel}>项目</Text>
          <Text style={styles.aboutValue}>Omnity (开源)</Text>
        </View>
      </View>

      {/* Danger zone */}
      <View style={styles.section}>
        <TouchableOpacity style={styles.logoutBtn} onPress={handleLogout}>
          <Text style={styles.logoutText}>退出登录</Text>
        </TouchableOpacity>
      </View>

      <Text style={styles.footer}>
        Omnity · 碳硅共居，万物有灵
      </Text>
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: colors.bg },
  content: { paddingBottom: spacing.xxl },

  header: {
    paddingTop: 56,
    paddingHorizontal: spacing.lg,
    paddingBottom: spacing.md,
  },
  headerTitle: {
    fontSize: fontSize.xl,
    fontWeight: "700",
    color: colors.textPrimary,
  },

  // Profile
  profileCard: {
    marginHorizontal: spacing.lg,
    marginBottom: spacing.lg,
    backgroundColor: colors.bgCard,
    borderRadius: borderRadius.lg,
    padding: spacing.md,
    borderWidth: 1,
    borderColor: colors.border,
  },
  profileRow: { flexDirection: "row", alignItems: "center" },
  avatar: {
    width: 48,
    height: 48,
    borderRadius: 24,
    backgroundColor: colors.accent,
    justifyContent: "center",
    alignItems: "center",
    marginRight: spacing.md,
  },
  avatarText: {
    fontSize: fontSize.xl,
    fontWeight: "700",
    color: colors.bg,
  },
  profileInfo: { flex: 1 },
  profileName: {
    fontSize: fontSize.lg,
    fontWeight: "700",
    color: colors.textPrimary,
  },
  profileSub: { fontSize: fontSize.sm, color: colors.textMuted },

  // Sections
  section: {
    marginHorizontal: spacing.lg,
    marginBottom: spacing.lg,
  },
  sectionTitle: {
    fontSize: fontSize.md,
    fontWeight: "600",
    color: colors.accent,
    marginBottom: spacing.xs,
  },
  sectionDesc: {
    fontSize: fontSize.sm,
    color: colors.textMuted,
    marginBottom: spacing.md,
  },

  // Autonomy
  autonomyCard: {
    flexDirection: "row",
    alignItems: "center",
    backgroundColor: colors.bgCard,
    borderRadius: borderRadius.md,
    padding: spacing.md,
    marginBottom: spacing.sm,
    borderWidth: 1,
    borderColor: colors.border,
  },
  autonomyCardActive: { borderColor: colors.accent },
  autonomyEmoji: { fontSize: 24, marginRight: spacing.md },
  autonomyInfo: { flex: 1 },
  autonomyName: {
    fontSize: fontSize.md,
    fontWeight: "600",
    color: colors.textPrimary,
  },
  autonomyNameActive: { color: colors.accent },
  autonomyDesc: { fontSize: fontSize.sm, color: colors.textSecondary },
  checkMark: {
    fontSize: fontSize.lg,
    color: colors.accent,
    fontWeight: "700",
  },

  // Settings rows
  settingRow: {
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "center",
    backgroundColor: colors.bgCard,
    borderRadius: borderRadius.md,
    padding: spacing.md,
    borderWidth: 1,
    borderColor: colors.border,
  },
  settingLabel: {
    fontSize: fontSize.md,
    color: colors.textPrimary,
    fontWeight: "500",
  },
  settingDesc: { fontSize: fontSize.xs, color: colors.textMuted, marginTop: 2 },

  // About
  aboutRow: {
    flexDirection: "row",
    justifyContent: "space-between",
    paddingVertical: spacing.sm,
    borderBottomWidth: 1,
    borderBottomColor: colors.border,
  },
  aboutLabel: { fontSize: fontSize.md, color: colors.textSecondary },
  aboutValue: { fontSize: fontSize.md, color: colors.textPrimary },

  // Logout
  logoutBtn: {
    backgroundColor: colors.bgCard,
    borderRadius: borderRadius.md,
    padding: spacing.md,
    alignItems: "center",
    borderWidth: 1,
    borderColor: colors.error,
  },
  logoutText: {
    fontSize: fontSize.md,
    fontWeight: "600",
    color: colors.error,
  },

  footer: {
    textAlign: "center",
    fontSize: fontSize.xs,
    color: colors.textMuted,
    marginTop: spacing.lg,
    marginBottom: spacing.xxl,
  },
});
