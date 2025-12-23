"""
Centralized model configuration for SpeakWithAI agents.

This module provides a single source of truth for model configurations
per agent type. To change the model for an agent, simply modify the
configuration in the factory functions below.

IMPORTANT: Uses lazy initialization to ensure models are created AFTER
environment variables (like GEMINI_API_KEY) are loaded.
"""

from google.genai import types
from livekit.agents.types import APIConnectOptions
from typing import Dict, Any, Optional
from livekit.plugins import silero
from livekit.plugins.google.realtime import RealtimeModel
from livekit.plugins import openai, deepgram, cartesia, silero
from livekit.agents import (
    inference
)
from livekit.plugins import inworld

# =============================================================================
# CONVERSATION AGENT MODEL CONFIGURATION
# =============================================================================

def _create_conversation_model_config(voice: Optional[str] = None) -> Dict[str, Any]:
    """
    Create model configuration for Conversation Agent.

    This function uses lazy initialization - models are created when called,
    not at module import time. This ensures environment variables are loaded.

    Args:
        voice: Optional voice override for TTS

    Returns:
        Dictionary of model configuration
    """
    config = {
        "llm": RealtimeModel(
            model="gemini-2.5-flash-native-audio-preview-09-2025",
            voice=voice or "Charon",
            temperature=0.8,
            conn_options=APIConnectOptions(
                timeout=60
            ),
            realtime_input_config=types.RealtimeInputConfig(
                automatic_activity_detection=types.AutomaticActivityDetection(
                    disabled=True,
                ),
            ),
        ),
        "vad": silero.VAD.load(),
        "turn_detection": "vad",
        # "llm": openai.LLM(model="gpt-4o-mini"),
        # "stt": inference.STT(model="assemblyai/universal-streaming", language="en"),
        # "tts": inworld.TTS(model="inworld-tts-1-max", voice="Ashley"),
        # "stt": "assemblyai/universal-streaming", # Docs mention VAD only works when STT is present
    }

    return config


# =============================================================================
# FEEDBACK AGENT MODEL CONFIGURATION
# =============================================================================

def _create_feedback_model_config(voice: Optional[str] = None) -> Dict[str, Any]:
    """
    Create model configuration for Feedback Agent.

    This function uses lazy initialization - models are created when called,
    not at module import time. This ensures environment variables are loaded.

    Args:
        voice: Optional voice override for TTS

    Returns:
        Dictionary of model configuration
    """
    config = {
        "llm": RealtimeModel(
            model="gemini-2.5-flash-native-audio-preview-09-2025",
            voice=voice or "Charon",
            temperature=0.6,  # Lower for more consistent feedback
            conn_options=APIConnectOptions(
                timeout=60
            ),
            realtime_input_config=types.RealtimeInputConfig(
                automatic_activity_detection=types.AutomaticActivityDetection(
                    disabled=True,
                ),
            ),
        ),
        "vad": silero.VAD.load(
             min_speech_duration=0.1,   # Minimum speech duration to trigger (seconds)
             min_silence_duration=0.5,  # Silence duration to end speech (seconds)
        ),
        "turn_detection": "vad",
    }

    return config


def get_agent_model_config(
    agent_type: str,
    voice: Optional[str] = None
) -> Dict[str, Any]:
    """
    Get model configuration for a specific agent type.

    This function calls the appropriate factory function to create models
    lazily (after environment variables are loaded).

    Args:
        agent_type: Type of agent ("conversation" or "feedback")
        voice: Optional voice override for TTS

    Returns:
        Dictionary of model configuration kwargs for Agent constructor

    Raises:
        ValueError: If agent_type is not recognized
    """
    if agent_type == "conversation":
        config = _create_conversation_model_config(voice)
    elif agent_type == "feedback":
        config = _create_feedback_model_config(voice)
    else:
        raise ValueError(
            f"Unknown agent type: {agent_type}. "
            f"Expected 'conversation' or 'feedback'"
        )

    # Filter out None values
    return {k: v for k, v in config.items() if v is not None}
