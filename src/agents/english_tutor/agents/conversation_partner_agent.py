"""Conversation Partner Agent for English Tutor."""

from livekit.agents.voice.agent import Agent
import logging
from livekit.agents.llm import function_tool
from livekit.agents.voice import RunContext

from core.agents.base import BaseAgent
from core.session.checkpoints import SessionTimingConfig
from .base_tutor_agent import BaseTutorAgent
from ..context import EnglishTutorContext
from ..config import CONVERSATION_TIMING_CONFIG

logger = logging.getLogger(__name__)


class ConversationPartnerAgent(BaseTutorAgent):
    """
    Conversation Partner for English learning sessions.

    This agent handles:
    - Phase 1: Greeting and onboarding (10%)
    - Phase 2: Natural speaking practice (90%)

    The agent acts as a friendly conversational partner, engaging
    students in natural dialogue without real-time corrections.
    After ~4 minutes, it transfers to the FeedbackProviderAgent.
    """

    def get_timing_config(self) -> SessionTimingConfig:
        """Get timing configuration for conversation phase."""
        return CONVERSATION_TIMING_CONFIG

    async def _on_enter_hook(self) -> None:
        """
        Start the conversation phase.

        Generates an initial greeting to welcome the student and
        begin the onboarding process.
        """
        logger.info("ConversationPartnerAgent: Starting conversation phase")

        userdata: EnglishTutorContext = self.session.userdata

        # Log student info
        if userdata.student_name:
            logger.info(f"Starting conversation with student: {userdata.student_name}")

        # Generate initial greeting
        await self.session.generate_reply(
            instructions="Greet the student warmly and begin the onboarding process."
        )

    @function_tool()
    async def record_topic_discussed(
        self,
        context: RunContext[EnglishTutorContext],
        topic: str
    ) -> bool:
        """
        Record a topic that was discussed during the conversation.

        Use this function when the conversation shifts to a new topic
        to help track what was covered for the feedback session.

        Args:
            topic: Brief description of the topic (e.g., "job interview preparation",
                   "travel experiences", "daily routine")

        Returns:
            True if topic was recorded successfully
        """
        context.userdata.add_topic(topic)
        logger.info(f"Topic recorded: {topic}")
        return True

    @function_tool()
    async def transfer_to_feedback(
        self,
        context: RunContext[EnglishTutorContext]
    ) -> Agent:
        """
        Transfer control to the Feedback Provider agent.

        Use this function when you've completed about 3 minutes of speaking
        practice and are ready to transition to the feedback phase.

        Returns:
            The FeedbackProviderAgent instance
        """
        logger.info("Transferring to FeedbackProviderAgent")
        return await self._transfer_to_agent("feedback")
