"""
Centralized model configuration for English Tutor agents.

This module provides a single source of truth for model configurations
per agent type. To change the model for an agent, simply modify the
configuration in this file.
"""

from typing import Dict, Any, Optional
from livekit.plugins import openai, deepgram, cartesia, silero
from livekit.plugins.google.beta.realtime import RealtimeModel as GoogleRealtimeModel


# =============================================================================
# CONVERSATION PARTNER AGENT MODEL CONFIGURATION
# =============================================================================
# Change these settings to switch models for the conversation partner
CONVERSATION_MODEL_CONFIG: Dict[str, Any] = {
    # Primary LLM for conversation
    "llm": GoogleRealtimeModel(
        model="gemini-2.5-flash-native-audio-preview-09-2025",
        voice="Charon",  # Indian English voice
        temperature=0.8,
    ),
    # STT - Not needed for realtime models
    "stt": None,
    # TTS - Not needed for realtime models
    "tts": None,
    # VAD for voice activity detection
    "vad": silero.VAD.load(),
}

# Alternative: Pipeline-based configuration (separate STT/LLM/TTS)
# Uncomment and use this if you prefer traditional pipeline approach
# CONVERSATION_MODEL_CONFIG: Dict[str, Any] = {
#     "llm": openai.LLM(model="gpt-4o"),
#     "stt": deepgram.STT(model="nova-3"),
#     "tts": cartesia.TTS(voice="indian-english-male"),
#     "vad": silero.VAD.load(),
# }


# =============================================================================
# FEEDBACK PROVIDER AGENT MODEL CONFIGURATION
# =============================================================================
# Change these settings to switch models for the feedback provider
FEEDBACK_MODEL_CONFIG: Dict[str, Any] = {
    # Can use a different/smaller model for feedback to save costs
    "llm": GoogleRealtimeModel(
        model="gemini-2.5-flash-native-audio-preview-09-2025",
        voice="Charon",  # Same voice for consistency
        temperature=0.7,  # Slightly lower for more consistent feedback
    ),
    "stt": None,
    "tts": None,
    "vad": silero.VAD.load(),
}

# Alternative: Use cheaper model for feedback
# FEEDBACK_MODEL_CONFIG: Dict[str, Any] = {
#     "llm": openai.LLM(model="gpt-4o-mini"),
#     "stt": deepgram.STT(model="nova-3"),
#     "tts": cartesia.TTS(voice="indian-english-male"),
#     "vad": silero.VAD.load(),
# }


def get_agent_model_config(
    agent_type: str,
    voice: Optional[str] = None
) -> Dict[str, Any]:
    """
    Get model configuration for a specific agent type.

    Args:
        agent_type: Type of agent ("conversation_partner" or "feedback_provider")
        voice: Optional voice override for TTS

    Returns:
        Dictionary of model configuration kwargs for Agent constructor

    Raises:
        ValueError: If agent_type is not recognized
    """
    if agent_type == "conversation_partner":
        config = CONVERSATION_MODEL_CONFIG.copy()
    elif agent_type == "feedback_provider":
        config = FEEDBACK_MODEL_CONFIG.copy()
    else:
        raise ValueError(
            f"Unknown agent type: {agent_type}. "
            f"Expected 'conversation_partner' or 'feedback_provider'"
        )

    # Apply voice override if provided and TTS exists
    if voice and config.get("tts"):
        # Create new TTS with specified voice
        if isinstance(config["tts"], cartesia.TTS):
            config["tts"] = cartesia.TTS(voice=voice)
        # Add more TTS providers here as needed

    # Filter out None values
    return {k: v for k, v in config.items() if v is not None}
