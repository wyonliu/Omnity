import { useState, useCallback } from "react";
import {
  View,
  Text,
  StyleSheet,
  ScrollView,
  RefreshControl,
  TouchableOpacity,
} from "react-native";
import { useFocusEffect } from "expo-router";
import { getDashboard, getProfile, listSkills } from "../../lib/api";
import { colors, spacing, fontSize, borderRadius } from "../../lib/theme";

const BOND_STAGES = [
  { emoji: "🌱", name: "初见", desc: "一切刚开始" },
  { emoji: "🌿", name: "嫩芽", desc: "开始有记忆了" },
  { emoji: "🌳", name: "小树", desc: "开始有生活了" },
  { emoji: "🌲", name: "茂盛", desc: "能帮你做事了" },
  { emoji: "🍊", name: "结果", desc: "能替你社交了" },
  { emoji: "🌸", name: "繁花", desc: "完全代表你了" },
  { emoji: "🏔️", name: "参天", desc: "传说级存在" },
];

const STREAK_MILESTONES = [3, 7, 14, 30, 90, 365];

export default function LifeScreen() {
  const [profile, setProfile] = useState<any>(null);
  const [dashboard, setDashboard] = useState<any>(null);
  const [skills, setSkills] = useState<any[]>([]);
  const [refreshing, setRefreshing] = useState(false);
  const [tab, setTab] = useState<"overview" | "achieve" | "skills">("overview");

  const load = useCallback(async () => {
    try {
      const [p, d, s] = await Promise.all([
        getProfile(),
        getDashboard(),
        listSkills(),
      ]);
      setProfile(p);
      setDashboard(d);
      setSkills(s.skills || s || []);
    } catch (err) {
      console.log("Life load error:", err);
    }
  }, []);

  useFocusEffect(
    useCallback(() => {
      load();
    }, [load])
  );

  const onRefresh = async () => {
    setRefreshing(true);
    await load();
    setRefreshing(false);
  };

  const bondLevel = profile?.bond?.level ?? 0;
  const bondName = profile?.bond?.name ?? "初见";
  const bondProgress = profile?.bond?.progress ?? 0;
  const totalInteractions = profile?.bond?.total_interactions ?? 0;
  const stage = BOND_STAGES[Math.min(bondLevel, 6)];

  const streak = profile?.streak?.current ?? 0;
  const longestStreak = profile?.streak?.longest ?? 0;
  const nextMilestone = STREAK_MILESTONES.find((m) => m > streak) || 365;

  const achievements = dashboard?.achievements?.list || [];
  const achieveCount = dashboard?.achievements?.count || "0/0";

  const mood = profile?.emotion?.mood ?? "neutral";
  const moodEmoji = profile?.emotion?.mood_emoji ?? "😌";

  return (
    <ScrollView
      style={styles.container}
      contentContainerStyle={styles.content}
      refreshControl={
        <RefreshControl
          refreshing={refreshing}
          onRefresh={onRefresh}
          tintColor={colors.accent}
        />
      }
    >
      {/* Header */}
      <View style={styles.header}>
        <Text style={styles.headerTitle}>📊 成长</Text>
      </View>

      {/* Bond progress hero */}
      <View style={styles.bondHero}>
        <Text style={styles.bondEmoji}>{stage.emoji}</Text>
        <Text style={styles.bondLevel}>
          Lv.{bondLevel} · {bondName}
        </Text>
        <Text style={styles.bondDesc}>{stage.desc}</Text>

        {/* Progress bar */}
        <View style={styles.progressOuter}>
          <View
            style={[
              styles.progressInner,
              { width: `${Math.min(bondProgress * 100, 100)}%` },
            ]}
          />
        </View>
        <Text style={styles.progressText}>
          第 {totalInteractions} 次对话 · 下一阶段{" "}
          {((1 - bondProgress) * 100).toFixed(0)}%
        </Text>
      </View>

      {/* Tab switcher */}
      <View style={styles.tabBar}>
        {(["overview", "achieve", "skills"] as const).map((t) => (
          <TouchableOpacity
            key={t}
            style={[styles.tabItem, tab === t && styles.tabActive]}
            onPress={() => setTab(t)}
          >
            <Text style={[styles.tabText, tab === t && styles.tabTextActive]}>
              {t === "overview" ? "总览" : t === "achieve" ? "成就" : "技能"}
            </Text>
          </TouchableOpacity>
        ))}
      </View>

      {/* Tab content */}
      {tab === "overview" && (
        <View>
          {/* Emotion */}
          <View style={styles.card}>
            <Text style={styles.cardTitle}>当前状态</Text>
            <View style={styles.moodRow}>
              <Text style={styles.moodEmoji}>{moodEmoji}</Text>
              <View>
                <Text style={styles.moodLabel}>{mood}</Text>
                <Text style={styles.moodSub}>
                  {profile?.emotion?.style_modifier || "平静中"}
                </Text>
              </View>
            </View>
          </View>

          {/* Streak */}
          <View style={styles.card}>
            <Text style={styles.cardTitle}>连续互动</Text>
            <View style={styles.streakRow}>
              <View style={styles.streakMain}>
                <Text style={styles.streakNum}>{streak}</Text>
                <Text style={styles.streakUnit}>天</Text>
              </View>
              <View style={styles.streakMeta}>
                <Text style={styles.streakMetaText}>
                  最长 {longestStreak} 天
                </Text>
                <Text style={styles.streakMetaText}>
                  下一里程碑 {nextMilestone} 天
                </Text>
              </View>
            </View>

            {/* Milestone dots */}
            <View style={styles.milestoneDots}>
              {STREAK_MILESTONES.map((m) => (
                <View
                  key={m}
                  style={[
                    styles.milestoneDot,
                    streak >= m && styles.milestoneDotDone,
                  ]}
                >
                  <Text
                    style={[
                      styles.milestoneText,
                      streak >= m && styles.milestoneTextDone,
                    ]}
                  >
                    {m}
                  </Text>
                </View>
              ))}
            </View>
          </View>

          {/* Highlights */}
          {dashboard?.highlights && dashboard.highlights.length > 0 && (
            <View style={styles.card}>
              <Text style={styles.cardTitle}>本周亮点</Text>
              {dashboard.highlights.slice(0, 5).map((h: string, i: number) => (
                <Text key={i} style={styles.highlightItem}>
                  · {h}
                </Text>
              ))}
            </View>
          )}
        </View>
      )}

      {tab === "achieve" && (
        <View>
          <View style={styles.card}>
            <Text style={styles.cardTitle}>成就 {achieveCount}</Text>
            {achievements.length === 0 ? (
              <View style={styles.emptySection}>
                <Text style={styles.emptyEmoji}>🏆</Text>
                <Text style={styles.emptyText}>继续聊天，解锁成就</Text>
              </View>
            ) : (
              achievements.map((a: any, i: number) => (
                <View key={i} style={styles.achieveItem}>
                  <Text style={styles.achieveEmoji}>{a.emoji || "🎖️"}</Text>
                  <View style={styles.achieveInfo}>
                    <Text style={styles.achieveName}>{a.name}</Text>
                    <Text style={styles.achieveDesc}>{a.description}</Text>
                  </View>
                </View>
              ))
            )}
          </View>
        </View>
      )}

      {tab === "skills" && (
        <View>
          <View style={styles.card}>
            <Text style={styles.cardTitle}>技能树</Text>
            {skills.length === 0 ? (
              <View style={styles.emptySection}>
                <Text style={styles.emptyEmoji}>🔧</Text>
                <Text style={styles.emptyText}>
                  提升羁绊等级，解锁更多技能
                </Text>
              </View>
            ) : (
              skills.map((s: any, i: number) => (
                <View key={i} style={styles.skillItem}>
                  <View style={styles.skillHeader}>
                    <Text style={styles.skillName}>{s.name}</Text>
                    <Text
                      style={[
                        styles.skillBadge,
                        s.available
                          ? styles.skillAvailable
                          : styles.skillLocked,
                      ]}
                    >
                      {s.available
                        ? "可用"
                        : `Lv.${s.min_bond || "?"} 解锁`}
                    </Text>
                  </View>
                  <Text style={styles.skillDesc}>{s.description}</Text>
                </View>
              ))
            )}
          </View>

          {/* Autonomy */}
          {dashboard?.autonomy && (
            <View style={styles.card}>
              <Text style={styles.cardTitle}>自治能力</Text>
              <View style={styles.autonomyRow}>
                <Text style={styles.autonomyLabel}>等级</Text>
                <Text style={styles.autonomyValue}>
                  {dashboard.autonomy.level_name || "观察者"}
                </Text>
              </View>
              <View style={styles.autonomyRow}>
                <Text style={styles.autonomyLabel}>状态</Text>
                <Text style={styles.autonomyValue}>
                  {dashboard.autonomy.state || "IDLE"}
                </Text>
              </View>
              <View style={styles.autonomyRow}>
                <Text style={styles.autonomyLabel}>今日行动</Text>
                <Text style={styles.autonomyValue}>
                  {dashboard.autonomy.actions_today ?? 0}/
                  {dashboard.autonomy.daily_budget ?? 50}
                </Text>
              </View>
            </View>
          )}
        </View>
      )}
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

  // Bond hero
  bondHero: {
    alignItems: "center",
    padding: spacing.lg,
    marginHorizontal: spacing.lg,
    backgroundColor: colors.bgCard,
    borderRadius: borderRadius.lg,
    borderWidth: 1,
    borderColor: colors.border,
    marginBottom: spacing.lg,
  },
  bondEmoji: { fontSize: 56, marginBottom: spacing.sm },
  bondLevel: {
    fontSize: fontSize.xl,
    fontWeight: "700",
    color: colors.bondGreen,
  },
  bondDesc: {
    fontSize: fontSize.sm,
    color: colors.textMuted,
    marginTop: spacing.xs,
  },
  progressOuter: {
    width: "100%",
    height: 6,
    backgroundColor: colors.bgInput,
    borderRadius: 3,
    marginTop: spacing.md,
    overflow: "hidden",
  },
  progressInner: {
    height: "100%",
    backgroundColor: colors.bondGreen,
    borderRadius: 3,
  },
  progressText: {
    fontSize: fontSize.xs,
    color: colors.textMuted,
    marginTop: spacing.xs,
  },

  // Tabs
  tabBar: {
    flexDirection: "row",
    marginHorizontal: spacing.lg,
    marginBottom: spacing.md,
    backgroundColor: colors.bgCard,
    borderRadius: borderRadius.md,
    padding: 2,
  },
  tabItem: {
    flex: 1,
    paddingVertical: spacing.sm,
    alignItems: "center",
    borderRadius: borderRadius.sm,
  },
  tabActive: { backgroundColor: colors.bgInput },
  tabText: { fontSize: fontSize.md, color: colors.textMuted },
  tabTextActive: { color: colors.accent, fontWeight: "600" },

  // Cards
  card: {
    marginHorizontal: spacing.lg,
    marginBottom: spacing.md,
    backgroundColor: colors.bgCard,
    borderRadius: borderRadius.lg,
    padding: spacing.md,
    borderWidth: 1,
    borderColor: colors.border,
  },
  cardTitle: {
    fontSize: fontSize.md,
    fontWeight: "600",
    color: colors.accent,
    marginBottom: spacing.md,
  },

  // Mood
  moodRow: { flexDirection: "row", alignItems: "center", gap: spacing.md },
  moodEmoji: { fontSize: 36 },
  moodLabel: {
    fontSize: fontSize.lg,
    fontWeight: "600",
    color: colors.textPrimary,
    textTransform: "capitalize",
  },
  moodSub: { fontSize: fontSize.sm, color: colors.textSecondary },

  // Streak
  streakRow: {
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "center",
  },
  streakMain: { flexDirection: "row", alignItems: "baseline" },
  streakNum: {
    fontSize: fontSize.title,
    fontWeight: "700",
    color: colors.streakOrange,
  },
  streakUnit: {
    fontSize: fontSize.lg,
    color: colors.streakOrange,
    marginLeft: spacing.xs,
  },
  streakMeta: { alignItems: "flex-end" },
  streakMetaText: { fontSize: fontSize.xs, color: colors.textMuted },
  milestoneDots: {
    flexDirection: "row",
    justifyContent: "space-between",
    marginTop: spacing.md,
  },
  milestoneDot: {
    width: 40,
    height: 40,
    borderRadius: 20,
    backgroundColor: colors.bgInput,
    justifyContent: "center",
    alignItems: "center",
  },
  milestoneDotDone: { backgroundColor: colors.streakOrange },
  milestoneText: { fontSize: fontSize.xs, color: colors.textMuted },
  milestoneTextDone: { color: colors.bg, fontWeight: "700" },

  // Highlights
  highlightItem: {
    fontSize: fontSize.sm,
    color: colors.textSecondary,
    lineHeight: 22,
    marginBottom: 2,
  },

  // Empty
  emptySection: { alignItems: "center", paddingVertical: spacing.lg },
  emptyEmoji: { fontSize: 36, marginBottom: spacing.sm },
  emptyText: { fontSize: fontSize.md, color: colors.textMuted },

  // Achievements
  achieveItem: {
    flexDirection: "row",
    alignItems: "center",
    paddingVertical: spacing.sm,
    borderBottomWidth: 1,
    borderBottomColor: colors.border,
  },
  achieveEmoji: { fontSize: 28, marginRight: spacing.md },
  achieveInfo: { flex: 1 },
  achieveName: {
    fontSize: fontSize.md,
    fontWeight: "600",
    color: colors.textPrimary,
  },
  achieveDesc: { fontSize: fontSize.sm, color: colors.textSecondary },

  // Skills
  skillItem: {
    paddingVertical: spacing.sm,
    borderBottomWidth: 1,
    borderBottomColor: colors.border,
  },
  skillHeader: {
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "center",
  },
  skillName: {
    fontSize: fontSize.md,
    fontWeight: "600",
    color: colors.textPrimary,
  },
  skillBadge: {
    fontSize: fontSize.xs,
    paddingHorizontal: spacing.sm,
    paddingVertical: 2,
    borderRadius: borderRadius.sm,
    overflow: "hidden",
  },
  skillAvailable: { backgroundColor: colors.bondGreen, color: colors.bg },
  skillLocked: { backgroundColor: colors.bgInput, color: colors.textMuted },
  skillDesc: {
    fontSize: fontSize.sm,
    color: colors.textSecondary,
    marginTop: spacing.xs,
  },

  // Autonomy
  autonomyRow: {
    flexDirection: "row",
    justifyContent: "space-between",
    paddingVertical: spacing.sm,
    borderBottomWidth: 1,
    borderBottomColor: colors.border,
  },
  autonomyLabel: { fontSize: fontSize.md, color: colors.textSecondary },
  autonomyValue: {
    fontSize: fontSize.md,
    fontWeight: "600",
    color: colors.textPrimary,
  },
});
