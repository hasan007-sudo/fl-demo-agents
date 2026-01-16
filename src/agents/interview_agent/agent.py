"""Interview Agent for conducting interviews."""

import logging
from typing import Optional
from livekit.agents import AgentSession
from livekit.agents.llm import function_tool
from livekit.agents.voice import RunContext

from core.agents.base import BaseAgent
from core.agents.mixins.shutdown import ShutdownMixin
from core.agents.mixins.timing import TimingMixin
from core.session.checkpoints import SessionTimingConfig, Checkpoint
from core.prompts.base import BasePromptBuilder
from .context import InterviewAgentContext
from .prompt_builder import InterviewPromptBuilder
from .config import get_timing_config

logger = logging.getLogger(__name__)


class InterviewAgent(TimingMixin, ShutdownMixin, BaseAgent[InterviewAgentContext]):
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
        # Store timing config based on mode
        is_mock = context.mock_interview if context else False
        self._timing_config = get_timing_config(is_mock)

        logger.info(
            f"InterviewAgent initialized - Mode: {'Mock Interview' if is_mock else 'Practice'}, "
            f"Duration: {self._timing_config.max_duration}s, "
            f"Checkpoints: {len(self._timing_config.checkpoints)}"
        )

    def get_timing_config(self) -> SessionTimingConfig:
        """Get the timing configuration for this agent."""
        return self._timing_config

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

            mode = 'Mock Interview' if self._context.mock_interview else 'Practice'
            logger.info(f"Interview mode: {mode}, Duration: {self._timing_config.max_duration}s")

        # Initialize timing (starts checkpoint monitoring)
        self._init_timing()

        # Different greeting based on mode
        duration_mins = self._timing_config.max_duration // 60
        if self._context and self._context.mock_interview:
            instructions = (
                f"Greet the candidate professionally and begin the mock interview. "
                f"Introduce yourself as the interviewer and set a formal tone. "
                f"This is a {duration_mins}-minute interview session."
            )
        else:
            instructions = (
                f"Greet the candidate warmly and begin the interview practice session. "
                f"This is a {duration_mins}-minute practice session."
            )

        await self.session.generate_reply(instructions=instructions)

    async def _on_checkpoint_reached(self, checkpoint: Checkpoint, idx: int) -> None:
        """Handle regular checkpoint by sending time awareness instruction."""
        if checkpoint.ai_instruction:
            logger.info(f"InterviewAgent: Checkpoint {idx + 1} reached - sending instruction")
            await self.session.generate_reply(instructions=checkpoint.ai_instruction)

    async def _on_session_timeout(self, checkpoint: Checkpoint, idx: int) -> None:
        """Handle final checkpoint - end the session gracefully."""
        logger.warning(f"InterviewAgent: Final checkpoint reached at {checkpoint.time}s - ending session")
        await self._graceful_shutdown()

    async def _on_session_ended_hook(self, session: AgentSession) -> None:
        """Hook for session end logic."""
        logger.info("InterviewAgent: Session ended")
        await self._stop_timing()

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
    async def get_time_remaining(
        self,
        context: RunContext[InterviewAgentContext]
    ) -> str:
        """
        Check how much time is remaining in the interview session.

        Use this to be aware of time constraints and pace the interview
        appropriately.

        Returns:
            String describing remaining time
        """
        total = self._timing_config.max_duration
        elapsed = int(self._timer.elapsed_time()) if self._timer else 0
        remaining = max(0, total - elapsed)

        if remaining <= 0:
            return "Time has expired. Please conclude the interview."
        elif remaining <= 60:
            return f"Less than 1 minute remaining ({remaining}s). Wrap up now."
        elif remaining <= 120:
            return f"About {remaining // 60} minute(s) remaining. Begin wrapping up."
        else:
            return f"{remaining // 60} minutes remaining ({elapsed}s elapsed of {total}s total)."

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
