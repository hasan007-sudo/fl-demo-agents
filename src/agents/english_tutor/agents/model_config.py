"""
Centralized model configuration for English Tutor agents.

This module provides a single source of truth for model configurations
per agent type. To change the model for an agent, simply modify the
configuration in the factory functions below.

IMPORTANT: Uses lazy initialization to ensure models are created AFTER
environment variables (like GEMINI_API_KEY) are loaded.
"""

from google.genai import types
from livekit.agents import (
    inference
)
from livekit.plugins import inworld
from livekit.agents.types import APIConnectOptions
from typing import Dict, Any, Optional
from livekit.plugins import openai, deepgram, cartesia, silero
from livekit.plugins.google.beta.realtime import RealtimeModel as GoogleRealtimeModel


# =============================================================================
# CONVERSATION PARTNER AGENT MODEL CONFIGURATION
# =============================================================================

def _create_conversation_model_config(voice: Optional[str] = None) -> Dict[str, Any]:
    """
    Create model configuration for Conversation Partner Agent.

    This function uses lazy initialization - models are created when called,
    not at module import time. This ensures environment variables are loaded.

    To change the model for conversation partner, edit this function.

    Args:
        voice: Optional voice override for TTS

    Returns:
        Dictionary of model configuration
    """
    # Primary configuration: Google Gemini Realtime
    config = {
        "llm": GoogleRealtimeModel(
            model="gemini-2.5-flash-native-audio-preview-09-2025",
            voice=voice or "Charon",  # Indian English voice
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
        # for local
        # "llm": openai.LLM(model="gpt-4o-mini"),
        # "stt": inference.STT(model="assemblyai/universal-streaming", language="en"),
        # "tts": inworld.TTS(model="inworld-tts-1-max", voice="Ashley"),
    }

    return config

# =============================================================================
# FEEDBACK PROVIDER AGENT MODEL CONFIGURATION
# =============================================================================

def _create_feedback_model_config(voice: Optional[str] = None) -> Dict[str, Any]:
    """
    Create model configuration for Feedback Provider Agent.

    This function uses lazy initialization - models are created when called,
    not at module import time. This ensures environment variables are loaded.

    To change the model for feedback provider, edit this function.
    You can use a different/cheaper model here to save costs.

    Args:
        voice: Optional voice override for TTS

    Returns:
        Dictionary of model configuration
    """
    # Primary configuration: Google Gemini Realtime (same as conversation)
    config = {
        "llm": GoogleRealtimeModel(
            model="gemini-2.5-flash-native-audio-preview-09-2025",
            voice=voice or "Charon",  # Same voice for consistency
            temperature=0.6,  # Slightly lower for more consistent feedback
            conn_options=APIConnectOptions(
                timeout=60
            ),
            # thinking_config=types.ThinkingConfig(
            #     include_thoughts=False,
            # ),
            realtime_input_config=types.RealtimeInputConfig(
                automatic_activity_detection=types.AutomaticActivityDetection(
                    disabled=True,
                ),
            ),
        ),
        "vad": silero.VAD.load(),
        "turn_detection": "vad",
        # for local
        # "llm": openai.LLM(model="gpt-4o-mini"),
        # "stt": inference.STT(language="en"),
        # "tts": inworld.TTS(model="inworld-tts-1-max", voice="Ashley"),
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
        agent_type: Type of agent ("conversation_partner" or "feedback_provider")
        voice: Optional voice override for TTS

    Returns:
        Dictionary of model configuration kwargs for Agent constructor

    Raises:
        ValueError: If agent_type is not recognized
    """
    if agent_type == "conversation_partner":
        config = _create_conversation_model_config(voice)
    elif agent_type == "feedback_provider":
        config = _create_feedback_model_config(voice)
    else:
        raise ValueError(
            f"Unknown agent type: {agent_type}. "
            f"Expected 'conversation_partner' or 'feedback_provider'"
        )

    # Filter out None values
    return {k: v for k, v in config.items() if v is not None}
