"""Conversation Partner Agent for English Tutor."""

from livekit.agents.voice.agent import Agent
import logging
from livekit.agents.llm import function_tool
from livekit.agents.voice import RunContext

from core.agents.base import AgentMetadata
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

    @property
    def metadata(self) -> AgentMetadata:
        """Get metadata about this agent."""
        return AgentMetadata(
            name="ConversationPartner",
            version="1.0.0",
            description="Friendly conversation partner for English speaking practice",
            supported_languages=["en"],
            capabilities=["conversation", "topic_tracking", "agent_handoff"]
        )

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
            user_input="Greet the student warmly and begin the onboarding process."
        )

    @function_tool()
    async def record_topic_discussed(
        self,
        context: RunContext[EnglishTutorContext],
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
        context: RunContext[EnglishTutorContext]
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
