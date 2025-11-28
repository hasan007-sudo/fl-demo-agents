"""Feedback Provider Agent for English Tutor."""

from core.agents.mixins.shutdown import ShutdownMixin
import logging
from livekit.agents.llm import function_tool
from livekit.agents.voice import RunContext

from core.session.checkpoints import SessionTimingConfig
from .base_tutor_agent import BaseTutorAgent
from ..context import EnglishTutorContext
from ..config import FEEDBACK_TIMING_CONFIG

logger = logging.getLogger(__name__)


class FeedbackProviderAgent(BaseTutorAgent, ShutdownMixin):
    """
    Feedback Provider for English learning sessions.

    This agent handles:
    - Phase 3: Feedback in Tanglish (Tamil + English) (~40 seconds)
    - Phase 4: Professional closure in English (~20 seconds)

    The agent provides constructive feedback based on the conversation
    history and ends the session with a polished closing statement.
    """

    def get_timing_config(self) -> SessionTimingConfig:
        """Get timing configuration for feedback phase."""
        return FEEDBACK_TIMING_CONFIG

    async def _on_enter_hook(self) -> None:
        """
        Start the feedback phase.

        Analyzes the conversation history and generates feedback
        for the student based on topics discussed and session metrics.
        """
        logger.info("FeedbackProviderAgent: Starting feedback phase")

        userdata: EnglishTutorContext = self.session.userdata

        # Build context about the session for the AI
        topics_str = ", ".join(userdata.topics_discussed) if userdata.topics_discussed else "various topics"

        feedback_context = (
            f"Start by saying exactly: 'Hold on. We are running out of time. Let's wrap up now'. "
            f"Then, provide constructive feedback based on the conversation. "
            f"The student discussed: {topics_str}. "
            # f"Start with 'Konjam notes eduthukonga, sila corrections share panren.'"
        )

        logger.info(f"Feedback context: {feedback_context}")

        # Generate feedback based on conversation history
        await self.session.generate_reply(
            instructions=feedback_context,
            allow_interruptions=False
        )
        logger.info("FeedbackProviderAgent: Feedback generated")
        await self._graceful_shutdown()
        logger.info("Session shutdown gracefully after feedback")

    def get_goodbye_instruction(self) -> str:
        return "Say goodbye professionally in English"

    def get_session_duration(self) -> int:
        return self.get_timing_config().max_duration
