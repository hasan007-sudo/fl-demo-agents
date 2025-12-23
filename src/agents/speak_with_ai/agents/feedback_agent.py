"""Feedback Agent for SpeakWithAI."""

from core.agents.mixins.shutdown import ShutdownMixin
import logging

from core.session.checkpoints import SessionTimingConfig
from .base_speak_with_ai_agent import BaseSpeakWithAIAgent
from ..context import SpeakWithAIContext
from ..config import FEEDBACK_TIMING_CONFIG

logger = logging.getLogger(__name__)


class FeedbackAgent(BaseSpeakWithAIAgent, ShutdownMixin):
    """
    Feedback Agent for SpeakWithAI sessions.

    This agent:
    - Summarizes the conversation and questions explored
    - Provides constructive feedback on the discussion
    - Closes the session professionally
    """

    def get_timing_config(self) -> SessionTimingConfig:
        """Get timing configuration for feedback phase."""
        return FEEDBACK_TIMING_CONFIG

    async def _on_enter_hook(self) -> None:
        """Start the feedback phase."""
        logger.info("FeedbackAgent: Starting feedback phase")

        userdata: SpeakWithAIContext = self.session.userdata

        # Build summary of what was discussed
        questions_discussed = userdata.questions_discussed
        topics = userdata.topics_discussed

        discussed_questions_summary = []
        for qid in questions_discussed:
            q = userdata.get_question_by_id(qid)
            if q:
                discussed_questions_summary.append(q.text)

        questions_str = ", ".join(discussed_questions_summary) if discussed_questions_summary else "various topics"
        topics_str = ", ".join(topics) if topics else ""

        combined_topics = questions_str
        if topics_str:
            combined_topics += f" and {topics_str}"

        feedback_context = (
            f"Start by transitioning smoothly: 'Let me share some thoughts on our conversation.' "
            f"The student explored these topics: {combined_topics}. "
            f"Questions discussed: {len(questions_discussed)} out of {len(userdata.questions)}. "
            f"Provide constructive feedback on their engagement and communication, "
            f"then close the session professionally."
        )

        logger.info(f"Feedback context: {feedback_context}")

        # Generate feedback
        await self.session.generate_reply(
            instructions=feedback_context,
            allow_interruptions=False
        )
        logger.info("FeedbackAgent: Feedback generated")
        await self._graceful_shutdown()
        logger.info("Session shutdown gracefully after feedback")

    def get_goodbye_instruction(self) -> str:
        """Get the instruction for generating goodbye message."""
        return "Say goodbye professionally and end the session."

    def get_session_duration(self) -> int:
        """Get the session duration for metadata."""
        return self.get_timing_config().max_duration
