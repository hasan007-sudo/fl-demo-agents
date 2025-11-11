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

    # OpenAI voice mapping - Updated with supported Realtime API voices
    VOICE_MAPPING = {
        "male": "ash",
        "female": "shimmer",
        "no_preference": "alloy"
    }

    # Default voice if no preference
    DEFAULT_VOICE = "alloy"

    @classmethod
    def select_voice(
        cls,
        gender_preference: Optional[str] = None
    ) -> str:
        """
        Select an appropriate voice based on gender preference.
        Maintains exact compatibility with existing voice_selector.py

        Args:
            gender_preference: "male", "female", or "no_preference"

        Returns:
            Selected voice name: "echo", "nova", or "alloy"
        """
        if not gender_preference:
            logger.info(f"No gender preference provided. Using default voice: {cls.DEFAULT_VOICE}")
            return cls.DEFAULT_VOICE

        # Use exact same mapping as existing code
        selected_voice = cls.VOICE_MAPPING.get(gender_preference.lower(), cls.DEFAULT_VOICE)

        logger.info(
            f"Selected voice: {selected_voice} (gender preference: {gender_preference})"
        )

        return selected_voice

    @classmethod
    def get_voice_for_agent(
        cls,
        agent_type: str,
        context: Optional[Dict[str, Any]] = None
    ) -> str:
        """
        Get voice for a specific agent type based on gender_preference.

        Args:
            agent_type: Type of agent
            context: Agent context with preferences

        Returns:
            Selected voice
        """
        # Get gender_preference from context - this is what frontend sends
        gender_preference = context.gender_preference

        # Use gender_preference to select voice (same field for both agents)
        return cls.select_voice(gender_preference=gender_preference)