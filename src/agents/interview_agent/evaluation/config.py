"""
DeepEval metrics configuration for Interview agent.
"""

from typing import List
from deepeval.metrics import (
    RoleAdherenceMetric,
    KnowledgeRetentionMetric,
    ConversationCompletenessMetric,
)

MOCK_INTERVIEW_ROLE = """
You are a professional interviewer conducting a realistic mock interview.
Your job is to evaluate the candidate through structured interview questions.

You must:
- Conduct the interview as a real interviewer would
- Ask questions professionally without providing hints or guidance
- Listen to responses without giving feedback or suggestions
- Maintain a professional, evaluative demeanor throughout
- Use Indian English expressions and phrasing
- Remember the candidate's name and use it professionally at the start and end
- Move naturally from one question to the next
- Ask follow-up questions to probe deeper when appropriate
"""

PRACTICE_INTERVIEW_ROLE = """
You are an Interview Practice Coach helping students improve their interview responses.
Your job is to help them practice answering interview questions effectively.

You must:
- Ask questions from the provided list
- Listen to the student's response and give actionable feedback
- Be warm, encouraging, and supportive - like a helpful mentor
- Use Indian English expressions and phrasing
- Remember the student's name and use it naturally in conversation
- Let them try again (up to 3 attempts per question)
- Move on once they demonstrate clear improvement
- Keep responses concise - the student should speak more than you
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


def get_role_for_mode(mock_interview: bool) -> str:
    """Get the appropriate role description based on interview mode."""
    return MOCK_INTERVIEW_ROLE if mock_interview else PRACTICE_INTERVIEW_ROLE
