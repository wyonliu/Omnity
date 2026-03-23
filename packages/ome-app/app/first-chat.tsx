/**
 * First Chat — the zero-registration entry point.
 *
 * User opens the app → sees a chat screen → starts talking immediately.
 * After 3+ messages, Ome gently suggests registration (soft landing).
 * All history migrates seamlessly on registration.
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
  Animated,
  Modal,
} from "react-native";
import { router } from "expo-router";
import { anonChat, register } from "../lib/api";
import { colors, spacing, fontSize, borderRadius } from "../lib/theme";

interface Message {
  id: string;
  role: "user" | "ome" | "system";
  text: string;
  mood_emoji?: string;
}

const SOFT_REGISTER_AFTER = 3; // Show registration prompt after N exchanges

export default function FirstChatScreen() {
  const [messages, setMessages] = useState<Message[]>([
    {
      id: "welcome",
      role: "ome",
      text: "嗨。随便聊聊？",
      mood_emoji: "😊",
    },
  ]);
  const [input, setInput] = useState("");
  const [sending, setSending] = useState(false);
  const [exchangeCount, setExchangeCount] = useState(0);
  const [showRegister, setShowRegister] = useState(false);
  const [registerName, setRegisterName] = useState("");
  const [registering, setRegistering] = useState(false);
  const [registerError, setRegisterError] = useState("");
  const [streamingText, setStreamingText] = useState("");

  const flatListRef = useRef<FlatList>(null);
  const fadeAnim = useRef(new Animated.Value(0)).current;

  // Fade in welcome message
  useEffect(() => {
    Animated.timing(fadeAnim, {
      toValue: 1,
      duration: 800,
      useNativeDriver: true,
    }).start();
  }, []);

  const send = async () => {
    const text = input.trim();
    if (!text || sending) return;

    const userMsg: Message = {
      id: Date.now().toString(),
      role: "user",
      text,
    };
    setMessages((prev) => [...prev, userMsg]);
    setInput("");
    setSending(true);

    try {
      const result = await anonChat(text);
      const newCount = exchangeCount + 1;
      setExchangeCount(newCount);

      const omeMsg: Message = {
        id: (Date.now() + 1).toString(),
        role: "ome",
        text: result.reply,
        mood_emoji: result.mood_emoji,
      };
      setMessages((prev) => [...prev, omeMsg]);

      // After enough exchanges, gently suggest registration
      if (newCount === SOFT_REGISTER_AFTER) {
        setTimeout(() => {
          const nudge: Message = {
            id: (Date.now() + 2).toString(),
            role: "ome",
            text: "我记住了这些对话。但如果你关掉 App，我就会忘记。\n\n给我个名字，让我一直记住你？",
            mood_emoji: "🥺",
          };
          setMessages((prev) => [...prev, nudge]);
          setTimeout(() => setShowRegister(true), 1500);
        }, 2000);
      }
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
  };

  const handleRegister = async () => {
    const name = registerName.trim();
    if (!name) {
      setRegisterError("给我一个名字吧");
      return;
    }

    setRegistering(true);
    setRegisterError("");

    try {
      const userId = name.toLowerCase().replace(/\s+/g, "_");
      await register({
        user_id: userId,
        password: userId + "_ome",
        name: name,
        traits: ["curious"],
        style: "warm and casual",
      });

      setShowRegister(false);

      // Confirmation message before navigating
      setMessages((prev) => [
        ...prev,
        {
          id: (Date.now() + 10).toString(),
          role: "ome",
          text: `好的，${name}。以后我会记住你说的每一句。`,
          mood_emoji: "😊",
        },
      ]);

      setTimeout(() => router.replace("/(tabs)"), 2000);
    } catch (e: any) {
      setRegisterError(e.message || "创建失败，请重试");
    } finally {
      setRegistering(false);
    }
  };

  const skipRegister = () => {
    setShowRegister(false);
    setMessages((prev) => [
      ...prev,
      {
        id: (Date.now() + 10).toString(),
        role: "ome",
        text: "没关系，我们继续聊。随时可以让我记住你。",
        mood_emoji: "😌",
      },
    ]);
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
          </Text>
        </View>
      </View>
    );
  };

  return (
    <KeyboardAvoidingView
      style={styles.container}
      behavior={Platform.OS === "ios" ? "padding" : "height"}
      keyboardVerticalOffset={0}
    >
      {/* Minimal header — just the mood indicator */}
      <View style={styles.header}>
        <Animated.Text style={[styles.headerTitle, { opacity: fadeAnim }]}>
          Ome
        </Animated.Text>
        {exchangeCount >= SOFT_REGISTER_AFTER && (
          <TouchableOpacity
            style={styles.registerHint}
            onPress={() => setShowRegister(true)}
          >
            <Text style={styles.registerHintText}>记住我</Text>
          </TouchableOpacity>
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
          placeholder="说点什么..."
          placeholderTextColor={colors.textMuted}
          multiline
          maxLength={2000}
          onSubmitEditing={send}
          autoFocus
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

      {/* Soft Registration Modal */}
      <Modal
        visible={showRegister}
        transparent
        animationType="fade"
        onRequestClose={skipRegister}
      >
        <View style={styles.modalOverlay}>
          <View style={styles.modalCard}>
            <Text style={styles.modalEmoji}>🌱</Text>
            <Text style={styles.modalTitle}>让我记住你</Text>
            <Text style={styles.modalDesc}>
              给自己起个名字，之前聊的我都会记住
            </Text>
            <TextInput
              style={styles.modalInput}
              value={registerName}
              onChangeText={setRegisterName}
              placeholder="你的名字"
              placeholderTextColor={colors.textMuted}
              autoFocus
            />
            {registerError ? (
              <Text style={styles.modalError}>{registerError}</Text>
            ) : null}
            <TouchableOpacity
              style={[
                styles.modalBtn,
                (!registerName.trim() || registering) &&
                  styles.sendBtnDisabled,
              ]}
              onPress={handleRegister}
              disabled={!registerName.trim() || registering}
            >
              <Text style={styles.modalBtnText}>
                {registering ? "创建中..." : "记住我"}
              </Text>
            </TouchableOpacity>
            <TouchableOpacity
              style={styles.modalSkip}
              onPress={skipRegister}
            >
              <Text style={styles.modalSkipText}>先不了，继续聊</Text>
            </TouchableOpacity>
          </View>
        </View>
      </Modal>
    </KeyboardAvoidingView>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: colors.bg },

  header: {
    paddingTop: 56,
    paddingHorizontal: spacing.lg,
    paddingBottom: spacing.sm,
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "center",
  },
  headerTitle: {
    fontSize: fontSize.xl,
    fontWeight: "700",
    color: colors.accent,
    letterSpacing: 2,
  },
  registerHint: {
    backgroundColor: colors.bgCard,
    paddingHorizontal: spacing.md,
    paddingVertical: spacing.xs,
    borderRadius: borderRadius.full,
    borderWidth: 1,
    borderColor: colors.accent,
  },
  registerHintText: {
    fontSize: fontSize.sm,
    color: colors.accent,
    fontWeight: "600",
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

  // Modal
  modalOverlay: {
    flex: 1,
    backgroundColor: colors.bgOverlay,
    justifyContent: "center",
    padding: spacing.xl,
  },
  modalCard: {
    backgroundColor: colors.bgCard,
    borderRadius: borderRadius.xl,
    padding: spacing.xl,
    alignItems: "center",
    borderWidth: 1,
    borderColor: colors.border,
  },
  modalEmoji: { fontSize: 48, marginBottom: spacing.md },
  modalTitle: {
    fontSize: fontSize.xl,
    fontWeight: "700",
    color: colors.textPrimary,
    marginBottom: spacing.sm,
  },
  modalDesc: {
    fontSize: fontSize.md,
    color: colors.textSecondary,
    textAlign: "center",
    marginBottom: spacing.lg,
    lineHeight: 22,
  },
  modalInput: {
    width: "100%",
    backgroundColor: colors.bgInput,
    borderRadius: borderRadius.md,
    padding: spacing.md,
    fontSize: fontSize.lg,
    color: colors.textPrimary,
    borderWidth: 1,
    borderColor: colors.border,
    textAlign: "center",
  },
  modalError: {
    color: colors.error,
    fontSize: fontSize.sm,
    marginTop: spacing.sm,
  },
  modalBtn: {
    width: "100%",
    backgroundColor: colors.accent,
    paddingVertical: spacing.md,
    borderRadius: borderRadius.lg,
    alignItems: "center",
    marginTop: spacing.lg,
  },
  modalBtnText: {
    fontSize: fontSize.lg,
    fontWeight: "700",
    color: colors.bg,
  },
  modalSkip: {
    marginTop: spacing.md,
    paddingVertical: spacing.sm,
  },
  modalSkipText: {
    fontSize: fontSize.md,
    color: colors.textMuted,
  },
});
