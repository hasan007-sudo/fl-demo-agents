"""Evaluation module for conversation quality metrics using DeepEval."""

from .conversation_evaluator import (
    ConversationEvaluator,
    evaluate_tutoring_session,
    EvaluationResult,
)
from .metrics import (
    TopicAdherenceMetric,
    EngagementMetric,
    LearningEffectivenessMetric,
)

__all__ = [
    "ConversationEvaluator",
    "evaluate_tutoring_session",
    "EvaluationResult",
    "TopicAdherenceMetric",
    "EngagementMetric",
    "LearningEffectivenessMetric",
]
