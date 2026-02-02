"""Conversation Agent for SpeakWithAI."""

from livekit.agents.voice.agent import Agent
import logging
from livekit.agents.llm import function_tool
from livekit.agents.voice import RunContext

from core.session.checkpoints import SessionTimingConfig
from .base_speak_with_ai_agent import BaseSpeakWithAIAgent
from ..context import SpeakWithAIContext
from ..config import CONVERSATION_TIMING_CONFIG

logger = logging.getLogger(__name__)


class ConversationAgent(BaseSpeakWithAIAgent):
    """
    Conversation Agent for question-guided discussions.

    This agent:
    - Uses provided questions as conversation starters/guides
    - Explores topics in depth through casual conversation
    - Tracks which questions have been discussed
    - Transfers to feedback after 8 minutes
    """

    def get_timing_config(self) -> SessionTimingConfig:
        """Get timing configuration for conversation phase."""
        return CONVERSATION_TIMING_CONFIG

    async def _on_enter_hook(self) -> None:
        """Start the conversation phase."""
        logger.info("ConversationAgent: Starting conversation phase")

        userdata: SpeakWithAIContext = self.session.userdata

        if userdata.student_name:
            logger.info(f"Starting conversation with student: {userdata.student_name}")

        # Log available questions
        if userdata.questions:
            logger.info(f"Available questions: {len(userdata.questions)}")
            for q in userdata.questions:
                logger.debug(f"  - {q.identifier}: {q.text[:50]}...")

        # Generate initial greeting
        await self.session.generate_reply(
            instructions=(
                "Greet the student warmly and begin the conversation. "
                "Use the first question naturally as a conversation starter."
            )
        )

    @function_tool()
    async def record_question_discussed(
        self,
        context: RunContext[SpeakWithAIContext],
        identifier: str
    ) -> bool:
        """
        Record when a question topic has been explored in the conversation.

        Use this function when you've meaningfully discussed a question topic.
        This helps track progress and informs the feedback phase.

        Args:
            identifier: The unique identifier of the question that was discussed

        Returns:
            True if question was recorded successfully, False if already recorded
                or question not found
        """
        result = context.userdata.mark_question_discussed(identifier)
        if result:
            question = context.userdata.get_question_by_id(identifier)
            logger.info(f"Question recorded as discussed: {identifier} - {question.text[:50] if question else 'N/A'}...")
        else:
            logger.info(f"Question already discussed or not found: {identifier}")
        return result

    @function_tool()
    async def record_topic_discussed(
        self,
        context: RunContext[SpeakWithAIContext],
        topic: str
    ) -> bool:
        """
        Record a general topic that was discussed during the conversation.

        Use this when the conversation explores a topic beyond the provided
        questions, to help track what was covered for the feedback session.

        Args:
            topic: Brief description of the topic (e.g., "career goals",
                   "learning challenges", "work experience")

        Returns:
            True if topic was recorded successfully
        """
        context.userdata.add_topic(topic)
        logger.info(f"Topic recorded: {topic}")
        return True

    @function_tool()
    async def get_remaining_questions(
        self,
        context: RunContext[SpeakWithAIContext]
    ) -> str:
        """
        Get a list of questions that haven't been discussed yet.

        Use this to check which questions are still available to explore
        when looking for conversation direction.

        Returns:
            Summary of remaining undiscussed questions
        """
        remaining = context.userdata.get_undiscussed_questions()
        if not remaining:
            return "All questions have been discussed."

        lines = []
        for q in remaining:
            lines.append(f"- {q.text} (Hint: {q.hint})")

        return f"Remaining questions ({len(remaining)}):\n" + "\n".join(lines)

    @function_tool()
    async def transfer_to_feedback(
        self,
        context: RunContext[SpeakWithAIContext]
    ) -> Agent:
        """
        Transfer control to the Feedback agent.

        Use this function when the conversation phase is complete
        and you're ready to transition to the feedback phase.

        Returns:
            The FeedbackAgent instance
        """
        logger.info("Transferring to FeedbackAgent")
        await context.wait_for_playout()
        return await self._transfer_to_agent("feedback")
