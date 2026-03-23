/**
 * Chat screen — authenticated user's main conversation with Ome.
 * Supports streaming (token-by-token) and mirror mode.
 */
import { useState, useRef, useEffect } from "react";
import {
  View,
  Text,
  TextInput,
  TouchableOpacity,
  FlatList,
  StyleSheet,
  KeyboardAvoidingView,
  Platform,
} from "react-native";
import { useLocalSearchParams } from "expo-router";
import AsyncStorage from "@react-native-async-storage/async-storage";
import { chat, mirror, chatStream } from "../../lib/api";
import { colors, spacing, fontSize, borderRadius } from "../../lib/theme";

interface Message {
  id: string;
  role: "user" | "ome";
  text: string;
  mood_emoji?: string;
  streaming?: boolean;
}

export default function ChatScreen() {
  const params = useLocalSearchParams<{ mode?: string }>();
  const isMirror = params.mode === "mirror";

  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState("");
  const [sending, setSending] = useState(false);
  const [name, setName] = useState("Ome");
  const flatListRef = useRef<FlatList>(null);

  useEffect(() => {
    AsyncStorage.getItem("ome_name").then((n) => n && setName(n));
    setMessages([
      {
        id: "welcome",
        role: "ome",
        text: isMirror
          ? `镜像模式：我会用${name || "你"}的语气说话。试试看？`
          : `嗨！有什么想聊的？`,
        mood_emoji: "😊",
      },
    ]);
  }, [isMirror]);

  const send = async () => {
    const text = input.trim();
    if (!text || sending) return;

    const userMsg: Message = { id: Date.now().toString(), role: "user", text };
    setMessages((prev) => [...prev, userMsg]);
    setInput("");
    setSending(true);

    if (isMirror) {
      // Mirror mode — no streaming
      try {
        const result = await mirror(text);
        setMessages((prev) => [
          ...prev,
          {
            id: (Date.now() + 1).toString(),
            role: "ome",
            text: result.reply,
            mood_emoji: result.mood_emoji,
          },
        ]);
      } catch (e: any) {
        setMessages((prev) => [
          ...prev,
          {
            id: (Date.now() + 1).toString(),
            role: "ome",
            text: `连接失败: ${e.message}`,
          },
        ]);
      } finally {
        setSending(false);
      }
      return;
    }

    // Normal mode — try streaming first, fall back to regular
    const streamMsgId = (Date.now() + 1).toString();
    let streamedText = "";

    // Add empty streaming message
    setMessages((prev) => [
      ...prev,
      {
        id: streamMsgId,
        role: "ome",
        text: "",
        mood_emoji: "💭",
        streaming: true,
      },
    ]);

    try {
      await chatStream(text, {
        onToken: (token) => {
          streamedText += token;
          setMessages((prev) =>
            prev.map((m) =>
              m.id === streamMsgId ? { ...m, text: streamedText } : m
            )
          );
        },
        onDone: (result) => {
          setMessages((prev) =>
            prev.map((m) =>
              m.id === streamMsgId
                ? {
                    ...m,
                    text: result.full_reply,
                    mood_emoji: result.mood_emoji,
                    streaming: false,
                  }
                : m
            )
          );
          setSending(false);
        },
        onError: async (error) => {
          // Fallback to regular chat
          try {
            const result = await chat(text);
            setMessages((prev) =>
              prev.map((m) =>
                m.id === streamMsgId
                  ? {
                      ...m,
                      text: result.reply,
                      mood_emoji: result.mood_emoji,
                      streaming: false,
                    }
                  : m
              )
            );
          } catch (e2: any) {
            setMessages((prev) =>
              prev.map((m) =>
                m.id === streamMsgId
                  ? { ...m, text: `连接失败: ${e2.message}`, streaming: false }
                  : m
              )
            );
          }
          setSending(false);
        },
      });
    } catch {
      // chatStream itself threw before starting
      try {
        const result = await chat(text);
        setMessages((prev) =>
          prev.map((m) =>
            m.id === streamMsgId
              ? {
                  ...m,
                  text: result.reply,
                  mood_emoji: result.mood_emoji,
                  streaming: false,
                }
              : m
          )
        );
      } catch (e2: any) {
        setMessages((prev) =>
          prev.map((m) =>
            m.id === streamMsgId
              ? { ...m, text: `连接失败: ${e2.message}`, streaming: false }
              : m
          )
        );
      }
      setSending(false);
    }
  };

  const renderMessage = ({ item }: { item: Message }) => {
    const isUser = item.role === "user";
    return (
      <View style={[styles.msgRow, isUser && styles.msgRowUser]}>
        {!isUser && item.mood_emoji && (
          <Text style={styles.msgAvatar}>{item.mood_emoji}</Text>
        )}
        <View
          style={[styles.msgBubble, isUser ? styles.msgUser : styles.msgOme]}
        >
          <Text style={[styles.msgText, isUser && styles.msgTextUser]}>
            {item.text}
            {item.streaming && "▌"}
          </Text>
        </View>
      </View>
    );
  };

  return (
    <KeyboardAvoidingView
      style={styles.container}
      behavior={Platform.OS === "ios" ? "padding" : "height"}
      keyboardVerticalOffset={90}
    >
      {/* Header */}
      <View style={styles.header}>
        <Text style={styles.headerTitle}>
          {isMirror ? `🪞 镜像 · ${name}` : `💬 对话`}
        </Text>
        {isMirror && (
          <Text style={styles.headerSub}>Ome 正在用你的语气说话</Text>
        )}
      </View>

      {/* Messages */}
      <FlatList
        ref={flatListRef}
        data={messages}
        renderItem={renderMessage}
        keyExtractor={(item) => item.id}
        contentContainerStyle={styles.msgList}
        onContentSizeChange={() =>
          flatListRef.current?.scrollToEnd({ animated: true })
        }
      />

      {/* Input */}
      <View style={styles.inputBar}>
        <TextInput
          style={styles.input}
          value={input}
          onChangeText={setInput}
          placeholder={isMirror ? "和自己聊聊..." : "说点什么..."}
          placeholderTextColor={colors.textMuted}
          multiline
          maxLength={2000}
          onSubmitEditing={send}
        />
        <TouchableOpacity
          style={[
            styles.sendBtn,
            (!input.trim() || sending) && styles.sendBtnDisabled,
          ]}
          onPress={send}
          disabled={!input.trim() || sending}
        >
          <Text style={styles.sendText}>{sending ? "···" : "→"}</Text>
        </TouchableOpacity>
      </View>
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

  msgList: { padding: spacing.md, paddingBottom: spacing.lg },
  msgRow: {
    flexDirection: "row",
    marginBottom: spacing.md,
    alignItems: "flex-end",
  },
  msgRowUser: { justifyContent: "flex-end" },
  msgAvatar: { fontSize: 20, marginRight: spacing.sm, marginBottom: 2 },
  msgBubble: {
    maxWidth: "80%",
    padding: spacing.md,
    borderRadius: borderRadius.lg,
  },
  msgOme: {
    backgroundColor: colors.bgCard,
    borderBottomLeftRadius: 4,
    borderWidth: 1,
    borderColor: colors.border,
  },
  msgUser: {
    backgroundColor: colors.accent,
    borderBottomRightRadius: 4,
  },
  msgText: {
    fontSize: fontSize.md,
    color: colors.textPrimary,
    lineHeight: 22,
  },
  msgTextUser: { color: colors.bg },

  inputBar: {
    flexDirection: "row",
    alignItems: "flex-end",
    padding: spacing.md,
    paddingBottom: spacing.xl,
    borderTopWidth: 1,
    borderTopColor: colors.border,
    backgroundColor: colors.bgCard,
  },
  input: {
    flex: 1,
    backgroundColor: colors.bgInput,
    borderRadius: borderRadius.lg,
    padding: spacing.md,
    paddingTop: spacing.md,
    fontSize: fontSize.md,
    color: colors.textPrimary,
    maxHeight: 100,
    marginRight: spacing.sm,
  },
  sendBtn: {
    width: 44,
    height: 44,
    borderRadius: 22,
    backgroundColor: colors.accent,
    justifyContent: "center",
    alignItems: "center",
  },
  sendBtnDisabled: { opacity: 0.4 },
  sendText: {
    fontSize: fontSize.xl,
    fontWeight: "700",
    color: colors.bg,
  },
});
