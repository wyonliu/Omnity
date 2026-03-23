import { useEffect, useState, useCallback } from "react";
import {
  View,
  Text,
  StyleSheet,
  ScrollView,
  TouchableOpacity,
  RefreshControl,
} from "react-native";
import { router } from "expo-router";
import AsyncStorage from "@react-native-async-storage/async-storage";
import { getDashboard, getEvents, getProfile } from "../../lib/api";
import { colors, spacing, fontSize, borderRadius } from "../../lib/theme";

// Bond level visual stages
const SOULSCAPE_STAGES = [
  { emoji: "🌱", label: "种子", desc: "一切刚开始" },
  { emoji: "🌿", label: "嫩芽", desc: "开始有记忆了" },
  { emoji: "🌳", label: "小树", desc: "开始有生活了" },
  { emoji: "🌲", label: "茂盛", desc: "能帮你做事了" },
  { emoji: "🍊", label: "结果", desc: "能替你社交了" },
  { emoji: "🌸", label: "繁花", desc: "完全代表你了" },
  { emoji: "🏔️", label: "参天", desc: "传说级存在" },
];

export default function SoulscapeScreen() {
  const [profile, setProfile] = useState<any>(null);
  const [dashboard, setDashboard] = useState<any>(null);
  const [events, setEvents] = useState<any[]>([]);
  const [refreshing, setRefreshing] = useState(false);
  const [name, setName] = useState("Ome");

  const load = useCallback(async () => {
    try {
      const [p, d, e, n] = await Promise.all([
        getProfile(),
        getDashboard(),
        getEvents(),
        AsyncStorage.getItem("ome_name"),
      ]);
      setProfile(p);
      setDashboard(d);
      setEvents(e || []);
      if (n) setName(n);
      // Cache bond level for progressive tab unlock
      if (p?.bond?.level !== undefined) {
        AsyncStorage.setItem("ome_bond_level", String(p.bond.level));
      }
    } catch (err) {
      console.log("Load error:", err);
    }
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  const onRefresh = async () => {
    setRefreshing(true);
    await load();
    setRefreshing(false);
  };

  const bondLevel = profile?.bond?.level ?? 0;
  const stage = SOULSCAPE_STAGES[Math.min(bondLevel, 6)];
  const streak = profile?.streak?.current ?? 0;
  const mood = profile?.emotion?.mood ?? "neutral";
  const moodEmoji = profile?.emotion?.mood_emoji ?? "😌";

  return (
    <ScrollView
      style={styles.container}
      contentContainerStyle={styles.content}
      refreshControl={
        <RefreshControl refreshing={refreshing} onRefresh={onRefresh} tintColor={colors.accent} />
      }
    >
      {/* Soulscape visual */}
      <View style={styles.soulscape}>
        <Text style={styles.soulscapeEmoji}>{stage.emoji}</Text>
        <Text style={styles.soulscapeLabel}>
          灵境 · 第 {profile?.bond?.total_interactions ?? 0} 天
        </Text>
        <Text style={styles.soulscapeDesc}>{stage.desc}</Text>
      </View>

      {/* Ome greeting / events */}
      <View style={styles.greetingCard}>
        <Text style={styles.greetingEmoji}>{moodEmoji}</Text>
        {events.length > 0 ? (
          <Text style={styles.greetingText}>{events[0].message}</Text>
        ) : (
          <Text style={styles.greetingText}>
            嗨，{name}。今天想聊什么？
          </Text>
        )}
      </View>

      {/* Quick stats */}
      <View style={styles.statsRow}>
        <View style={styles.statCard}>
          <Text style={styles.statValue}>Lv.{bondLevel}</Text>
          <Text style={styles.statLabel}>
            {profile?.bond?.name ?? "初见"}
          </Text>
        </View>
        <View style={styles.statCard}>
          <Text style={[styles.statValue, { color: colors.streakOrange }]}>
            {streak}
          </Text>
          <Text style={styles.statLabel}>连续天数</Text>
        </View>
        <View style={styles.statCard}>
          <Text style={[styles.statValue, { color: colors.achieveGold }]}>
            {dashboard?.achievements?.count ?? "0/0"}
          </Text>
          <Text style={styles.statLabel}>成就</Text>
        </View>
        <View style={styles.statCard}>
          <Text style={[styles.statValue, { color: colors.emotionPurple }]}>
            {profile?.total_memories ?? 0}
          </Text>
          <Text style={styles.statLabel}>记忆</Text>
        </View>
      </View>

      {/* Highlights */}
      {dashboard?.highlights && dashboard.highlights.length > 0 && (
        <View style={styles.highlightCard}>
          <Text style={styles.highlightTitle}>本周亮点</Text>
          {dashboard.highlights.slice(0, 5).map((h: string, i: number) => (
            <Text key={i} style={styles.highlightItem}>
              · {h}
            </Text>
          ))}
        </View>
      )}

      {/* Quick actions */}
      <View style={styles.actionsRow}>
        <TouchableOpacity
          style={styles.actionBtn}
          onPress={() => router.push("/(tabs)/chat")}
        >
          <Text style={styles.actionEmoji}>💬</Text>
          <Text style={styles.actionLabel}>聊天</Text>
        </TouchableOpacity>
        <TouchableOpacity
          style={styles.actionBtn}
          onPress={() => router.push("/(tabs)/chat?mode=mirror")}
        >
          <Text style={styles.actionEmoji}>🪞</Text>
          <Text style={styles.actionLabel}>镜像</Text>
        </TouchableOpacity>
        <TouchableOpacity
          style={styles.actionBtn}
          onPress={() => router.push("/(tabs)/memory")}
        >
          <Text style={styles.actionEmoji}>🧠</Text>
          <Text style={styles.actionLabel}>记忆</Text>
        </TouchableOpacity>
        <TouchableOpacity
          style={styles.actionBtn}
          onPress={() => router.push("/(tabs)/life")}
        >
          <Text style={styles.actionEmoji}>📊</Text>
          <Text style={styles.actionLabel}>成长</Text>
        </TouchableOpacity>
      </View>
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: colors.bg },
  content: { padding: spacing.lg, paddingTop: 60 },

  soulscape: { alignItems: "center", marginBottom: spacing.xl, paddingVertical: spacing.xxl },
  soulscapeEmoji: { fontSize: 80, marginBottom: spacing.md },
  soulscapeLabel: { fontSize: fontSize.md, color: colors.textSecondary },
  soulscapeDesc: { fontSize: fontSize.sm, color: colors.textMuted, marginTop: spacing.xs },

  greetingCard: {
    flexDirection: "row", alignItems: "center",
    backgroundColor: colors.bgCard, borderRadius: borderRadius.lg,
    padding: spacing.md, marginBottom: spacing.lg,
    borderWidth: 1, borderColor: colors.border,
  },
  greetingEmoji: { fontSize: 28, marginRight: spacing.md },
  greetingText: { fontSize: fontSize.md, color: colors.textPrimary, flex: 1, lineHeight: 22 },

  statsRow: { flexDirection: "row", gap: spacing.sm, marginBottom: spacing.lg },
  statCard: {
    flex: 1, backgroundColor: colors.bgCard, borderRadius: borderRadius.md,
    padding: spacing.md, alignItems: "center",
    borderWidth: 1, borderColor: colors.border,
  },
  statValue: { fontSize: fontSize.xl, fontWeight: "700", color: colors.bondGreen },
  statLabel: { fontSize: fontSize.xs, color: colors.textMuted, marginTop: spacing.xs },

  highlightCard: {
    backgroundColor: colors.bgCard, borderRadius: borderRadius.lg,
    padding: spacing.md, marginBottom: spacing.lg,
    borderWidth: 1, borderColor: colors.border,
  },
  highlightTitle: {
    fontSize: fontSize.md, fontWeight: "600", color: colors.accent,
    marginBottom: spacing.sm,
  },
  highlightItem: { fontSize: fontSize.sm, color: colors.textSecondary, lineHeight: 22 },

  actionsRow: {
    flexDirection: "row", gap: spacing.md, marginBottom: spacing.xxl,
  },
  actionBtn: {
    flex: 1, backgroundColor: colors.bgCard, borderRadius: borderRadius.lg,
    padding: spacing.md, alignItems: "center",
    borderWidth: 1, borderColor: colors.border,
  },
  actionEmoji: { fontSize: 24, marginBottom: spacing.xs },
  actionLabel: { fontSize: fontSize.sm, color: colors.textSecondary },
});
