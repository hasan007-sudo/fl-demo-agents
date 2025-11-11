"""
Context definition for English Tutor agent.

This maintains 100% compatibility with the existing TutorContext.
All field names and types remain exactly the same.
"""

from typing import Optional, List, Dict, Any
from dataclasses import dataclass
from core.context.base import BaseContext


@dataclass
class EnglishTutorContext(BaseContext):
    """
    Context data for personalizing the English Tutor agent.

    IMPORTANT: These fields are EXACTLY as they exist in the current system.
    No changes to maintain frontend compatibility.

    The frontend sends this via room metadata in the tutor_context field.
    """
    # EXACT fields from frontend EnglishTutorContext interface
    student_name: Optional[str] = None
    proficiency_level: Optional[str] = None  # ProficiencyLevel type in frontend
    gender_preference: Optional[str] = None  # GenderPreference type - "male" or "female"
    speaking_speed: Optional[str] = None  # SpeakingSpeed type
    interests: Optional[List[str]] = None  # Interest[] in frontend
    comfortable_language: Optional[str] = None  # IndianLanguage type
    tutor_styles: Optional[List[str]] = None  # NewTutorStyle[] in frontend
    correction_preference: Optional[str] = None  # CorrectionPreference type
    email: Optional[str] = None
    whatsapp: Optional[str] = None
    # Note: learning_goals was in old context but not in the frontend interface

    def __post_init__(self):
        """Initialize with default agent type."""
        if not self.agent_type:
            self.agent_type = "english_tutor"
        super().__post_init__()

    def validate(self):
        """Validate the context data."""
        super().validate()
        # Add any English Tutor specific validation here if needed

        # Validate proficiency level if provided
        valid_levels = ["A1", "A2", "B1", "B2", "C1", "C2"]
        if self.proficiency_level and self.proficiency_level not in valid_levels:
            # Don't fail, just log warning to maintain compatibility
            import logging
            logging.warning(f"Invalid proficiency level: {self.proficiency_level}")

        # Validate correction preference if provided
        valid_corrections = ["immediate", "let_me_finish", "major_only", "focus_on_fluency"]
        if self.correction_preference and self.correction_preference not in valid_corrections:
            import logging
            logging.warning(f"Invalid correction preference: {self.correction_preference}")

        # Validate speaking speed if provided
        valid_speeds = ["very_slow", "slow", "normal", "fast"]
        if self.speaking_speed and self.speaking_speed not in valid_speeds:
            import logging
            logging.warning(f"Invalid speaking speed: {self.speaking_speed}")

    @classmethod
    def from_metadata(cls, metadata: Dict[str, Any]) -> 'EnglishTutorContext':
        """
        Parse EnglishTutorContext from room metadata.

        Handles camelCase to snake_case conversion and filters out agentType.

        Args:
            metadata: Room metadata dictionary from frontend

        Returns:
            EnglishTutorContext instance
        """
        from utils.helpers import camel_to_snake

        # Convert camelCase keys to snake_case, exclude agentType
        context_data = {
            camel_to_snake(k): v
            for k, v in metadata.items()
            if k != "agentType"
        }

        # Extract tutor_context from metadata
        tutor_context = context_data.get("context", {})
        return cls(agent_type="english_tutor", **tutor_context)