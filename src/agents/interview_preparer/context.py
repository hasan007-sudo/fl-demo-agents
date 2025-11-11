"""
Context definition for Interview Preparer agent.

Defines the fields needed for conducting mock interviews.
"""

from typing import Optional, List, Dict, Any
from dataclasses import dataclass, field
from core.context.base import BaseContext


@dataclass
class InterviewContext(BaseContext):
    """
    Context data for the Interview Preparer agent.

    The frontend sends this via room metadata.
    """
    # Required fields
    candidate_name: str
    interview_type: str  # technical, behavioral, hr, case_study
    job_role: str  # software_engineer, product_manager, data_scientist, etc.
    experience_level: str  # entry, mid, senior, executive
    focus_areas: List[str] = field(default_factory=list)  # Specific topics to focus on

    # Optional fields
    gender_preference: Optional[str] = None
    target_industry: Optional[str] = None  # tech, finance, healthcare, retail, etc.
    company_size: Optional[str] = None  # startup, small, medium, large, enterprise
    interview_format: Optional[str] = None  # phone, video, in_person, panel
    preparation_level: Optional[str] = None  # beginner, intermediate, advanced
    weak_points: Optional[List[str]] = None  # Areas candidate struggles with
    practice_goals: Optional[List[str]] = None  # What candidate wants to achieve
    
    email: Optional[str] = None
    whatsapp: Optional[str] = None

    def __post_init__(self):
        """Initialize with default agent type."""
        if not self.agent_type:
            self.agent_type = "interview_preparer"
        super().__post_init__()

    def validate(self):
        """Validate the context data."""
        super().validate()

        # Validate interview type
        valid_types = ["technical", "behavioral", "hr", "case_study"]
        if self.interview_type not in valid_types:
            import logging
            logging.warning(f"Invalid interview type: {self.interview_type}")

        # Validate experience level
        valid_levels = ["entry", "mid", "senior", "executive"]
        if self.experience_level not in valid_levels:
            import logging
            logging.warning(f"Invalid experience level: {self.experience_level}")

    @classmethod
    def from_metadata(cls, metadata: Dict[str, Any]) -> 'InterviewContext':
        """
        Parse InterviewContext from room metadata.

        Handles camelCase to snake_case conversion and filters out agentType.

        Args:
            metadata: Room metadata dictionary from frontend

        Returns:
            InterviewContext instance
        """
        from utils.helpers import camel_to_snake

        # Convert camelCase keys to snake_case, exclude agentType
        context_data = {
            camel_to_snake(k): v
            for k, v in metadata.items()
            if k != "agent_type"
        }
        context = context_data.get("context", {})
        return cls(agent_type="interview_preparer", **context)