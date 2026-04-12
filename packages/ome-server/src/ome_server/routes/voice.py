"""Voice interaction routes — STT transcription + TTS synthesis.

Feature D1 in Ome365. Provides:
  - POST /voice/transcribe  — audio → text (STT)
  - POST /voice/chat        — audio → text → Ome reply (STT + chat in one step)
  - POST /voice/synthesize   — text → audio (TTS)

STT/TTS backends are pluggable via env vars:
  - VOICE_STT_PROVIDER: "whisper" (OpenAI Whisper API) | "deepseek" | "local" (whisper.cpp)
  - VOICE_TTS_PROVIDER: "minimax" (MiniMax Speech-01) | "openai" | "edge" (edge-tts, free)
  - Defaults to whatever API keys are available.
"""

from __future__ import annotations

import asyncio
import base64
import io
import logging
import os
import tempfile
from typing import Any, Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from ome.core import Ome
from ome_server.deps import get_ome

log = logging.getLogger("ome_server.voice")
router = APIRouter()


# ── STT Provider ──────────────────────────────────────────────────────

def _get_stt_provider() -> str:
    explicit = os.environ.get("VOICE_STT_PROVIDER", "").lower()
    if explicit:
        return explicit
    # Auto-detect from available keys
    if os.environ.get("OPENAI_API_KEY"):
        return "whisper"
    if os.environ.get("DEEPSEEK_API_KEY"):
        return "deepseek"
    return "none"


async def _transcribe_audio(audio_bytes: bytes, filename: str = "audio.wav") -> str:
    """Transcribe audio bytes to text using the configured STT provider."""
    provider = _get_stt_provider()

    if provider == "whisper":
        return await _transcribe_whisper(audio_bytes, filename)
    elif provider == "deepseek":
        return await _transcribe_deepseek(audio_bytes, filename)
    elif provider == "local":
        return await _transcribe_local(audio_bytes, filename)
    else:
        raise HTTPException(
            status_code=503,
            detail="No STT provider configured. Set OPENAI_API_KEY for Whisper, "
                   "or VOICE_STT_PROVIDER=local for whisper.cpp.",
        )


async def _transcribe_whisper(audio_bytes: bytes, filename: str) -> str:
    """OpenAI Whisper API transcription."""
    try:
        import openai
    except ImportError:
        raise HTTPException(status_code=503, detail="openai package not installed")

    client = openai.OpenAI(api_key=os.environ["OPENAI_API_KEY"])

    def _do():
        audio_file = io.BytesIO(audio_bytes)
        audio_file.name = filename
        resp = client.audio.transcriptions.create(
            model="whisper-1",
            file=audio_file,
            response_format="text",
        )
        return resp.strip() if isinstance(resp, str) else resp.text.strip()

    return await asyncio.to_thread(_do)


async def _transcribe_deepseek(audio_bytes: bytes, filename: str) -> str:
    """DeepSeek STT (OpenAI-compatible endpoint)."""
    try:
        import openai
    except ImportError:
        raise HTTPException(status_code=503, detail="openai package not installed")

    client = openai.OpenAI(
        api_key=os.environ["DEEPSEEK_API_KEY"],
        base_url="https://api.deepseek.com/v1",
    )

    def _do():
        audio_file = io.BytesIO(audio_bytes)
        audio_file.name = filename
        resp = client.audio.transcriptions.create(
            model="deepseek-audio",
            file=audio_file,
            response_format="text",
        )
        return resp.strip() if isinstance(resp, str) else resp.text.strip()

    return await asyncio.to_thread(_do)


async def _transcribe_local(audio_bytes: bytes, filename: str) -> str:
    """Local whisper.cpp transcription."""
    import subprocess
    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
        f.write(audio_bytes)
        f.flush()
        tmp_path = f.name

    try:
        whisper_bin = os.environ.get("WHISPER_CPP_BIN", "whisper-cpp")
        whisper_model = os.environ.get("WHISPER_CPP_MODEL", "base")
        proc = await asyncio.to_thread(
            subprocess.run,
            [whisper_bin, "-m", whisper_model, "-f", tmp_path, "--no-timestamps", "-l", "auto"],
            capture_output=True, text=True, timeout=30,
        )
        return proc.stdout.strip()
    finally:
        os.unlink(tmp_path)


# ── TTS Provider ──────────────────────────────────────────────────────

def _get_tts_provider() -> str:
    explicit = os.environ.get("VOICE_TTS_PROVIDER", "").lower()
    if explicit:
        return explicit
    if os.environ.get("MINIMAX_API_KEY"):
        return "minimax"
    if os.environ.get("OPENAI_API_KEY"):
        return "openai"
    return "edge"  # edge-tts is free, no key needed


async def _synthesize_speech(text: str, voice: str = "") -> tuple[bytes, str]:
    """Synthesize text to audio bytes. Returns (audio_bytes, content_type)."""
    provider = _get_tts_provider()

    if provider == "minimax":
        return await _tts_minimax(text, voice)
    elif provider == "openai":
        return await _tts_openai(text, voice)
    elif provider == "edge":
        return await _tts_edge(text, voice)
    else:
        raise HTTPException(status_code=503, detail="No TTS provider configured.")


async def _tts_minimax(text: str, voice: str) -> tuple[bytes, str]:
    """MiniMax Speech-01-HD TTS."""
    import httpx
    api_key = os.environ["MINIMAX_API_KEY"]
    group_id = os.environ.get("MINIMAX_GROUP_ID", "")
    voice_id = voice or os.environ.get("MINIMAX_VOICE_ID", "male-qn-qingse")

    url = f"https://api.minimax.chat/v1/t2a_v2?GroupId={group_id}"
    payload = {
        "model": "speech-01-hd",
        "text": text,
        "voice_setting": {"voice_id": voice_id, "speed": 1.0, "vol": 1.0, "pitch": 0},
        "audio_setting": {"sample_rate": 24000, "bitrate": 128000, "format": "mp3"},
    }

    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.post(url, json=payload, headers={"Authorization": f"Bearer {api_key}"})
        resp.raise_for_status()
        data = resp.json()

    audio_b64 = data.get("data", {}).get("audio", "")
    if not audio_b64:
        raise HTTPException(status_code=502, detail="MiniMax returned no audio")
    return base64.b64decode(audio_b64), "audio/mpeg"


async def _tts_openai(text: str, voice: str) -> tuple[bytes, str]:
    """OpenAI TTS."""
    try:
        import openai
    except ImportError:
        raise HTTPException(status_code=503, detail="openai package not installed")

    client = openai.OpenAI(api_key=os.environ["OPENAI_API_KEY"])

    def _do():
        resp = client.audio.speech.create(
            model="tts-1",
            voice=voice or "alloy",
            input=text,
            response_format="mp3",
        )
        return resp.content

    audio = await asyncio.to_thread(_do)
    return audio, "audio/mpeg"


async def _tts_edge(text: str, voice: str) -> tuple[bytes, str]:
    """Edge TTS (free, no API key)."""
    try:
        import edge_tts
    except ImportError:
        raise HTTPException(
            status_code=503,
            detail="edge-tts not installed. Run: pip install edge-tts",
        )

    voice_name = voice or "zh-CN-XiaoxiaoNeural"
    communicate = edge_tts.Communicate(text, voice_name)

    chunks = []
    async for chunk in communicate.stream():
        if chunk["type"] == "audio":
            chunks.append(chunk["data"])

    if not chunks:
        raise HTTPException(status_code=502, detail="edge-tts produced no audio")
    return b"".join(chunks), "audio/mpeg"


# ── Routes ────────────────────────────────────────────────────────────

class TranscribeResponse(BaseModel):
    text: str
    provider: str


class VoiceChatResponse(BaseModel):
    transcription: str
    reply: str
    mood: str
    mood_emoji: str


class SynthesizeRequest(BaseModel):
    text: str
    voice: str = ""


@router.post("/voice/transcribe", response_model=TranscribeResponse)
async def transcribe(
    audio: UploadFile = File(...),
    ome: Ome = Depends(get_ome),
):
    """Transcribe uploaded audio to text (STT)."""
    audio_bytes = await audio.read()
    if not audio_bytes:
        raise HTTPException(status_code=400, detail="Empty audio file")

    text = await _transcribe_audio(audio_bytes, audio.filename or "audio.wav")
    return {"text": text, "provider": _get_stt_provider()}


@router.post("/voice/chat", response_model=VoiceChatResponse)
async def voice_chat(
    audio: UploadFile = File(...),
    ome: Ome = Depends(get_ome),
):
    """Voice-in, text-out: transcribe audio → chat with Ome → return reply.

    For full voice loop, call this endpoint then POST /voice/synthesize with the reply.
    """
    audio_bytes = await audio.read()
    if not audio_bytes:
        raise HTTPException(status_code=400, detail="Empty audio file")

    # STT
    text = await _transcribe_audio(audio_bytes, audio.filename or "audio.wav")
    if not text:
        raise HTTPException(status_code=422, detail="Could not transcribe audio")

    # Chat
    reply = await asyncio.to_thread(ome.chat, text)

    return {
        "transcription": text,
        "reply": reply,
        "mood": ome.emotion.mood,
        "mood_emoji": ome.emotion.mood_emoji(),
    }


@router.post("/voice/synthesize")
async def synthesize(req: SynthesizeRequest, ome: Ome = Depends(get_ome)):
    """Synthesize text to audio (TTS). Returns audio/mpeg stream."""
    if not req.text:
        raise HTTPException(status_code=400, detail="Empty text")

    audio_bytes, content_type = await _synthesize_speech(req.text, req.voice)
    return StreamingResponse(
        io.BytesIO(audio_bytes),
        media_type=content_type,
        headers={"Content-Disposition": "inline; filename=speech.mp3"},
    )


@router.get("/voice/providers")
async def voice_providers(ome: Ome = Depends(get_ome)):
    """Check which voice providers are available."""
    return {
        "stt": _get_stt_provider(),
        "tts": _get_tts_provider(),
        "stt_available": _get_stt_provider() != "none",
        "tts_available": True,  # edge-tts is always available as fallback
    }
