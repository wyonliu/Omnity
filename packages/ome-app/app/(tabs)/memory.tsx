import { useState, useCallback } from "react";
import {
  View,
  Text,
  TextInput,
  TouchableOpacity,
  FlatList,
  StyleSheet,
  KeyboardAvoidingView,
  Platform,
  ActivityIndicator,
} from "react-native";
import { useFocusEffect } from "expo-router";
import { recall, remember } from "../../lib/api";
import { colors, spacing, fontSize, borderRadius } from "../../lib/theme";

interface Memory {
  id: string;
  text: string;
  score?: number;
  timestamp?: string;
  tags?: string[];
}

export default function MemoryScreen() {
  const [query, setQuery] = useState("");
  const [memories, setMemories] = useState<Memory[]>([]);
  const [loading, setLoading] = useState(false);
  const [addMode, setAddMode] = useState(false);
  const [newMemory, setNewMemory] = useState("");
  const [saving, setSaving] = useState(false);
  const [hasSearched, setHasSearched] = useState(false);

  // Load recent memories on focus
  useFocusEffect(
    useCallback(() => {
      if (!hasSearched) {
        handleSearch("最近的记忆", true);
      }
    }, [hasSearched])
  );

  const handleSearch = async (q?: string, silent = false) => {
    const searchQuery = q || query.trim();
    if (!searchQuery) return;

    if (!silent) setHasSearched(true);
    setLoading(true);
    try {
      const result = await recall(searchQuery, 20);
      const items = (result.memories || result.results || []).map(
        (m: any, i: number) => ({
          id: m.id || `mem-${i}`,
          text: m.text || m.content || "",
          score: m.score,
          timestamp: m.timestamp || m.created_at,
          tags: m.tags,
        })
      );
      setMemories(items);
    } catch (e: any) {
      console.log("Recall error:", e.message);
    } finally {
      setLoading(false);
    }
  };

  const handleAdd = async () => {
    const text = newMemory.trim();
    if (!text || saving) return;

    setSaving(true);
    try {
      await remember(text);
      setNewMemory("");
      setAddMode(false);
      // Refresh with recent
      handleSearch("最近的记忆", true);
    } catch (e: any) {
      console.log("Remember error:", e.message);
    } finally {
      setSaving(false);
    }
  };

  const renderMemory = ({ item }: { item: Memory }) => (
    <View style={styles.memoryCard}>
      <Text style={styles.memoryText}>{item.text}</Text>
      <View style={styles.memoryMeta}>
        {item.score !== undefined && (
          <Text style={styles.metaText}>
            相关度 {(item.score * 100).toFixed(0)}%
          </Text>
        )}
        {item.tags && item.tags.length > 0 && (
          <View style={styles.tagRow}>
            {item.tags.map((tag, i) => (
              <View key={i} style={styles.tag}>
                <Text style={styles.tagText}>{tag}</Text>
              </View>
            ))}
          </View>
        )}
      </View>
    </View>
  );

  return (
    <KeyboardAvoidingView
      style={styles.container}
      behavior={Platform.OS === "ios" ? "padding" : "height"}
      keyboardVerticalOffset={90}
    >
      {/* Header */}
      <View style={styles.header}>
        <Text style={styles.headerTitle}>🧠 记忆</Text>
        <Text style={styles.headerSub}>
          {memories.length > 0
            ? `${memories.length} 条记忆`
            : "搜索 Ome 的记忆"}
        </Text>
      </View>

      {/* Search bar */}
      <View style={styles.searchBar}>
        <TextInput
          style={styles.searchInput}
          value={query}
          onChangeText={setQuery}
          placeholder="搜索记忆..."
          placeholderTextColor={colors.textMuted}
          onSubmitEditing={() => handleSearch()}
          returnKeyType="search"
        />
        <TouchableOpacity
          style={[styles.searchBtn, !query.trim() && styles.btnDisabled]}
          onPress={() => handleSearch()}
          disabled={!query.trim()}
        >
          <Text style={styles.searchBtnText}>搜</Text>
        </TouchableOpacity>
        <TouchableOpacity
          style={styles.addBtn}
          onPress={() => setAddMode(!addMode)}
        >
          <Text style={styles.addBtnText}>{addMode ? "×" : "+"}</Text>
        </TouchableOpacity>
      </View>

      {/* Add memory form */}
      {addMode && (
        <View style={styles.addForm}>
          <TextInput
            style={styles.addInput}
            value={newMemory}
            onChangeText={setNewMemory}
            placeholder="告诉 Ome 一件事..."
            placeholderTextColor={colors.textMuted}
            multiline
            maxLength={2000}
            autoFocus
          />
          <TouchableOpacity
            style={[
              styles.saveBtn,
              (!newMemory.trim() || saving) && styles.btnDisabled,
            ]}
            onPress={handleAdd}
            disabled={!newMemory.trim() || saving}
          >
            <Text style={styles.saveBtnText}>
              {saving ? "保存中..." : "记住"}
            </Text>
          </TouchableOpacity>
        </View>
      )}

      {/* Memory list */}
      {loading ? (
        <View style={styles.center}>
          <ActivityIndicator size="large" color={colors.accent} />
        </View>
      ) : memories.length === 0 ? (
        <View style={styles.center}>
          <Text style={styles.emptyEmoji}>🌊</Text>
          <Text style={styles.emptyText}>
            {hasSearched ? "没有找到相关记忆" : "和 Ome 聊天，记忆会自动积累"}
          </Text>
        </View>
      ) : (
        <FlatList
          data={memories}
          renderItem={renderMemory}
          keyExtractor={(item) => item.id}
          contentContainerStyle={styles.list}
          showsVerticalScrollIndicator={false}
        />
      )}
    </KeyboardAvoidingView>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: colors.bg },

  header: {
    paddingTop: 56,
    paddingHorizontal: spacing.lg,
    paddingBottom: spacing.md,
    borderBottomWidth: 1,
    borderBottomColor: colors.border,
  },
  headerTitle: {
    fontSize: fontSize.xl,
    fontWeight: "700",
    color: colors.textPrimary,
  },
  headerSub: {
    fontSize: fontSize.sm,
    color: colors.textMuted,
    marginTop: spacing.xs,
  },

  searchBar: {
    flexDirection: "row",
    padding: spacing.md,
    gap: spacing.sm,
  },
  searchInput: {
    flex: 1,
    backgroundColor: colors.bgInput,
    borderRadius: borderRadius.lg,
    padding: spacing.md,
    fontSize: fontSize.md,
    color: colors.textPrimary,
  },
  searchBtn: {
    width: 44,
    height: 44,
    borderRadius: borderRadius.md,
    backgroundColor: colors.accent,
    justifyContent: "center",
    alignItems: "center",
  },
  searchBtnText: {
    fontSize: fontSize.md,
    fontWeight: "700",
    color: colors.bg,
  },
  addBtn: {
    width: 44,
    height: 44,
    borderRadius: 22,
    backgroundColor: colors.bgCard,
    justifyContent: "center",
    alignItems: "center",
    borderWidth: 1,
    borderColor: colors.border,
  },
  addBtnText: {
    fontSize: fontSize.xl,
    color: colors.accent,
    fontWeight: "600",
  },
  btnDisabled: { opacity: 0.4 },

  addForm: {
    marginHorizontal: spacing.md,
    marginBottom: spacing.md,
    backgroundColor: colors.bgCard,
    borderRadius: borderRadius.lg,
    padding: spacing.md,
    borderWidth: 1,
    borderColor: colors.accent,
  },
  addInput: {
    fontSize: fontSize.md,
    color: colors.textPrimary,
    minHeight: 60,
    textAlignVertical: "top",
  },
  saveBtn: {
    alignSelf: "flex-end",
    backgroundColor: colors.accent,
    paddingVertical: spacing.sm,
    paddingHorizontal: spacing.lg,
    borderRadius: borderRadius.md,
    marginTop: spacing.sm,
  },
  saveBtnText: {
    fontSize: fontSize.md,
    fontWeight: "600",
    color: colors.bg,
  },

  list: { padding: spacing.md, paddingBottom: spacing.xxl },

  memoryCard: {
    backgroundColor: colors.bgCard,
    borderRadius: borderRadius.lg,
    padding: spacing.md,
    marginBottom: spacing.md,
    borderWidth: 1,
    borderColor: colors.border,
  },
  memoryText: {
    fontSize: fontSize.md,
    color: colors.textPrimary,
    lineHeight: 22,
  },
  memoryMeta: {
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "center",
    marginTop: spacing.sm,
  },
  metaText: { fontSize: fontSize.xs, color: colors.textMuted },
  tagRow: { flexDirection: "row", gap: spacing.xs },
  tag: {
    backgroundColor: colors.bgInput,
    borderRadius: borderRadius.sm,
    paddingHorizontal: spacing.sm,
    paddingVertical: 2,
  },
  tagText: { fontSize: fontSize.xs, color: colors.textSecondary },

  center: { flex: 1, justifyContent: "center", alignItems: "center" },
  emptyEmoji: { fontSize: 48, marginBottom: spacing.md },
  emptyText: {
    fontSize: fontSize.md,
    color: colors.textMuted,
    textAlign: "center",
  },
});
