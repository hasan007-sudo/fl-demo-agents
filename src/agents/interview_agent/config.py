"""Interview agent configuration."""

from typing import Dict, Any, Optional
from livekit.plugins import silero, openai, sarvam

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
        "stt": sarvam.STT(
            language="en-IN",
            model="saarika:v2.5",
        ),
        "tts": sarvam.TTS(
            target_language_code="en-IN",
            speaker=voice or "manisha",
            model="bulbul:v2",
            pace=0.9,
        ),
    }
