"""
English Tutor Agent - Multi-agent orchestration for conversational English practice.

This package provides a multi-agent system for English language learning:
- ConversationPartnerAgent: Handles greeting, onboarding, and speaking practice
- FeedbackProviderAgent: Provides constructive feedback and closes the session

The agents work together to create a natural, effective learning experience.
"""

from .agents import (
    ConversationPartnerAgent,
    FeedbackProviderAgent,
    get_agent_model_config,
)
from .context import EnglishTutorContext
from .prompt_builder import EnglishTutorPromptBuilder
from .shared.session_data import EnglishTutorSessionData

__all__ = [
    "ConversationPartnerAgent",
    "FeedbackProviderAgent",
    "get_agent_model_config",
    "EnglishTutorContext",
    "EnglishTutorPromptBuilder",
    "EnglishTutorSessionData",
]
