"""Interview Agent for conducting interviews."""

import logging
from typing import Optional
from livekit.agents import AgentSession
from livekit.agents.llm import function_tool
from livekit.agents.voice import RunContext

from core.agents.base import BaseAgent
from core.prompts.base import BasePromptBuilder
from .context import InterviewAgentContext
from .prompt_builder import InterviewPromptBuilder

logger = logging.getLogger(__name__)


class InterviewAgent(BaseAgent[InterviewAgentContext]):
    """
    Interview Agent for question-guided interviews.

    This agent:
    - Uses provided questions as interview guides
    - Explores topics in depth through professional conversation
    - Tracks which questions have been discussed
    """

    def __init__(
        self,
        context: Optional[InterviewAgentContext] = None,
        prompt_builder: Optional[BasePromptBuilder] = None,
        **kwargs
    ):
        super().__init__(
            context=context,
            prompt_builder=prompt_builder,
            **kwargs
        )
        logger.info("InterviewAgent initialized")

    def _create_default_prompt_builder(self) -> BasePromptBuilder:
        """Create the default prompt builder."""
        return InterviewPromptBuilder()

    def _get_default_instructions(self) -> str:
        """Get default instructions when no context is available."""
        return "You are a professional interviewer. Conduct the interview professionally."

    async def on_enter(self) -> None:
        """Called when agent becomes active in the session."""
        logger.info("InterviewAgent: Starting interview session")

        if self._context:
            if self._context.student_name:
                logger.info(f"Starting interview with candidate: {self._context.student_name}")

            if self._context.questions:
                logger.info(f"Available questions: {len(self._context.questions)}")
                for q in self._context.questions:
                    logger.debug(f"  - {q.identifier}: {q.text[:50]}...")

        await self.session.generate_reply(
            instructions=(
                "Greet the candidate warmly and begin the interview. "
                # "Use the first question naturally as an opener."
            )
        )

    async def _on_session_ended_hook(self, session: AgentSession) -> None:
        """Hook for session end logic."""
        logger.info("InterviewAgent: Session ended")

    async def _validate_context_hook(self, context: InterviewAgentContext) -> bool:
        """Validate the context."""
        return context is not None

    @function_tool()
    async def record_question_discussed(
        self,
        context: RunContext[InterviewAgentContext],
        identifier: str
    ) -> bool:
        """
        Record when a question topic has been explored in the interview.

        Use this function when you've meaningfully discussed a question topic.
        This helps track interview progress.

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
        context: RunContext[InterviewAgentContext],
        topic: str
    ) -> bool:
        """
        Record a general topic that was discussed during the interview.

        Use this when the conversation explores a topic beyond the provided
        questions, to help track what was covered.

        Args:
            topic: Brief description of the topic (e.g., "career goals",
                   "technical skills", "work experience")

        Returns:
            True if topic was recorded successfully
        """
        context.userdata.add_topic(topic)
        logger.info(f"Topic recorded: {topic}")
        return True

    @function_tool()
    async def get_remaining_questions(
        self,
        context: RunContext[InterviewAgentContext]
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
