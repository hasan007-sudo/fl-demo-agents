"""Interview Preparer Agent implementation."""

import logging

from livekit.agents import AgentSession
from core.agents.base import BaseAgent, AgentMetadata
from core.agents.mixins import TimingMixin, ShutdownMixin
from core.prompts.base import BasePromptBuilder
from core.session.checkpoints import SessionTimingConfig, Checkpoint
from .context import InterviewContext
from .prompt_builder import InterviewPromptBuilder
from .config import TIMING_CONFIG, GOODBYE_INSTRUCTION

logger = logging.getLogger(__name__)


class InterviewPreparerAgent(TimingMixin, ShutdownMixin, BaseAgent[InterviewContext]):
    """AI interview coach for mock interview practice."""

    auto_register = True
    registration_name = "interview_preparer"

    @property
    def metadata(self) -> AgentMetadata:
        """Get metadata about this agent."""
        return AgentMetadata(
            name="Interview Preparer",
            version="1.0.0",
            description="AI interview coach for mock interview practice",
            supported_languages=["en"],
            capabilities=[
                "mock_interviews",
                "behavioral_questions",
                "technical_interviews",
                "interview_feedback",
                "answer_coaching",
                "confidence_building"
            ]
        )

    def _create_default_prompt_builder(self) -> BasePromptBuilder:
        """Create the default prompt builder for Interview Preparer."""
        return InterviewPromptBuilder()

    def _get_default_instructions(self) -> str:
        """Get default instructions when no context is available."""
        return self._prompt_builder.build_default()

    def get_timing_config(self) -> SessionTimingConfig:
        """Get timing configuration from config file."""
        return TIMING_CONFIG

    async def _on_checkpoint_reached(self, checkpoint: Checkpoint, idx: int) -> None:
        """Handle checkpoint by sending AI instruction."""
        if checkpoint.ai_instruction:
            try:
                logger.info(f"Interview checkpoint {idx + 1}: Sending AI instruction")
                self.session.generate_reply(user_input=checkpoint.ai_instruction)
            except Exception as e:
                logger.warning(f"Failed to send checkpoint {idx + 1} instruction: {e}")

    async def _on_session_timeout(self) -> None:
        """Handle session timeout by triggering graceful shutdown."""
        await self._graceful_shutdown()

    def get_goodbye_instruction(self) -> str:
        """Get goodbye instruction from config."""
        return GOODBYE_INSTRUCTION

    def get_session_duration(self) -> int:
        """Get session duration from timing config."""
        return self.get_timing_config().max_duration

    async def on_enter(self) -> None:
        """Called when agent becomes active in the session."""
        print("🔥 INTERVIEW PREPARER: on_enter CALLED!")

        try:
            self.session.generate_reply(
                user_input="Start by greeting the candidate warmly by name if provided"
            )

            logger.info(
                f"Interview session started for candidate: "
                f"{self.context.candidate_name if self.context else 'Unknown'}"
            )

            if self.context:
                logger.info(
                    f"Interview config - Type: {self.context.interview_type}, "
                    f"Role: {self.context.job_role}, "
                    f"Level: {self.context.experience_level}"
                )

            self._init_timing()

            logger.info("Interview session initialized")
        except Exception as e:
            print(f"❌ ERROR IN on_enter: {e}")
            import traceback
            traceback.print_exc()
            raise

    async def _on_session_ended_hook(self, session: AgentSession) -> None:
        """Called when an interview session ends."""
        logger.info("Interview session ended")
        await self._stop_timing()

    async def _validate_context_hook(self, context: InterviewContext) -> bool:
        """Validate context for Interview Preparer."""
        return True

    def get_interview_questions(self) -> list:
        """
        Get a list of interview questions based on context.

        This method can be expanded to include a question bank.

        Returns:
            List of relevant interview questions
        """
        if not self.context:
            return []

        questions = []

        # Technical interview questions
        if self.context.interview_type == "technical":
            if self.context.job_role == "software_engineer":
                questions = [
                    "Can you explain the difference between a stack and a queue?",
                    "How would you design a URL shortening service?",
                    "What's your approach to debugging a performance issue?",
                    "Describe a challenging technical problem you solved recently."
                ]
            elif self.context.job_role == "data_scientist":
                questions = [
                    "Explain the difference between supervised and unsupervised learning.",
                    "How do you handle missing data in a dataset?",
                    "What metrics would you use to evaluate a classification model?",
                    "Describe a data project you're most proud of."
                ]

        # Behavioral interview questions
        elif self.context.interview_type == "behavioral":
            questions = [
                "Tell me about a time you faced a conflict with a teammate.",
                "Describe a situation where you had to meet a tight deadline.",
                "Give an example of when you showed leadership.",
                "Tell me about a failure and what you learned from it.",
                "How do you prioritize when everything seems urgent?"
            ]

        # HR interview questions
        elif self.context.interview_type == "hr":
            questions = [
                "Why are you interested in this position?",
                "Where do you see yourself in 5 years?",
                "What are your salary expectations?",
                "Why are you leaving your current job?",
                "What makes you the best candidate for this role?"
            ]

        return questions