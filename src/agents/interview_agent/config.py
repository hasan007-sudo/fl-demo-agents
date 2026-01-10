"""Interview agent configuration."""

from typing import Dict, Any, Optional
from livekit.plugins import silero, openai
from livekit.plugins import inworld
from livekit.agents import inference

# Session duration
MAX_SESSION_DURATION = 600  # 10 minutes


def get_model_config(voice: Optional[str] = None) -> Dict[str, Any]:
    """
    Get model configuration for Interview agent.

    Args:
        voice: Optional voice override for TTS

    Returns:
        Dictionary of model configuration
    """
    return {
        "vad": silero.VAD.load(),
        "turn_detection": "vad",
        "llm": openai.LLM(model="gpt-4o-mini"),
        "stt": inference.STT(model="assemblyai/universal-streaming", language="en"),
        "tts": inworld.TTS(model="inworld-tts-1-max", voice=voice or "Ashley"),
    }
