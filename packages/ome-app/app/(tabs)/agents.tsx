/**
 * Agents screen — OmeTown square.
 *
 * Browse other Omes, introduce yourself, exchange messages.
 * Foundation for the symbiotic agent world.
 */
import { useState, useCallback } from "react";
import {
  View,
  Text,
  StyleSheet,
  FlatList,
  TouchableOpacity,
  TextInput,
  Modal,
  ActivityIndicator,
  RefreshControl,
} from "react-native";
import { useFocusEffect } from "expo-router";
import {
  getAgentDirectory,
  introduceToAgent,
  messageAgent,
  getAgentProfile,
} from "../../lib/api";
import { colors, spacing, fontSize, borderRadius } from "../../lib/theme";

interface AgentInfo {
  user_id: string;
  name: string;
  bond_level: number;
  mood: string;
  mood_emoji: string;
}

export default function AgentsScreen() {
  const [agents, setAgents] = useState<AgentInfo[]>([]);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);

  // Chat modal state
  const [selectedAgent, setSelectedAgent] = useState<AgentInfo | null>(null);
  const [chatInput, setChatInput] = useState("");
  const [chatMessages, setChatMessages] = useState<
    { role: "me" | "them"; text: string }[]
  >([]);
  const [chatSending, setChatSending] = useState(false);

  const loadAgents = useCallback(async () => {
    try {
      const result = await getAgentDirectory();
      setAgents(result.agents || []);
    } catch (err) {
      console.log("Agent directory error:", err);
    } finally {
      setLoading(false);
    }
  }, []);

  useFocusEffect(
    useCallback(() => {
      loadAgents();
    }, [loadAgents])
  );

  const onRefresh = async () => {
    setRefreshing(true);
    await loadAgents();
    setRefreshing(false);
  };

  const handleIntroduce = async (agent: AgentInfo) => {
    setSelectedAgent(agent);
    setChatMessages([]);
    setChatSending(true);

    try {
      const result = await introduceToAgent(agent.user_id, "你好！很高兴认识你");
      setChatMessages([
        {
          role: "me",
          text: `[我的 Ome 向 ${agent.name} 打了招呼]`,
        },
        {
          role: "them",
          text: `${result.their_mood_emoji} ${result.their_name} 已收到你的问候`,
        },
      ]);
    } catch (e: any) {
      setChatMessages([
        { role: "them", text: `连接失败: ${e.message}` },
      ]);
    } finally {
      setChatSending(false);
    }
  };

  const handleSendMessage = async () => {
    if (!selectedAgent || !chatInput.trim() || chatSending) return;

    const text = chatInput.trim();
    setChatInput("");
    setChatMessages((prev) => [...prev, { role: "me", text }]);
    setChatSending(true);

    try {
      const result = await messageAgent(selectedAgent.user_id, text);
      setChatMessages((prev) => [
        ...prev,
        {
          role: "them",
          text: `${result.their_mood_emoji} ${result.their_reply}`,
        },
      ]);
    } catch (e: any) {
      setChatMessages((prev) => [
        ...prev,
        { role: "them", text: `发送失败: ${e.message}` },
      ]);
    } finally {
      setChatSending(false);
    }
  };

  const renderAgent = ({ item }: { item: AgentInfo }) => (
    <TouchableOpacity
      style={styles.agentCard}
      onPress={() => handleIntroduce(item)}
    >
      <Text style={styles.agentEmoji}>{item.mood_emoji}</Text>
      <View style={styles.agentInfo}>
        <Text style={styles.agentName}>{item.name}</Text>
        <Text style={styles.agentMeta}>
          Lv.{item.bond_level} · {item.mood}
        </Text>
      </View>
      <View style={styles.agentAction}>
        <Text style={styles.agentActionText}>对话</Text>
      </View>
    </TouchableOpacity>
  );

  return (
    <View style={styles.container}>
      {/* Header */}
      <View style={styles.header}>
        <Text style={styles.headerTitle}>🏘️ 广场</Text>
        <Text style={styles.headerSub}>
          OmeTown · {agents.length} 个 Ome 在线
        </Text>
      </View>

      {loading ? (
        <View style={styles.center}>
          <ActivityIndicator size="large" color={colors.accent} />
        </View>
      ) : agents.length === 0 ? (
        <View style={styles.center}>
          <Text style={styles.emptyEmoji}>🌍</Text>
          <Text style={styles.emptyTitle}>还没有其他 Ome</Text>
          <Text style={styles.emptyText}>
            当更多人创建自己的 Ome，这里就会热闹起来。{"\n"}
            你的 Ome 将能和他们交朋友、交换记忆。
          </Text>
        </View>
      ) : (
        <FlatList
          data={agents}
          renderItem={renderAgent}
          keyExtractor={(item) => item.user_id}
          contentContainerStyle={styles.list}
          refreshControl={
            <RefreshControl
              refreshing={refreshing}
              onRefresh={onRefresh}
              tintColor={colors.accent}
            />
          }
        />
      )}

      {/* Agent chat modal */}
      <Modal
        visible={!!selectedAgent}
        transparent
        animationType="slide"
        onRequestClose={() => setSelectedAgent(null)}
      >
        <View style={styles.modalContainer}>
          <View style={styles.modalContent}>
            {/* Modal header */}
            <View style={styles.modalHeader}>
              <View>
                <Text style={styles.modalTitle}>
                  与 {selectedAgent?.name} 对话
                </Text>
                <Text style={styles.modalSub}>
                  你的 Ome 代表你发言
                </Text>
              </View>
              <TouchableOpacity onPress={() => setSelectedAgent(null)}>
                <Text style={styles.modalClose}>✕</Text>
              </TouchableOpacity>
            </View>

            {/* Messages */}
            <FlatList
              data={chatMessages}
              renderItem={({ item }) => (
                <View
                  style={[
                    styles.chatMsg,
                    item.role === "me" ? styles.chatMsgMe : styles.chatMsgThem,
                  ]}
                >
                  <Text
                    style={[
                      styles.chatMsgText,
                      item.role === "me" && styles.chatMsgTextMe,
                    ]}
                  >
                    {item.text}
                  </Text>
                </View>
              )}
              keyExtractor={(_, i) => i.toString()}
              contentContainerStyle={styles.chatList}
            />

            {/* Input */}
            <View style={styles.chatInputBar}>
              <TextInput
                style={styles.chatInput}
                value={chatInput}
                onChangeText={setChatInput}
                placeholder="让你的 Ome 说..."
                placeholderTextColor={colors.textMuted}
                onSubmitEditing={handleSendMessage}
              />
              <TouchableOpacity
                style={[
                  styles.chatSendBtn,
                  (!chatInput.trim() || chatSending) && styles.btnDisabled,
                ]}
                onPress={handleSendMessage}
                disabled={!chatInput.trim() || chatSending}
              >
                <Text style={styles.chatSendText}>
                  {chatSending ? "···" : "→"}
                </Text>
              </TouchableOpacity>
            </View>
          </View>
        </View>
      </Modal>
    </View>
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

  center: {
    flex: 1,
    justifyContent: "center",
    alignItems: "center",
    padding: spacing.xl,
  },
  emptyEmoji: { fontSize: 56, marginBottom: spacing.md },
  emptyTitle: {
    fontSize: fontSize.xl,
    fontWeight: "700",
    color: colors.textPrimary,
    marginBottom: spacing.sm,
  },
  emptyText: {
    fontSize: fontSize.md,
    color: colors.textMuted,
    textAlign: "center",
    lineHeight: 22,
  },

  list: { padding: spacing.md },
  agentCard: {
    flexDirection: "row",
    alignItems: "center",
    backgroundColor: colors.bgCard,
    borderRadius: borderRadius.lg,
    padding: spacing.md,
    marginBottom: spacing.md,
    borderWidth: 1,
    borderColor: colors.border,
  },
  agentEmoji: { fontSize: 32, marginRight: spacing.md },
  agentInfo: { flex: 1 },
  agentName: {
    fontSize: fontSize.lg,
    fontWeight: "600",
    color: colors.textPrimary,
  },
  agentMeta: { fontSize: fontSize.sm, color: colors.textSecondary },
  agentAction: {
    backgroundColor: colors.accent,
    paddingHorizontal: spacing.md,
    paddingVertical: spacing.sm,
    borderRadius: borderRadius.md,
  },
  agentActionText: {
    fontSize: fontSize.sm,
    fontWeight: "600",
    color: colors.bg,
  },

  // Modal
  modalContainer: {
    flex: 1,
    backgroundColor: colors.bg,
  },
  modalContent: { flex: 1 },
  modalHeader: {
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "center",
    paddingTop: 56,
    paddingHorizontal: spacing.lg,
    paddingBottom: spacing.md,
    borderBottomWidth: 1,
    borderBottomColor: colors.border,
  },
  modalTitle: {
    fontSize: fontSize.xl,
    fontWeight: "700",
    color: colors.textPrimary,
  },
  modalSub: { fontSize: fontSize.sm, color: colors.textMuted },
  modalClose: {
    fontSize: fontSize.xl,
    color: colors.textMuted,
    padding: spacing.sm,
  },

  chatList: { padding: spacing.md, paddingBottom: spacing.lg },
  chatMsg: {
    maxWidth: "80%",
    padding: spacing.md,
    borderRadius: borderRadius.lg,
    marginBottom: spacing.sm,
  },
  chatMsgMe: {
    alignSelf: "flex-end",
    backgroundColor: colors.accent,
    borderBottomRightRadius: 4,
  },
  chatMsgThem: {
    alignSelf: "flex-start",
    backgroundColor: colors.bgCard,
    borderBottomLeftRadius: 4,
    borderWidth: 1,
    borderColor: colors.border,
  },
  chatMsgText: { fontSize: fontSize.md, color: colors.textPrimary, lineHeight: 22 },
  chatMsgTextMe: { color: colors.bg },

  chatInputBar: {
    flexDirection: "row",
    alignItems: "flex-end",
    padding: spacing.md,
    paddingBottom: spacing.xl,
    borderTopWidth: 1,
    borderTopColor: colors.border,
    backgroundColor: colors.bgCard,
  },
  chatInput: {
    flex: 1,
    backgroundColor: colors.bgInput,
    borderRadius: borderRadius.lg,
    padding: spacing.md,
    fontSize: fontSize.md,
    color: colors.textPrimary,
    marginRight: spacing.sm,
  },
  chatSendBtn: {
    width: 44,
    height: 44,
    borderRadius: 22,
    backgroundColor: colors.accent,
    justifyContent: "center",
    alignItems: "center",
  },
  chatSendText: { fontSize: fontSize.xl, fontWeight: "700", color: colors.bg },
  btnDisabled: { opacity: 0.4 },
});
