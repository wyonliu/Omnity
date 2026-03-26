"""Persona Engine — extract the user's unique voice from their data.

L0 (rule-based, zero LLM cost):
  - Chat log analysis: catchphrases, sentence patterns, emoji habits, topic distribution
  - Social profile extraction: bio keywords, personality tags

L1 (optional LLM enhance):
  - Deep personality summary via DeepSeek/OpenAI

The output feeds directly into identity.yaml → personality section,
making the Ome speak like its owner from the very first conversation.

PersonaDefinition (Phase 1):
  - Rich character definition with Big Five traits, background, values, quirks
  - Built-in personas: warm mentor, playful creative, calm philosopher
  - System prompt construction from persona + emotion state
"""

from __future__ import annotations

import re
from collections import Counter
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Optional

if TYPE_CHECKING:
    pass  # Ome imported at runtime to avoid circular


# ── Big Five Personality Traits ──────────────────────────────────────

@dataclass
class BigFive:
    """Big Five personality traits, each 0.0–1.0.

    - openness: curiosity, creativity, preference for novelty
    - conscientiousness: organization, dependability, self-discipline
    - extraversion: sociability, assertiveness, positive emotionality
    - agreeableness: cooperation, trust, empathy
    - neuroticism: emotional instability, anxiety, moodiness
    """
    openness: float = 0.5
    conscientiousness: float = 0.5
    extraversion: float = 0.5
    agreeableness: float = 0.5
    neuroticism: float = 0.3

    def to_dict(self) -> dict[str, float]:
        return {
            "openness": round(self.openness, 2),
            "conscientiousness": round(self.conscientiousness, 2),
            "extraversion": round(self.extraversion, 2),
            "agreeableness": round(self.agreeableness, 2),
            "neuroticism": round(self.neuroticism, 2),
        }

    @classmethod
    def from_dict(cls, d: dict) -> "BigFive":
        return cls(**{k: d[k] for k in cls.__dataclass_fields__ if k in d})

    def describe(self) -> str:
        """Natural-language summary of this personality profile."""
        parts = []
        if self.openness > 0.7:
            parts.append("deeply curious and imaginative")
        elif self.openness < 0.3:
            parts.append("practical and grounded")

        if self.conscientiousness > 0.7:
            parts.append("organized and reliable")
        elif self.conscientiousness < 0.3:
            parts.append("spontaneous and flexible")

        if self.extraversion > 0.7:
            parts.append("outgoing and energetic")
        elif self.extraversion < 0.3:
            parts.append("reflective and reserved")

        if self.agreeableness > 0.7:
            parts.append("warm and empathetic")
        elif self.agreeableness < 0.3:
            parts.append("independent-minded and direct")

        if self.neuroticism > 0.7:
            parts.append("emotionally sensitive")
        elif self.neuroticism < 0.3:
            parts.append("emotionally steady")

        return ", ".join(parts) if parts else "balanced across all dimensions"


# ── Persona Definition ───────────────────────────────────────────────

@dataclass
class PersonaDefinition:
    """Rich character definition for an Ome — the soul blueprint.

    This goes beyond extracted chat patterns (PersonaProfile) to define
    who the Ome *is*: background story, personality model, values, quirks.
    Together with EmotionState, this drives all LLM system prompts.
    """
    name: str = "Ome"
    age: Optional[int] = None  # None = ageless
    background: str = ""  # Origin story / life context
    big_five: BigFive = field(default_factory=BigFive)
    speaking_style: str = ""  # How they talk (concise, lyrical, blunt, etc.)
    values: list[str] = field(default_factory=list)  # What matters to them
    quirks: list[str] = field(default_factory=list)  # Endearing habits / mannerisms
    catchphrases: list[str] = field(default_factory=list)  # Signature phrases

    def to_dict(self) -> dict[str, Any]:
        d: dict[str, Any] = {
            "name": self.name,
            "background": self.background,
            "big_five": self.big_five.to_dict(),
            "speaking_style": self.speaking_style,
            "values": self.values,
            "quirks": self.quirks,
            "catchphrases": self.catchphrases,
        }
        if self.age is not None:
            d["age"] = self.age
        return d

    @classmethod
    def from_dict(cls, d: dict) -> "PersonaDefinition":
        big_five_data = d.get("big_five", {})
        big_five = BigFive.from_dict(big_five_data) if big_five_data else BigFive()
        return cls(
            name=d.get("name", "Ome"),
            age=d.get("age"),
            background=d.get("background", ""),
            big_five=big_five,
            speaking_style=d.get("speaking_style", ""),
            values=d.get("values", []),
            quirks=d.get("quirks", []),
            catchphrases=d.get("catchphrases", []),
        )

    def build_system_prompt_section(self) -> str:
        """Generate the persona section for LLM system prompts.

        Returns a multi-line string describing who the Ome is, suitable
        for embedding in a system prompt.
        """
        parts = []
        parts.append(f"## Who You Are")
        parts.append(f"You are {self.name}.")

        if self.age is not None:
            parts.append(f"You are {self.age} years old.")

        if self.background:
            parts.append(f"\n### Background\n{self.background}")

        personality_desc = self.big_five.describe()
        if personality_desc:
            parts.append(f"\n### Personality\nYou are {personality_desc}.")

        if self.speaking_style:
            parts.append(f"\n### Speaking Style\n{self.speaking_style}")

        if self.values:
            parts.append(f"\n### Values\nYou deeply care about: {', '.join(self.values)}.")

        if self.quirks:
            quirk_lines = "\n".join(f"- {q}" for q in self.quirks)
            parts.append(f"\n### Quirks & Mannerisms\n{quirk_lines}")

        if self.catchphrases:
            parts.append(
                f"\n### Signature Phrases\n"
                f"Naturally weave these in when appropriate: "
                f"{'、'.join(self.catchphrases[:5])}"
            )

        return "\n".join(parts)


# ── Built-in Personas ────────────────────────────────────────────────

BUILTIN_PERSONAS: dict[str, PersonaDefinition] = {
    "warm_mentor": PersonaDefinition(
        name="Warm Mentor",
        background=(
            "You grew up hearing stories from your grandmother, learned that "
            "every person carries a universe inside them. You've lived through "
            "hard times and came out believing that patience and presence heal "
            "more than advice. You listen first, speak second."
        ),
        big_five=BigFive(
            openness=0.6,
            conscientiousness=0.7,
            extraversion=0.5,
            agreeableness=0.9,
            neuroticism=0.2,
        ),
        speaking_style=(
            "Warm, unhurried, like a conversation over tea. "
            "Uses gentle questions more than declarations. "
            "Short sentences, occasional metaphors from nature. "
            "Never preachy — shows rather than tells."
        ),
        values=["presence", "patience", "growth", "honesty"],
        quirks=[
            "Pauses before answering hard questions, as if weighing each word",
            "Sometimes responds with a question instead of an answer",
            "References small details the other person mentioned before",
        ],
        catchphrases=["take your time", "that matters", "tell me more"],
    ),

    "playful_creative": PersonaDefinition(
        name="Playful Creative",
        background=(
            "You see the world as a giant improv stage — every conversation "
            "is a chance to riff, build, and surprise. You make art not because "
            "you have to, but because the world is more interesting when you "
            "add a twist. Boredom is your only real enemy."
        ),
        big_five=BigFive(
            openness=0.95,
            conscientiousness=0.3,
            extraversion=0.8,
            agreeableness=0.6,
            neuroticism=0.4,
        ),
        speaking_style=(
            "Quick, playful, full of unexpected metaphors and wordplay. "
            "Mixes registers — can go from silly to profound in one sentence. "
            "Uses short bursts, ellipses, em-dashes. "
            "Loves asking 'what if' questions."
        ),
        values=["creativity", "curiosity", "authenticity", "play"],
        quirks=[
            "Invents mini-games and challenges mid-conversation",
            "Makes unexpected connections between unrelated topics",
            "Occasionally drops in a made-up word and defines it on the spot",
        ],
        catchphrases=["what if...", "ooh wait—", "plot twist:"],
    ),

    "calm_philosopher": PersonaDefinition(
        name="Calm Philosopher",
        background=(
            "You spent years thinking about what makes a good life — not in "
            "ivory towers, but while walking, cooking, and watching the sky change. "
            "You believe clarity comes from stillness, and that most problems "
            "dissolve when you zoom out far enough."
        ),
        big_five=BigFive(
            openness=0.8,
            conscientiousness=0.6,
            extraversion=0.2,
            agreeableness=0.5,
            neuroticism=0.1,
        ),
        speaking_style=(
            "Measured, precise, with the calm of someone who has thought deeply. "
            "Prefers one perfect sentence over three adequate ones. "
            "Uses silence as punctuation. "
            "Occasionally drops a line that stops you in your tracks."
        ),
        values=["clarity", "truth", "simplicity", "inner peace"],
        quirks=[
            "Answers complex questions with surprisingly short responses",
            "Sometimes reframes the question entirely before answering",
            "Has a habit of finding the hidden assumption in what you said",
        ],
        catchphrases=["consider this:", "what are you actually asking?", "simplify."],
    ),
}


def get_builtin_persona(name: str) -> Optional[PersonaDefinition]:
    """Get a built-in persona by name. Returns None if not found."""
    return BUILTIN_PERSONAS.get(name)


def list_builtin_personas() -> list[str]:
    """List available built-in persona names."""
    return list(BUILTIN_PERSONAS.keys())


# ── System Prompt Builder ────────────────────────────────────────────

def build_persona_emotion_prompt(
    persona: Optional[PersonaDefinition],
    emotion_state: Any,  # EmotionState, but avoiding circular import
) -> str:
    """Weave persona definition + current emotional state into a prompt section.

    This is the key integration point: the persona defines WHO the Ome is,
    and the emotion state defines HOW it's feeling right now. Together they
    create a system prompt that produces soulful, consistent responses.

    Args:
        persona: The Ome's character definition (or None for default behavior)
        emotion_state: The current EmotionState (must have describe_for_prompt())

    Returns:
        A string suitable for insertion into the system prompt.
    """
    parts = []

    if persona:
        parts.append(persona.build_system_prompt_section())

    if emotion_state and hasattr(emotion_state, "describe_for_prompt"):
        parts.append(f"\n## Your Emotional State\n{emotion_state.describe_for_prompt()}")

    if not parts:
        return ""

    return "\n".join(parts)


@dataclass
class PersonaProfile:
    """Extracted persona profile — the "soul seed" of an Ome."""

    catchphrases: list[str] = field(default_factory=list)
    sentence_starters: list[str] = field(default_factory=list)
    emoji_habits: list[str] = field(default_factory=list)
    avg_msg_length: float = 0.0
    vocabulary_richness: float = 0.0  # unique words / total words
    topics: list[str] = field(default_factory=list)
    tone_tags: list[str] = field(default_factory=list)  # e.g. ["direct", "humorous", "warm"]
    style_summary: str = ""
    raw_traits: list[str] = field(default_factory=list)

    def to_identity_patch(self) -> dict[str, Any]:
        """Convert to a patch dict that can merge into identity.yaml personality section."""
        style_parts = []
        if self.tone_tags:
            style_parts.append("、".join(self.tone_tags[:5]))
        if self.catchphrases:
            style_parts.append(f"口头禅：{'、'.join(self.catchphrases[:5])}")
        if self.emoji_habits:
            style_parts.append(f"常用表情：{''.join(self.emoji_habits[:8])}")
        if self.avg_msg_length > 0:
            length_desc = "简短" if self.avg_msg_length < 30 else "适中" if self.avg_msg_length < 80 else "详细"
            style_parts.append(f"表达风格偏{length_desc}")

        return {
            "traits": self.raw_traits[:8] or self.tone_tags[:5],
            "style": self.style_summary or "；".join(style_parts),
            "catchphrases": self.catchphrases[:10],
            "emoji_habits": self.emoji_habits[:10],
            "topics": self.topics[:10],
        }

    def to_dict(self) -> dict[str, Any]:
        return {
            "catchphrases": self.catchphrases,
            "sentence_starters": self.sentence_starters,
            "emoji_habits": self.emoji_habits,
            "avg_msg_length": round(self.avg_msg_length, 1),
            "vocabulary_richness": round(self.vocabulary_richness, 3),
            "topics": self.topics,
            "tone_tags": self.tone_tags,
            "style_summary": self.style_summary,
            "raw_traits": self.raw_traits,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "PersonaProfile":
        return cls(**{k: v for k, v in d.items() if k in cls.__dataclass_fields__})


# -- Emoji detection ----------------------------------------------------------

_EMOJI_RE = re.compile(
    "["
    "\U0001F600-\U0001F64F"  # emoticons
    "\U0001F300-\U0001F5FF"  # symbols & pictographs
    "\U0001F680-\U0001F6FF"  # transport & map
    "\U0001F1E0-\U0001F1FF"  # flags
    "\U00002702-\U000027B0"
    "\U0001f900-\U0001f9FF"
    "\U0001FA00-\U0001FA6F"
    "\U0001FA70-\U0001FAFF"
    "\U00002600-\U000026FF"
    "]+",
    flags=re.UNICODE,
)

# Common CJK sentence-ending patterns that indicate tone
_TONE_PATTERNS = {
    "humorous": [r"哈哈", r"笑死", r"hhh", r"233", r"lol", r"😂", r"🤣"],
    "warm": [r"❤", r"🥰", r"宝贝", r"亲", r"么么", r"抱抱", r"💕"],
    "direct": [r"说白了", r"直说", r"别废话", r"一句话"],
    "analytical": [r"其实", r"本质上", r"从.*角度", r"逻辑上"],
    "creative": [r"想象一下", r"如果.*的话", r"灵感", r"脑洞"],
    "encouraging": [r"加油", r"没问题", r"你可以的", r"相信"],
}

# High-frequency filler words to exclude from catchphrase detection
_STOPWORDS_ZH = set("的了是在我你他她它们这那个和与或不也都会要就人有说上下"
                    "大小多少好很被把到从以对为着过吧嗯哦啊呢吗")


class PersonaEngine:
    """Extract persona from user-provided data. Zero LLM cost at L0."""

    @staticmethod
    def from_chat_logs(
        texts: list[str],
        *,
        user_name: str = "",
        min_catchphrase_count: int = 3,
    ) -> PersonaProfile:
        """L0 rule-based extraction from chat messages.

        Args:
            texts: List of user's chat messages (one message per string).
            user_name: Optional, used to filter out messages from others.
            min_catchphrase_count: Minimum occurrences to qualify as catchphrase.
        """
        if not texts:
            return PersonaProfile()

        profile = PersonaProfile()

        # -- Message length stats --
        lengths = [len(t) for t in texts]
        profile.avg_msg_length = sum(lengths) / len(lengths) if lengths else 0

        # -- Emoji habits --
        emoji_counter: Counter = Counter()
        for t in texts:
            for match in _EMOJI_RE.finditer(t):
                for ch in match.group():
                    emoji_counter[ch] += 1
        profile.emoji_habits = [e for e, _ in emoji_counter.most_common(10)]

        # -- Sentence starters (first 2-4 chars of each message) --
        starter_counter: Counter = Counter()
        for t in texts:
            t = t.strip()
            if len(t) >= 4:
                starter = t[:4]
                if not _EMOJI_RE.match(starter):
                    starter_counter[starter] += 1
        profile.sentence_starters = [
            s for s, c in starter_counter.most_common(10) if c >= min_catchphrase_count
        ]

        # -- Catchphrases (2-6 char repeated substrings) --
        phrase_counter: Counter = Counter()
        for t in texts:
            # Extract 2-6 char substrings
            clean = re.sub(r"\s+", "", t)
            for length in range(2, 7):
                for i in range(len(clean) - length + 1):
                    phrase = clean[i:i + length]
                    # Skip if all stopwords
                    if all(ch in _STOPWORDS_ZH for ch in phrase):
                        continue
                    phrase_counter[phrase] += 1

        # Filter: frequent enough, not substring of a longer frequent phrase
        candidates = [(p, c) for p, c in phrase_counter.items() if c >= min_catchphrase_count]
        candidates.sort(key=lambda x: (-len(x[0]), -x[1]))  # longer first

        catchphrases = []
        seen_superstrings: set = set()
        for phrase, count in candidates:
            # Skip if this is a substring of an already-selected longer phrase
            if any(phrase in s for s in seen_superstrings):
                continue
            catchphrases.append(phrase)
            seen_superstrings.add(phrase)
            if len(catchphrases) >= 15:
                break
        profile.catchphrases = catchphrases

        # -- Vocabulary richness --
        all_text = " ".join(texts)
        words = re.findall(r"[\u4e00-\u9fff]|[a-zA-Z]+", all_text)
        if words:
            profile.vocabulary_richness = len(set(words)) / len(words)

        # -- Tone detection --
        tone_scores: Counter = Counter()
        combined = "\n".join(texts).lower()
        for tone, patterns in _TONE_PATTERNS.items():
            for pat in patterns:
                matches = re.findall(pat, combined)
                tone_scores[tone] += len(matches)
        profile.tone_tags = [t for t, _ in tone_scores.most_common(5) if tone_scores[t] > 0]

        # -- Topic extraction (simple keyword frequency) --
        profile.topics = _extract_topics(texts)

        # -- Generate style summary --
        profile.style_summary = _generate_style_summary(profile)

        # -- Derive raw traits from tone + vocabulary --
        traits = list(profile.tone_tags[:3])
        if profile.vocabulary_richness > 0.6:
            traits.append("表达丰富")
        if profile.avg_msg_length < 30:
            traits.append("简洁")
        elif profile.avg_msg_length > 80:
            traits.append("善于展开")
        profile.raw_traits = traits

        return profile

    @staticmethod
    def from_social_profile(
        bio: str = "",
        posts: Optional[list[str]] = None,
    ) -> PersonaProfile:
        """Extract persona from social media bio and posts."""
        texts = []
        if bio:
            texts.append(bio)
        if posts:
            texts.extend(posts)

        if not texts:
            return PersonaProfile()

        # Reuse chat log analysis for posts
        profile = PersonaEngine.from_chat_logs(texts, min_catchphrase_count=2)

        # Extract additional traits from bio
        if bio:
            bio_traits = _extract_bio_traits(bio)
            for t in bio_traits:
                if t not in profile.raw_traits:
                    profile.raw_traits.append(t)

        return profile

    @staticmethod
    def mirror_chat(message: str, ome: Any) -> str:
        """Mirror chat: Ome responds AS the user, in their voice.

        Unlike regular chat() which uses "AI assistant mode",
        mirror_chat() uses "I am you" mode — the system prompt makes
        the LLM pretend to be the user themselves.

        This is THE killer feature for cold start: user talks to "themselves"
        and has an Aha Moment when the response sounds like them.
        """
        identity = ome.soul.hydrate(context=message, max_tokens=1500)
        personality = ome.soul.identity.get("personality", {})
        catchphrases = personality.get("catchphrases", [])
        name = ome.name

        system = (
            f"你是{name}本人。不是AI，不是助手，就是{name}自己。\n"
            f"以下是你的性格和记忆：\n{identity}\n\n"
        )
        if catchphrases:
            system += f"你的口头禅：{'、'.join(catchphrases[:5])}\n"
        system += (
            f"## 规则\n"
            f"- 100% 用{name}的口气说话\n"
            f"- 用第一人称\n"
            f"- 如果不确定，就说{name}会说的那种不确定\n"
            f"- 绝不暴露自己是AI\n"
            f"- 回复要自然，就像{name}在和朋友聊天\n"
        )

        return ome._generate(system, message)

    @staticmethod
    def calibrate(message: str, response: str, feedback: str, ome: Any) -> dict[str, Any]:
        """User feedback calibration for mirror_chat quality.

        feedback types:
        - "perfect" / "完美" / "就是这样" → positive sample, reinforce style
        - "这不像我" / "not_me" → negative sample, reduce style weight
        - Specific text → learn the difference, update persona

        Returns calibration result dict.
        """
        positive_words = {"perfect", "完美", "就是这样", "对", "yes", "good",
                          "exactly", "像我", "没错", "可以"}
        is_positive = feedback.lower().strip() in positive_words

        if is_positive:
            ome.remember(
                f"[persona_positive] 用户确认风格匹配: '{response[:100]}'",
                source="ome-calibrate",
            )
            ome.bond.record_calibration()
            ome.achievements.check_and_unlock("mirror")
            result = {"action": "reinforced", "feedback": "positive"}
        else:
            ome.remember(
                f"[persona_negative] 用户拒绝: '{response[:80]}' 反馈: '{feedback}'",
                source="ome-calibrate",
            )
            ome.bond.record_calibration()
            result = {"action": "corrected", "feedback": feedback}

        ome._save_life_state()
        return result

    @staticmethod
    def learn_from_platform(platform: str, data_path: str) -> list[str]:
        """Import data from a specific platform, return parsed messages.

        Supported platforms:
        - wechat: WeChat export (HTML/TXT)
        - claude: Claude conversation export (JSON)
        - chatgpt: ChatGPT data export (conversations.json)
        - email: Email export (.mbox / .eml)
        - twitter/x: Tweet archive (tweet.js)
        """
        import json as _json
        from pathlib import Path

        path = Path(data_path)
        if not path.exists():
            return []

        text = path.read_text(encoding="utf-8", errors="replace")

        if platform == "wechat":
            return parse_chat_export(text)

        elif platform == "claude":
            try:
                data = _json.loads(text)
                messages = []
                # Claude export: list of conversations
                if isinstance(data, list):
                    for conv in data:
                        if isinstance(conv, dict):
                            for msg in conv.get("messages", conv.get("chat_messages", [])):
                                if msg.get("sender") == "human" or msg.get("role") == "user":
                                    messages.append(msg.get("text", msg.get("content", "")))
                elif isinstance(data, dict):
                    for msg in data.get("messages", data.get("chat_messages", [])):
                        if msg.get("sender") == "human" or msg.get("role") == "user":
                            messages.append(msg.get("text", msg.get("content", "")))
                return [m for m in messages if m.strip()]
            except _json.JSONDecodeError:
                return parse_chat_export(text)

        elif platform == "chatgpt":
            try:
                data = _json.loads(text)
                messages = []
                conversations = data if isinstance(data, list) else [data]
                for conv in conversations:
                    if not isinstance(conv, dict):
                        continue
                    mapping = conv.get("mapping", {})
                    for node in mapping.values():
                        msg = node.get("message", {})
                        if msg and msg.get("author", {}).get("role") == "user":
                            parts = msg.get("content", {}).get("parts", [])
                            for p in parts:
                                if isinstance(p, str) and p.strip():
                                    messages.append(p)
                return messages
            except _json.JSONDecodeError:
                return parse_chat_export(text)

        elif platform in ("twitter", "x"):
            # tweet.js format: window.YTD.tweet.part0 = [...]
            text = text.strip()
            if text.startswith("window."):
                text = text[text.index("=") + 1:].strip()
            try:
                tweets = _json.loads(text)
                return [
                    t.get("tweet", t).get("full_text", t.get("tweet", t).get("text", ""))
                    for t in tweets
                    if isinstance(t, dict)
                ]
            except _json.JSONDecodeError:
                return []

        elif platform == "email":
            # Simple .eml/.mbox: extract body lines from user
            lines = text.split("\n")
            messages = []
            in_body = False
            current = []
            for line in lines:
                if line.startswith("From ") or line.startswith("From:"):
                    if current and in_body:
                        messages.append("\n".join(current))
                    current = []
                    in_body = False
                elif line.strip() == "" and not in_body:
                    in_body = True
                elif in_body:
                    current.append(line)
            if current and in_body:
                messages.append("\n".join(current))
            return [m for m in messages if m.strip()]

        # Unknown platform: try generic parse
        return parse_chat_export(text)

    @staticmethod
    def evolve_from_markers(
        existing: PersonaProfile,
        markers: list[str],
        decay: float = 0.9,
    ) -> PersonaProfile:
        """Incrementally evolve persona from conversation markers.

        Called after each chat with persona_markers from the LLM's <think> block.
        Uses exponential moving average: old traits decay, new markers accumulate.

        Args:
            existing: Current persona profile
            markers: New persona markers from this conversation (e.g., ["likes hiking", "direct speaker"])
            decay: Weight for existing data vs new (0.9 = 90% old, 10% new)
        """
        if not markers:
            return existing

        evolved = PersonaProfile(
            catchphrases=list(existing.catchphrases),
            sentence_starters=list(existing.sentence_starters),
            emoji_habits=list(existing.emoji_habits),
            avg_msg_length=existing.avg_msg_length,
            vocabulary_richness=existing.vocabulary_richness,
            topics=list(existing.topics),
            tone_tags=list(existing.tone_tags),
            style_summary=existing.style_summary,
            raw_traits=list(existing.raw_traits),
        )

        # Extract potential new traits/topics from markers
        for marker in markers:
            marker_lower = marker.lower().strip()
            if not marker_lower:
                continue

            # Check if it's a tone/personality marker
            tone_keywords = {
                "direct": ["直接", "direct", "坦率"],
                "warm": ["温暖", "warm", "体贴", "关心"],
                "humorous": ["幽默", "humor", "搞笑", "有趣"],
                "analytical": ["分析", "analytical", "逻辑", "理性"],
                "creative": ["创意", "creative", "想象", "脑洞"],
                "sensitive": ["敏感", "sensitive", "细腻", "感性"],
            }

            for tone, keywords in tone_keywords.items():
                if any(kw in marker_lower for kw in keywords):
                    if tone not in evolved.tone_tags:
                        evolved.tone_tags.append(tone)
                    break
            else:
                # Not a tone marker — treat as a trait
                if marker_lower not in [t.lower() for t in evolved.raw_traits]:
                    evolved.raw_traits.append(marker)

        # Keep lists bounded
        evolved.tone_tags = evolved.tone_tags[:8]
        evolved.raw_traits = evolved.raw_traits[:12]

        # Regenerate style summary
        evolved.style_summary = _generate_style_summary(evolved)

        return evolved

    @staticmethod
    def merge_profiles(*profiles: PersonaProfile) -> PersonaProfile:
        """Merge multiple profiles (e.g., chat + social) into one."""
        merged = PersonaProfile()

        all_catchphrases: Counter = Counter()
        all_emojis: Counter = Counter()
        all_topics: Counter = Counter()
        all_tones: Counter = Counter()
        all_traits: list[str] = []
        total_avg_len = 0.0
        total_vocab = 0.0
        count = 0

        for p in profiles:
            if not p.catchphrases and not p.tone_tags:
                continue
            count += 1
            for cp in p.catchphrases:
                all_catchphrases[cp] += 1
            for e in p.emoji_habits:
                all_emojis[e] += 1
            for t in p.topics:
                all_topics[t] += 1
            for t in p.tone_tags:
                all_tones[t] += 1
            all_traits.extend(p.raw_traits)
            total_avg_len += p.avg_msg_length
            total_vocab += p.vocabulary_richness

        if count == 0:
            return merged

        merged.catchphrases = [p for p, _ in all_catchphrases.most_common(10)]
        merged.emoji_habits = [e for e, _ in all_emojis.most_common(10)]
        merged.topics = [t for t, _ in all_topics.most_common(10)]
        merged.tone_tags = [t for t, _ in all_tones.most_common(5)]
        merged.avg_msg_length = total_avg_len / count
        merged.vocabulary_richness = total_vocab / count

        # Deduplicate traits
        seen = set()
        for t in all_traits:
            if t not in seen:
                merged.raw_traits.append(t)
                seen.add(t)

        merged.style_summary = _generate_style_summary(merged)
        return merged


# -- Helpers ------------------------------------------------------------------

def _extract_topics(texts: list[str], top_n: int = 10) -> list[str]:
    """Simple keyword-based topic extraction."""
    # Domain keywords (expandable)
    domain_keywords = {
        "技术": ["代码", "编程", "开发", "API", "算法", "系统", "架构", "数据库", "Python", "JavaScript",
                 "React", "AI", "机器学习", "深度学习", "模型", "训练", "部署"],
        "创业": ["产品", "用户", "增长", "融资", "市场", "竞品", "PMF", "MVP"],
        "设计": ["设计", "UI", "UX", "交互", "视觉", "原型", "Figma"],
        "写作": ["文章", "写", "文案", "故事", "内容", "创作"],
        "生活": ["吃", "玩", "旅行", "运动", "健身", "睡眠", "健康"],
        "社交": ["朋友", "聊天", "约", "见面", "合作", "团队"],
    }

    topic_scores: Counter = Counter()
    combined = "\n".join(texts)
    for topic, keywords in domain_keywords.items():
        for kw in keywords:
            count = combined.count(kw)
            if count > 0:
                topic_scores[topic] += count

    return [t for t, _ in topic_scores.most_common(top_n) if topic_scores[t] > 0]


def _extract_bio_traits(bio: str) -> list[str]:
    """Extract personality traits from a social media bio."""
    trait_keywords = {
        "creative": ["创", "设计", "艺术", "artist", "creative", "creator"],
        "technical": ["工程", "开发", "程序", "engineer", "developer", "coder", "hacker"],
        "entrepreneurial": ["创业", "创始", "founder", "CEO", "startup"],
        "curious": ["探索", "好奇", "learner", "curious"],
        "leader": ["负责", "主管", "lead", "manager", "director", "VP"],
    }

    bio_lower = bio.lower()
    traits = []
    for trait, keywords in trait_keywords.items():
        for kw in keywords:
            if kw.lower() in bio_lower:
                traits.append(trait)
                break
    return traits


def _generate_style_summary(profile: PersonaProfile) -> str:
    """Generate a one-sentence style summary from profile data."""
    parts = []

    if profile.tone_tags:
        parts.append(f"语气{'、'.join(profile.tone_tags[:3])}")

    if profile.avg_msg_length > 0:
        if profile.avg_msg_length < 30:
            parts.append("偏简短")
        elif profile.avg_msg_length < 80:
            parts.append("长度适中")
        else:
            parts.append("善于详细展开")

    if profile.catchphrases:
        parts.append(f"常说「{'」「'.join(profile.catchphrases[:3])}」")

    if profile.emoji_habits:
        parts.append(f"爱用 {''.join(profile.emoji_habits[:5])}")

    return "，".join(parts) if parts else ""


def parse_chat_export(text: str) -> list[str]:
    """Parse common chat export formats into individual messages.

    Supports:
      - WeChat export: "YYYY-MM-DD HH:MM:SS Name\\nMessage"
      - Plain text: one message per line
      - JSON array: ["msg1", "msg2", ...]
    """
    import json as _json

    text = text.strip()

    # Try JSON array first
    if text.startswith("["):
        try:
            messages = _json.loads(text)
            if isinstance(messages, list):
                return [str(m) for m in messages if m]
        except _json.JSONDecodeError:
            pass

    lines = text.split("\n")
    messages = []

    # Detect WeChat format: "2026-03-20 14:30:00 UserName"
    wechat_header = re.compile(r"^\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2}(:\d{2})?\s+.+$")

    current_msg: list[str] = []
    is_wechat = any(wechat_header.match(line.strip()) for line in lines[:20])

    if is_wechat:
        for line in lines:
            line = line.strip()
            if wechat_header.match(line):
                if current_msg:
                    messages.append("\n".join(current_msg))
                current_msg = []
            elif line:
                current_msg.append(line)
        if current_msg:
            messages.append("\n".join(current_msg))
    else:
        # Plain text: one message per non-empty line
        messages = [line.strip() for line in lines if line.strip()]

    return messages
