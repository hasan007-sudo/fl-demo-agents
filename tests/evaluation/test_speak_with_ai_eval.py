"""
Tests for Speak with AI evaluation using DeepEval.

Run with: pytest tests/evaluation/test_speak_with_ai_eval.py -v
Note: Integration tests require OPENAI_API_KEY.
"""

import os
import pytest
from deepeval import assert_test
from deepeval.test_case import ConversationalTestCase, Turn

from agents.speak_with_ai.evaluation import (
    SpeakWithAIEvaluator,
    get_conversation_metrics,
    SPEAK_WITH_AI_ROLE,
)
from core.evaluation import TranscriptBuilder, SessionTranscript
from core.evaluation.reporters import ConsolePrinter


# Sample conversation data
SAMPLE_GOOD_CONVERSATION = [
    Turn(role="user", content="Hello"),
    Turn(
        role="assistant",
        content="Hello Rahul! Good to speak with you. Let's discuss your career goals - what does your ideal career path look like?",
    ),
    Turn(role="user", content="I want to become a software architect"),
    Turn(
        role="assistant",
        content="That's a wonderful aspiration, Rahul! What draws you to architecture - the technical depth or strategic decision-making?",
    ),
]


@pytest.fixture
def sample_transcript() -> SessionTranscript:
    """Create a sample transcript for testing."""
    return SessionTranscript(
        session_id="test-session-001",
        agent_type="speak_with_ai",
        student_name="Rahul",
        questions=[{"identifier": "q1", "text": "What are your career goals?"}],
        questions_discussed=["q1"],
        conversation_turns=[
            {"user": "Hello", "assistant": "Hello Rahul! Let's discuss your career goals."},
            {"user": "I want to be an architect", "assistant": "That's great! Tell me more."},
        ],
    )


@pytest.fixture
def evaluator() -> SpeakWithAIEvaluator:
    """Create evaluator instance."""
    return SpeakWithAIEvaluator(model="gpt-4o-mini")


# Unit tests (no API key needed)

def test_transcript_builder_creates_test_case(sample_transcript):
    """Test TranscriptBuilder creates valid ConversationalTestCase."""
    test_case = TranscriptBuilder.build_test_case(
        transcript=sample_transcript,
        chatbot_role=SPEAK_WITH_AI_ROLE,
    )

    assert isinstance(test_case, ConversationalTestCase)
    assert len(test_case.turns) == 4  # 2 turns × 2 (user + assistant)
    assert test_case.chatbot_role == SPEAK_WITH_AI_ROLE
    assert test_case.additional_metadata["session_id"] == "test-session-001"


def test_get_conversation_metrics_returns_three():
    """Test that we get 3 metrics."""
    metrics = get_conversation_metrics()
    assert len(metrics) == 3


def test_evaluator_initialization(evaluator):
    """Test evaluator initializes correctly."""
    assert evaluator.model == "gpt-4o-mini"
    assert len(evaluator.get_metrics()) == 3


# Integration tests (require OPENAI_API_KEY)

@pytest.mark.skipif(
    not os.getenv("OPENAI_API_KEY"),
    reason="OPENAI_API_KEY not set"
)
class TestDeepEvalIntegration:
    """Integration tests that run actual DeepEval evaluations."""

    def test_role_adherence(self):
        """Test role adherence metric."""
        test_case = ConversationalTestCase(
            turns=SAMPLE_GOOD_CONVERSATION,
            chatbot_role=SPEAK_WITH_AI_ROLE,
        )

        from deepeval.metrics import RoleAdherenceMetric
        metric = RoleAdherenceMetric(threshold=0.6, model="gpt-4o-mini")
        assert_test(test_case, [metric])

    def test_full_evaluation(self, evaluator, sample_transcript):
        """Test full evaluation flow."""
        test_case = TranscriptBuilder.build_test_case(
            transcript=sample_transcript,
            chatbot_role=SPEAK_WITH_AI_ROLE,
        )

        result = evaluator.evaluate(test_case)

        assert result.session_id == "test-session-001"
        assert 0 <= result.overall_score <= 1
        assert "RoleAdherenceMetric" in result.metrics

        ConsolePrinter(use_colors=False).print(result)
