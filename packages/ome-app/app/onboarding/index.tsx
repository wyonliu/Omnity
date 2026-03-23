import { useState } from "react";
import {
  View,
  Text,
  TextInput,
  TouchableOpacity,
  StyleSheet,
  KeyboardAvoidingView,
  Platform,
  ScrollView,
} from "react-native";
import { router } from "expo-router";
import { register } from "../../lib/api";
import { colors, spacing, fontSize, borderRadius } from "../../lib/theme";

const PERSONALITY_OPTIONS = [
  { label: "好奇探索者", value: "curious", emoji: "🔍" },
  { label: "务实行动派", value: "pragmatic", emoji: "🎯" },
  { label: "温暖陪伴者", value: "warm", emoji: "🤗" },
  { label: "创意冒险家", value: "creative", emoji: "✨" },
];

const STYLE_OPTIONS = [
  { label: "简洁直接", value: "concise and direct" },
  { label: "温暖细腻", value: "warm and detailed" },
  { label: "幽默轻松", value: "humorous and casual" },
];

export default function OnboardingScreen() {
  const [step, setStep] = useState(0);
  const [name, setName] = useState("");
  const [selectedTraits, setSelectedTraits] = useState<string[]>([]);
  const [style, setStyle] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  const toggleTrait = (t: string) => {
    setSelectedTraits((prev) =>
      prev.includes(t) ? prev.filter((x) => x !== t) : [...prev, t]
    );
  };

  const handleCreate = async () => {
    if (!name.trim()) {
      setError("给你的 Ome 起个名字吧");
      return;
    }
    setLoading(true);
    setError("");
    try {
      // Use name as user_id for simplicity
      const userId = name.trim().toLowerCase().replace(/\s+/g, "_");
      await register({
        user_id: userId,
        password: userId + "_ome", // MVP: simple password
        name: name.trim(),
        traits: selectedTraits.length > 0 ? selectedTraits : ["curious"],
        style: style || "direct",
      });
      router.replace("/(tabs)");
    } catch (e: any) {
      setError(e.message || "创建失败，请重试");
    } finally {
      setLoading(false);
    }
  };

  return (
    <KeyboardAvoidingView
      behavior={Platform.OS === "ios" ? "padding" : "height"}
      style={styles.container}
    >
      <ScrollView
        contentContainerStyle={styles.scroll}
        keyboardShouldPersistTaps="handled"
      >
        {/* Progress dots */}
        <View style={styles.dots}>
          {[0, 1, 2].map((i) => (
            <View
              key={i}
              style={[styles.dot, i === step && styles.dotActive]}
            />
          ))}
        </View>

        {step === 0 && (
          <View style={styles.stepContainer}>
            <Text style={styles.title}>你好</Text>
            <Text style={styles.subtitle}>
              让我们创建你的 Ome{"\n"}—— 另一个你
            </Text>
            <View style={styles.inputGroup}>
              <Text style={styles.label}>你的名字</Text>
              <TextInput
                style={styles.input}
                value={name}
                onChangeText={setName}
                placeholder="输入你的名字"
                placeholderTextColor={colors.textMuted}
                autoFocus
              />
            </View>
            <TouchableOpacity
              style={[styles.btn, !name.trim() && styles.btnDisabled]}
              onPress={() => name.trim() && setStep(1)}
              disabled={!name.trim()}
            >
              <Text style={styles.btnText}>继续</Text>
            </TouchableOpacity>
          </View>
        )}

        {step === 1 && (
          <View style={styles.stepContainer}>
            <Text style={styles.title}>你是什么样的人？</Text>
            <Text style={styles.subtitle}>选择最像你的（可多选）</Text>
            <View style={styles.optionGrid}>
              {PERSONALITY_OPTIONS.map((opt) => (
                <TouchableOpacity
                  key={opt.value}
                  style={[
                    styles.optionCard,
                    selectedTraits.includes(opt.value) &&
                      styles.optionCardActive,
                  ]}
                  onPress={() => toggleTrait(opt.value)}
                >
                  <Text style={styles.optionEmoji}>{opt.emoji}</Text>
                  <Text style={styles.optionLabel}>{opt.label}</Text>
                </TouchableOpacity>
              ))}
            </View>
            <TouchableOpacity style={styles.btn} onPress={() => setStep(2)}>
              <Text style={styles.btnText}>继续</Text>
            </TouchableOpacity>
          </View>
        )}

        {step === 2 && (
          <View style={styles.stepContainer}>
            <Text style={styles.title}>你说话什么风格？</Text>
            <Text style={styles.subtitle}>Ome 会学习你的语气</Text>
            {STYLE_OPTIONS.map((opt) => (
              <TouchableOpacity
                key={opt.value}
                style={[
                  styles.styleOption,
                  style === opt.value && styles.styleOptionActive,
                ]}
                onPress={() => setStyle(opt.value)}
              >
                <Text
                  style={[
                    styles.styleText,
                    style === opt.value && styles.styleTextActive,
                  ]}
                >
                  {opt.label}
                </Text>
              </TouchableOpacity>
            ))}

            {error ? <Text style={styles.error}>{error}</Text> : null}

            <TouchableOpacity
              style={[styles.btn, styles.btnPrimary, loading && styles.btnDisabled]}
              onPress={handleCreate}
              disabled={loading}
            >
              <Text style={styles.btnText}>
                {loading ? "正在创建..." : "创建我的 Ome"}
              </Text>
            </TouchableOpacity>
          </View>
        )}
      </ScrollView>
    </KeyboardAvoidingView>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: colors.bg },
  scroll: { flexGrow: 1, justifyContent: "center", padding: spacing.xl },
  dots: { flexDirection: "row", justifyContent: "center", marginBottom: spacing.xxl },
  dot: {
    width: 8, height: 8, borderRadius: 4,
    backgroundColor: colors.textMuted, marginHorizontal: 4,
  },
  dotActive: { backgroundColor: colors.accent, width: 24 },
  stepContainer: { alignItems: "center" },
  title: {
    fontSize: fontSize.title, fontWeight: "700",
    color: colors.textPrimary, marginBottom: spacing.sm, textAlign: "center",
  },
  subtitle: {
    fontSize: fontSize.lg, color: colors.textSecondary,
    marginBottom: spacing.xl, textAlign: "center", lineHeight: 26,
  },
  inputGroup: { width: "100%", marginBottom: spacing.xl },
  label: { fontSize: fontSize.sm, color: colors.textSecondary, marginBottom: spacing.sm },
  input: {
    backgroundColor: colors.bgInput, borderRadius: borderRadius.md,
    padding: spacing.md, fontSize: fontSize.lg,
    color: colors.textPrimary, borderWidth: 1, borderColor: colors.border,
  },
  btn: {
    backgroundColor: colors.bgCard, paddingVertical: spacing.md,
    paddingHorizontal: spacing.xl, borderRadius: borderRadius.lg,
    marginTop: spacing.lg, width: "100%", alignItems: "center",
    borderWidth: 1, borderColor: colors.border,
  },
  btnPrimary: { backgroundColor: colors.accent, borderColor: colors.accent },
  btnDisabled: { opacity: 0.5 },
  btnText: { fontSize: fontSize.lg, fontWeight: "600", color: colors.textPrimary },
  optionGrid: {
    flexDirection: "row", flexWrap: "wrap",
    justifyContent: "center", gap: spacing.md, marginBottom: spacing.lg,
  },
  optionCard: {
    width: 140, padding: spacing.md, borderRadius: borderRadius.lg,
    backgroundColor: colors.bgCard, alignItems: "center",
    borderWidth: 1, borderColor: colors.border,
  },
  optionCardActive: { borderColor: colors.accent, backgroundColor: colors.bgInput },
  optionEmoji: { fontSize: 32, marginBottom: spacing.sm },
  optionLabel: { fontSize: fontSize.md, color: colors.textPrimary, fontWeight: "500" },
  styleOption: {
    width: "100%", padding: spacing.md, borderRadius: borderRadius.md,
    backgroundColor: colors.bgCard, marginBottom: spacing.sm,
    borderWidth: 1, borderColor: colors.border,
  },
  styleOptionActive: { borderColor: colors.accent },
  styleText: { fontSize: fontSize.lg, color: colors.textSecondary, textAlign: "center" },
  styleTextActive: { color: colors.accent, fontWeight: "600" },
  error: { color: colors.error, fontSize: fontSize.sm, marginTop: spacing.sm },
});
