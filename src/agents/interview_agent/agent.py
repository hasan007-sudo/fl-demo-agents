"""Interview Agent for conducting interviews."""

import logging
import time
from typing import Optional
from livekit.agents import AgentSession
from livekit.agents.llm import function_tool
from livekit.agents.voice import RunContext

from core.agents.base import BaseAgent
from core.agents.mixins.shutdown import ShutdownMixin
from core.prompts.base import BasePromptBuilder
from .context import InterviewAgentContext
from .prompt_builder import InterviewPromptBuilder

logger = logging.getLogger(__name__)


class InterviewAgent(ShutdownMixin, BaseAgent[InterviewAgentContext]):
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
        self._session_start_time = time.time()
        logger.info("InterviewAgent initialized")

    def get_goodbye_instruction(self) -> str:
        """Get the instruction for generating goodbye message."""
        student_name = self._context.student_name if self._context else "candidate"

        if self._context and self._context.mock_interview:
            # Mock interview: professional, no feedback
            return (
                f"The mock interview is now complete. "
                f"Thank {student_name} professionally for their time. "
                f"Do NOT provide any feedback or evaluation. "
                f"Simply inform them the interview has concluded and wish them well."
            )
        else:
            # Practice mode: warm, encouraging with summary
            return (
                f"The interview practice session is now complete. "
                f"Thank {student_name} warmly for their time and participation. "
                f"Summarize briefly what questions were covered and encourage them "
                f"to keep practicing. Wish them well for their future interviews."
            )

    def get_session_duration(self) -> int:
        """Get the session duration in seconds."""
        return int(time.time() - self._session_start_time)

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

            logger.info(f"Interview mode: {'Mock Interview' if self._context.mock_interview else 'Practice'}")

        # Different greeting based on mode
        if self._context and self._context.mock_interview:
            instructions = (
                "Greet the candidate professionally and begin the mock interview. "
                "Introduce yourself as the interviewer and set a formal tone."
            )
        else:
            instructions = (
                "Greet the candidate warmly and begin the interview practice session. "
            )

        await self.session.generate_reply(instructions=instructions)

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

    @function_tool()
    async def end_session(
        self,
        context: RunContext[InterviewAgentContext]
    ) -> str:
        """
        End the interview practice session gracefully.

        Call this when all questions have been practiced and discussed,
        or when the student indicates they want to end the session.
        This will trigger a goodbye message and close the session.

        Returns:
            Confirmation that the session is ending
        """
        logger.info("end_session tool called - initiating graceful shutdown")

        # Get summary for logging
        discussed = len(context.userdata.questions_discussed)
        total = len(context.userdata.questions)
        logger.info(f"Session ending - Questions covered: {discussed}/{total}")

        # Trigger graceful shutdown
        await self._graceful_shutdown()

        return f"Session ending. Covered {discussed} out of {total} questions."
