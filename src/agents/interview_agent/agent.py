"""Interview Agent for conducting interviews."""

import logging
import time
from typing import Optional

from livekit.agents import AgentSession
from livekit.agents.llm import function_tool
from livekit.agents.voice import RunContext

from core.agents.base import BaseAgent
from core.agents.mixins.shutdown import ShutdownMixin
from core.agents.mixins.timing import TimingMixin
from core.session.checkpoints import SessionTimingConfig, Checkpoint
from core.prompts.base import BasePromptBuilder
from .context import InterviewAgentContext, InterviewMode
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
        mode = context.mode if context else InterviewMode.PRACTICE
        self._timing_config = get_timing_config(mode)

        logger.info(
            f"InterviewAgent initialized - Mode: {mode.value}, "
            f"Duration: {self._timing_config.max_duration}s, "
            f"Checkpoints: {len(self._timing_config.checkpoints)}"
        )

    def get_timing_config(self) -> SessionTimingConfig:
        """Get the timing configuration for this agent."""
        return self._timing_config

    def get_goodbye_instruction(self) -> str:
        """Get the instruction for generating goodbye message."""
        student_name = self._context.student_name if self._context else "candidate"
        mode = self._context.mode if self._context else InterviewMode.PRACTICE

        if mode == InterviewMode.MOCK:
            # Mock interview: professional, no feedback
            return (
                f"The mock interview is now complete. "
                f"Thank {student_name} professionally for their time. "
                f"Do NOT provide any feedback or evaluation. "
                f"Simply inform them the interview has concluded and wish them well."
            )
        elif mode == InterviewMode.DIAGNOSTIC:
            # Diagnostic mode: encouraging with activity summary
            return (
                f"The diagnostic activity is now complete. "
                f"Thank {student_name} warmly for their participation. "
                f"Encourage them to review the feedback provided and keep practicing."
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
        return int(self._timer.elapsed_time()) if self._timer else 0

    def _create_default_prompt_builder(self) -> BasePromptBuilder:
        """Create the default prompt builder."""
        return InterviewPromptBuilder()

    def _get_default_instructions(self) -> str:
        """Get default instructions when no context is available."""
        return (
            "You are a professional interviewer. Conduct the interview professionally."
        )

    def _select_start_question_id(self) -> Optional[str]:
        """Select the first question to ask, accounting for resume state."""
        if not self._context:
            return None

        current_id = self._context.current_question_id
        if (
            current_id
            and self._context.get_question_by_id(current_id)
            and current_id not in self._context.questions_discussed
        ):
            return current_id

        remaining = self._context.get_undiscussed_questions()
        if not remaining:
            return None

        return remaining[0].identifier

    async def _restore_resume_chat_context(self) -> int:
        """
        Restore prior finalized turns into model chat context for resumed sessions.

        Returns:
            Number of transcript turns restored.
        """
        if not self._context or not self._context.is_resumed:
            return 0

        turns_to_restore = self._context.resume_transcript_turns
        if not turns_to_restore:
            return 0

        try:
            chat_ctx = self.chat_ctx.copy()
            chat_ctx.add_message(
                role="system",
                content=(
                    "This is a resumed interview session. Continue naturally from prior "
                    "conversation context and do not restart completed questions."
                ),
            )
            for turn in turns_to_restore:
                chat_ctx.add_message(role=turn.role, content=turn.text)

            await self.update_chat_ctx(chat_ctx)
            logger.info(
                f"Restored {len(turns_to_restore)} transcript turns for resumed session"
            )
            return len(turns_to_restore)
        except Exception as e:
            logger.warning(f"Failed to restore resume transcript turns: {e}")
            return 0

    async def on_enter(self) -> None:
        """Called when agent becomes active in the session."""
        restored_turn_count = 0

        logger.info(
            f"[DEBUG] on_enter - context: {self._context is not None}, questions: {len(self._context.questions) if self._context and self._context.questions else 0}"
        )
        if self._context:
            logger.info(
                f"[DEBUG] is_resumed={self._context.is_resumed}, current_question_id={self._context.current_question_id}, questions_discussed={self._context.questions_discussed}"
            )

        if self._context:
            if self._context.student_name:
                logger.info(
                    f"Starting interview with candidate: {self._context.student_name}"
                )

            if self._context.questions:
                logger.info(f"Available questions: {len(self._context.questions)}")
                for q in self._context.questions:
                    logger.debug(f"  - {q.identifier}: {q.text[:50]}...")

                # Emit questions_list event to frontend
                await self._publish_session_event(
                    event_type="questions_list",
                    status="ready",
                    metadata={
                        "questions": self._context.get_questions_for_frontend(),
                        "total_count": len(self._context.questions),
                    },
                )

            logger.info(
                f"Interview mode: {self._context.mode.value}, Duration: {self._timing_config.max_duration}s"
            )
            restored_turn_count = await self._restore_resume_chat_context()

            if self._context.resume_rejected_reason:
                await self._publish_session_event(
                    event_type="resume_state_rejected",
                    status="warning",
                    reason=self._context.resume_rejected_reason,
                    metadata={
                        "is_resumed": self._context.is_resumed,
                        "current_question_id": self._context.current_question_id,
                        "questions_discussed": self._context.questions_discussed,
                        "restored_turn_count": restored_turn_count,
                    },
                )

            await self._publish_session_event(
                event_type="resume_state_applied",
                status="ready",
                metadata={
                    "is_resumed": self._context.is_resumed,
                    "current_question_id": self._context.current_question_id,
                    "questions_discussed": self._context.questions_discussed,
                    "remaining_count": len(self._context.get_undiscussed_questions()),
                    "restored_turn_count": restored_turn_count,
                },
            )

        # Initialize timing (starts checkpoint monitoring)
        self._init_timing()

        # Select next question identifier, accounting for resumed state.
        first_question_id = self._select_start_question_id()

        if self._context and self._context.questions and first_question_id is None:
            logger.info("No remaining questions to ask. Ending session.")
            await self._graceful_shutdown()
            return

        # Different greeting based on mode
        duration_mins = self._timing_config.max_duration // 60
        mode = self._context.mode if self._context else InterviewMode.PRACTICE

        if mode == InterviewMode.MOCK:
            instructions = (
                f"Greet the candidate professionally and introduce yourself as the interviewer. "
                f"This is a {duration_mins}-minute mock interview session. "
            )
            if first_question_id:
                instructions += (
                    f"After the greeting, call start_question(\"{first_question_id}\") "
                    f"and ask ONLY that first question. Do not ask multiple questions at once."
                )
            await self.session.generate_reply(instructions=instructions)

        elif mode == InterviewMode.DIAGNOSTIC:
            # Diagnostic mode: No greeting, jump straight to the question
            if first_question_id:
                await self.session.generate_reply(
                    instructions=(
                        f"Call start_question(\"{first_question_id}\") and ask ONLY that question directly. "
                        f"Do not greet or introduce yourself - just ask the question."
                    )
                )

        else:
            # Practice mode
            instructions = (
                f"Greet the candidate warmly in their comfortable language. Generate text in that language. "
                f"This is a {duration_mins}-minute practice session. "
            )
            if first_question_id:
                instructions += (
                    f"After the greeting, call start_question(\"{first_question_id}\") "
                    f"and ask ONLY that first question. Ask one question at a time."
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

    def _get_question_index(self, identifier: str) -> int:
        """Get the index of a question by its identifier."""
        if not self._context:
            return -1
        for i, q in enumerate(self._context.questions):
            if q.identifier == identifier:
                return i
        return -1

    @function_tool()
    async def start_question(
        self,
        context: RunContext[InterviewAgentContext],
        identifier: str
    ) -> str:
        """
        Start discussing a question. Call this BEFORE asking any question.

        This sets the question as currently being discussed and notifies the frontend.
        You MUST call this before asking each question from the list.

        Args:
            identifier: The unique identifier of the question to start

        Returns:
            The question text and description to ask, or error message if not found
        """
        question = context.userdata.set_current_question(identifier)
        if question:
            question_index = self._get_question_index(identifier)
            logger.info(f"Starting question: {identifier} - {question.text[:50]}...")

            # Emit question_started event to frontend
            await self._publish_session_event(
                event_type="question_started",
                status="in_progress",
                metadata={
                    "question_id": identifier,
                    "question_index": question_index,
                }
            )

            return f"Question: {question.text}\nContext: {question.description}"
        else:
            logger.warning(f"Question not found: {identifier}")
            return f"Question with identifier '{identifier}' not found."

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
        question_index = self._get_question_index(identifier)
        result = context.userdata.mark_question_discussed(identifier)

        if result:
            question = context.userdata.get_question_by_id(identifier)
            remaining_count = len(context.userdata.get_undiscussed_questions())
            logger.info(f"Question recorded as discussed: {identifier} - {question.text[:50] if question else 'N/A'}...")

            # Emit question_completed event to frontend
            await self._publish_session_event(
                event_type="question_completed",
                status="completed",
                metadata={
                    "question_id": identifier,
                    "question_index": question_index,
                    "remaining_count": remaining_count,
                }
            )
        else:
            logger.info(f"Question already discussed or not found: {identifier}")
        return result

    # @function_tool()
    # async def record_topic_discussed(
    #     self,
    #     context: RunContext[InterviewAgentContext],
    #     topic: str
    # ) -> bool:
    #     """
    #     Record a general topic that was discussed during the interview.

    #     Use this when the conversation explores a topic beyond the provided
    #     questions, to help track what was covered.

    #     Args:
    #         topic: Brief description of the topic (e.g., "career goals",
    #                "technical skills", "work experience")

    #     Returns:
    #         True if topic was recorded successfully
    #     """
    #     context.userdata.add_topic(topic)
    #     logger.info(f"Topic recorded: {topic}")
    #     return True

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
