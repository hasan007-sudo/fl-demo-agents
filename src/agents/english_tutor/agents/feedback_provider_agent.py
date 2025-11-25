"""Feedback Provider Agent for English Tutor."""

import logging
from livekit.agents.llm import function_tool
from livekit.agents.voice import RunContext

from .base_tutor_agent import BaseTutorAgent
from ..shared.session_data import EnglishTutorSessionData

logger = logging.getLogger(__name__)


class FeedbackProviderAgent(BaseTutorAgent):
    """
    Feedback Provider for English learning sessions.

    This agent handles:
    - Phase 3: Feedback in Tanglish (Tamil + English) (~40 seconds)
    - Phase 4: Professional closure in English (~20 seconds)

    The agent provides constructive feedback based on the conversation
    history and ends the session with a polished closing statement.
    """

    async def _on_enter_hook(self) -> None:
        """
        Start the feedback phase.

        Analyzes the conversation history and generates feedback
        for the student based on topics discussed and session metrics.
        """
        logger.info("FeedbackProviderAgent: Starting feedback phase")

        userdata: EnglishTutorSessionData = self.session.userdata

        # Build context about the session for the AI
        topics_str = ", ".join(userdata.topics_discussed) if userdata.topics_discussed else "various topics"

        feedback_context = (
            f"The student discussed: {topics_str}. "
            f"Provide constructive feedback based on the conversation. "
            f"Start with 'Konjam notes eduthukonga, sila corrections share panren.'"
        )

        logger.info(f"Feedback context: {feedback_context}")

        # Generate feedback based on conversation history
        self.session.generate_reply(
            user_input=feedback_context
        )

    @function_tool()
    async def finalize_session(
        self,
        context: RunContext[EnglishTutorSessionData]
    ) -> str:
        """
        Finalize the session after providing feedback.

        Use this function after you've completed the closure statement
        to signal that the session should end gracefully.

        Returns:
            Session finalization confirmation
        """
        logger.info("Session finalized - preparing to end")

        # The session will end naturally after this
        # No need to explicitly trigger anything - LiveKit handles it

        return "Session finalized successfully"
