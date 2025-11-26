"""
Voice manager for selecting appropriate voices for agents based on preferences.
"""

from typing import Optional, Dict, Any
import logging

logger = logging.getLogger(__name__)


class VoiceManager:
    """
    Manages voice selection for agents.

    Maps preferences to actual OpenAI voice options.
    """

    # Voice mapping by provider
    VOICE_MAPPING = {
        "openai": {
            "male": "ash",
            "female": "shimmer",
            "no_preference": "alloy"
        },
        "google": {
            "male": "Charon",
            "female": "Aoede",
            "no_preference": "Charon"
        }
    }

    # Default voices per provider
    DEFAULT_VOICES = {
        "openai": "alloy",
        "google": "Charon"
    }

    @classmethod
    def select_voice(
        cls,
        gender_preference: Optional[str] = None,
        provider: str = "openai"
    ) -> str:
        """
        Select an appropriate voice based on gender preference and provider.

        Args:
            gender_preference: "male", "female", or "no_preference"
            provider: "openai" or "google"

        Returns:
            Selected voice name
        """
        provider = provider.lower()
        if provider not in cls.VOICE_MAPPING:
            logger.warning(f"Unknown provider {provider}, falling back to openai")
            provider = "openai"

        default_voice = cls.DEFAULT_VOICES.get(provider, "alloy")

        if not gender_preference:
            logger.info(f"No gender preference provided. Using default voice for {provider}: {default_voice}")
            return default_voice

        # Get provider-specific mapping
        provider_mapping = cls.VOICE_MAPPING[provider]
        selected_voice = provider_mapping.get(gender_preference.lower(), default_voice)

        logger.info(
            f"Selected voice: {selected_voice} (gender: {gender_preference}, provider: {provider})"
        )

        return selected_voice

    @classmethod
    def get_voice_for_agent(
        cls,
        agent_type: str,
        context: Optional[Dict[str, Any]] = None,
        provider: str = "openai"
    ) -> str:
        """
        Get voice for a specific agent type based on gender_preference.

        Args:
            agent_type: Type of agent
            context: Agent context with preferences
            provider: Model provider ("openai" or "google")

        Returns:
            Selected voice
        """
        # Get gender_preference from context - this is what frontend sends
        gender_preference = getattr(context, "gender_preference", None)

        # Use gender_preference to select voice
        return cls.select_voice(gender_preference=gender_preference, provider=provider)