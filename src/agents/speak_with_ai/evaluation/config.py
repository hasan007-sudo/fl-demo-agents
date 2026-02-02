"""
DeepEval metrics configuration for Speak with AI agent.
"""

from typing import List
from deepeval.metrics import (
    RoleAdherenceMetric,
    KnowledgeRetentionMetric,
    ConversationCompletenessMetric,
)

SPEAK_WITH_AI_ROLE = """
You are a friendly conversation partner speaking in professional, clear Indian English.
Your job is to discuss specific questions provided to you with the user.

You must:
- Use Indian English expressions and phrasing (not British or American English)
- Be warm, encouraging, and conversational
- Keep responses concise - the user should speak more than you
- Ask follow-up questions to explore answers deeper
- Stay on topic with the provided questions only
- Remember the student's name and use it naturally
"""


def get_conversation_metrics(
    role_threshold: float = 0.7,
    retention_threshold: float = 0.7,
    completeness_threshold: float = 0.7,
    model: str = "gpt-4o-mini",
) -> List:
    """Get configured DeepEval metrics for conversation evaluation."""
    return [
        RoleAdherenceMetric(
            threshold=role_threshold,
            model=model,
            include_reason=True,
        ),
        KnowledgeRetentionMetric(
            threshold=retention_threshold,
            model=model,
            include_reason=True,
        ),
        ConversationCompletenessMetric(
            threshold=completeness_threshold,
            model=model,
            include_reason=True,
        ),
    ]
