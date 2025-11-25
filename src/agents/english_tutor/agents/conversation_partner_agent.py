"""Conversation Partner Agent for English Tutor."""

import logging
from livekit.agents import Agent
from livekit.agents.llm import function_tool
from livekit.agents.voice import RunContext

from .base_tutor_agent import BaseTutorAgent
from ..shared.session_data import EnglishTutorSessionData

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

    async def _on_enter_hook(self) -> None:
        """
        Start the conversation phase.

        Generates an initial greeting to welcome the student and
        begin the onboarding process.
        """
        logger.info("ConversationPartnerAgent: Starting conversation phase")

        userdata: EnglishTutorSessionData = self.session.userdata

        # Log student info
        if userdata.student_name:
            logger.info(f"Starting conversation with student: {userdata.student_name}")

        # Generate initial greeting
        self.session.generate_reply(
            user_input="Greet the student warmly and begin the onboarding process."
        )

    @function_tool()
    async def record_topic_discussed(
        self,
        context: RunContext[EnglishTutorSessionData],
        topic: str
    ) -> str:
        """
        Record a topic that was discussed during the conversation.

        Use this function when the conversation shifts to a new topic
        to help track what was covered for the feedback session.

        Args:
            topic: Brief description of the topic (e.g., "job interview preparation",
                   "travel experiences", "daily routine")

        Returns:
            Confirmation message
        """
        context.userdata.add_topic(topic)
        logger.info(f"Topic recorded: {topic}")
        return f"Topic '{topic}' recorded successfully."

    @function_tool()
    async def transfer_to_feedback(
        self,
        context: RunContext[EnglishTutorSessionData]
    ) -> Agent:
        """
        Transfer control to the Feedback Provider agent.

        Use this function when you've completed about 4 minutes of speaking
        practice and are ready to transition to the feedback phase.

        The system will automatically trigger this after the time checkpoint,
        but you can also call it manually if the conversation naturally concludes.

        Returns:
            The FeedbackProviderAgent instance
        """
        logger.info("Transferring to FeedbackProviderAgent")

        # Optional: Say a brief transition message
        # (User preference: "brief pause with tone change")
        # The feedback agent will start directly, so no explicit message needed

        return await self._transfer_to_agent("feedback")
