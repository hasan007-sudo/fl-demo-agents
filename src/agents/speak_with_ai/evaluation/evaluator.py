"""
SpeakWithAI evaluator using DeepEval metrics.
"""

import logging
import os
from typing import Dict, Any, List, Optional, Tuple

from deepeval.metrics import BaseMetric
from deepeval.test_case import ConversationalTestCase

from core.evaluation.evaluator import BaseEvaluator, EvaluationResult
from core.evaluation.transcript_builder import TranscriptBuilder, SessionTranscript
from .config import SPEAK_WITH_AI_ROLE, get_conversation_metrics

logger = logging.getLogger(__name__)


class SpeakWithAIEvaluator(BaseEvaluator):
    """
    Evaluator for Speak with AI sessions.

    Metrics:
    - Role adherence (Indian English persona)
    - Knowledge retention (remembers context)
    - Conversation completeness
    """

    def __init__(
        self,
        model: str = "gpt-4o-mini",
        verbose: bool = False,
        role_threshold: float = 0.7,
        retention_threshold: float = 0.7,
        completeness_threshold: float = 0.7,
    ):
        super().__init__(model=model, verbose=verbose)
        self.role_threshold = role_threshold
        self.retention_threshold = retention_threshold
        self.completeness_threshold = completeness_threshold

    def get_metrics(self) -> List[BaseMetric]:
        """Get configured metrics."""
        return get_conversation_metrics(
            role_threshold=self.role_threshold,
            retention_threshold=self.retention_threshold,
            completeness_threshold=self.completeness_threshold,
            model=self.model,
        )

    def evaluate_session(
        self,
        chat_items: List[Any],
        session_id: str,
        context_data: Optional[Dict[str, Any]] = None,
    ) -> Tuple[EvaluationResult, SessionTranscript, ConversationalTestCase]:
        """
        Evaluate a session from chat history.

        Args:
            chat_items: Chat messages from AgentSession.chat_ctx.items
            session_id: Session identifier
            context_data: Additional context (student_name, questions, etc.)

        Returns:
            Tuple of (EvaluationResult, SessionTranscript, ConversationalTestCase)
        """
        transcript = TranscriptBuilder.from_chat_history(
            chat_items=chat_items,
            session_id=session_id,
            agent_type="speak_with_ai",
            context_data=context_data,
        )

        test_case = TranscriptBuilder.build_test_case(
            transcript=transcript,
            chatbot_role=SPEAK_WITH_AI_ROLE,
        )

        return self.evaluate(test_case), transcript, test_case

    def save_to_dataset(
        self,
        transcript: SessionTranscript,
        test_case: ConversationalTestCase,
        dataset_alias: str = "speak-with-ai-sessions",
    ) -> None:
        """
        Push session to Confident AI dataset as ConversationalGolden.

        Args:
            transcript: Session transcript with context data
            test_case: ConversationalTestCase with turns
            dataset_alias: Name of the dataset in Confident AI
        """
        from deepeval.dataset import EvaluationDataset, ConversationalGolden

        # Build scenario from context
        questions_text = ", ".join(
            q.get("text", q.get("identifier", ""))
            for q in (transcript.questions or [])
        )
        scenario = f"Student '{transcript.student_name}' session"
        if questions_text:
            scenario += f" discussing: {questions_text}"

        # Expected outcome = full question texts that SHOULD be covered
        question_texts = [
            q.get("text", "") for q in (transcript.questions or []) if q.get("text")
        ]
        expected_outcome = (
            "Agent should cover these questions in the conversation:\n"
            + "\n".join(f"- {text}" for text in question_texts)
        )

        golden = ConversationalGolden(
            scenario=scenario,
            expected_outcome=expected_outcome,
            turns=test_case.turns,
            additional_metadata=test_case.additional_metadata,
        )

        dataset = EvaluationDataset(goldens=[golden])
        dataset.push(alias=dataset_alias)
        logger.info(f"Pushed session {transcript.session_id} to dataset '{dataset_alias}'")
