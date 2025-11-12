"""English Tutor Agent implementation."""

import logging

from livekit.agents import AgentSession
from core.agents.base import BaseAgent, AgentMetadata
from core.agents.mixins import TimingMixin, ShutdownMixin
from core.prompts.base import BasePromptBuilder
from core.session.checkpoints import SessionTimingConfig, Checkpoint
from .context import EnglishTutorContext
from .prompt_builder import EnglishTutorPromptBuilder
from .config import TIMING_CONFIG, GOODBYE_INSTRUCTION

logger = logging.getLogger(__name__)


class EnglishTutorAgent(TimingMixin, ShutdownMixin, BaseAgent[EnglishTutorContext]):
    """AI English tutor for conversational practice."""

    auto_register = True
    registration_name = "english_tutor"

    @property
    def metadata(self) -> AgentMetadata:
        """Get metadata about this agent."""
        return AgentMetadata(
            name="English Tutor",
            version="1.0.0",
            description="AI English tutor for conversational practice",
            supported_languages=["en"],
            capabilities=[
                "conversation_practice",
                "grammar_correction",
                "pronunciation_help",
                "vocabulary_building",
                "fluency_improvement"
            ]
        )

    def _create_default_prompt_builder(self) -> BasePromptBuilder:
        """Create the default prompt builder for English Tutor."""
        return EnglishTutorPromptBuilder()

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
                logger.info(f"Checkpoint {idx + 1}: Sending AI instruction")
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
        print("🔥 ENGLISH TUTOR: on_enter CALLED!")

        try:
            self.session.generate_reply(
                user_input="Start by greeting the student warmly by name if provided"
            )

            logger.info(
                f"English Tutor session started for student: "
                f"{self.context.student_name if self.context else 'Unknown'}"
            )

            if self.context:
                logger.info(
                    f"Session config - Proficiency: {self.context.proficiency_level}, "
                    f"Speed: {self.context.speaking_speed}, "
                    f"Correction: {self.context.correction_preference}"
                )

            self._init_timing()

            logger.info("English Tutor session initialized")
        except Exception as e:
            print(f"❌ ERROR IN on_enter: {e}")
            import traceback
            traceback.print_exc()
            raise

    async def _on_session_ended_hook(self, session: AgentSession) -> None:
        """Called when a session ends."""
        logger.info("English Tutor session ended")
        await self._stop_timing()

    async def _validate_context_hook(self, context: EnglishTutorContext) -> bool:
        """Validate context for English Tutor."""
        return True


class Assistant(EnglishTutorAgent):
    """Backward compatibility alias for the original Assistant class."""
    pass