"""
Interview agent evaluator using DeepEval metrics.
"""

import logging
from typing import Dict, Any, List, Optional, Tuple

from deepeval.metrics import BaseMetric
from deepeval.test_case import ConversationalTestCase

from core.evaluation.evaluator import BaseEvaluator, EvaluationResult
from core.evaluation.transcript_builder import TranscriptBuilder, SessionTranscript
from .config import get_conversation_metrics, get_role_for_mode

logger = logging.getLogger(__name__)


class InterviewAgentEvaluator(BaseEvaluator):
    """
    Evaluator for Interview agent sessions.

    Metrics:
    - Role adherence (professional interviewer or coaching persona)
    - Knowledge retention (remembers context, candidate info)
    - Conversation completeness (covers interview questions)
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
            context_data: Additional context (student_name, questions, mock_interview, etc.)

        Returns:
            Tuple of (EvaluationResult, SessionTranscript, ConversationalTestCase)
        """
        context = context_data or {}
        mock_interview = context.get("mock_interview", False)

        transcript = TranscriptBuilder.from_chat_history(
            chat_items=chat_items,
            session_id=session_id,
            agent_type="interview_agent",
            context_data=context_data,
        )

        chatbot_role = get_role_for_mode(mock_interview)

        test_case = TranscriptBuilder.build_test_case(
            transcript=transcript,
            chatbot_role=chatbot_role,
        )

        return self.evaluate(test_case), transcript, test_case

    def save_to_dataset(
        self,
        transcript: SessionTranscript,
        test_case: ConversationalTestCase,
        dataset_alias: str = "interview-agent-sessions",
    ) -> None:
        """
        Push session to Confident AI dataset as ConversationalGolden.

        Args:
            transcript: Session transcript with context data
            test_case: ConversationalTestCase with turns
            dataset_alias: Name of the dataset in Confident AI
        """
        from deepeval.dataset import EvaluationDataset, ConversationalGolden

        # Determine interview mode from metadata
        metadata = test_case.additional_metadata or {}
        mock_interview = transcript.metadata.get("mock_interview", False)
        mode_label = "Mock Interview" if mock_interview else "Practice Interview"

        # Build scenario from context
        questions_text = ", ".join(
            q.get("text", q.get("identifier", ""))
            for q in (transcript.questions or [])
        )
        scenario = f"{mode_label} session for '{transcript.student_name}'"
        if questions_text:
            scenario += f" covering: {questions_text}"

        # Expected outcome = full question texts that SHOULD be covered
        question_texts = [
            q.get("text", "") for q in (transcript.questions or []) if q.get("text")
        ]
        expected_outcome = (
            f"Agent should conduct a {mode_label.lower()} covering these questions:\n"
            + "\n".join(f"- {text}" for text in question_texts)
        )

        goldens = ConversationalGolden(
            scenario=scenario,
            expected_outcome=expected_outcome,
            turns=test_case.turns,
            additional_metadata=test_case.additional_metadata,
        )

        dataset = EvaluationDataset(goldens=[goldens])
        dataset.push(alias=dataset_alias)
        logger.info(f"Pushed session {transcript.session_id} to dataset '{dataset_alias}'")
