"""
English Tutor Agent implementation.

This maintains 100% compatibility with the existing Assistant class
while using the new architecture.
"""

from typing import Optional
import logging
import time
import asyncio
import os

from livekit.agents import AgentSession
from livekit.agents.job import get_job_context
from livekit import api
from core.agents.base import BaseAgent, AgentMetadata
from core.prompts.base import BasePromptBuilder
from .context import EnglishTutorContext
from .prompt_builder import EnglishTutorPromptBuilder

logger = logging.getLogger(__name__)

# Session duration constants
MAX_SESSION_DURATION = 300  # 5 minutes in seconds

# Time checkpoint configuration
# Each checkpoint defines when to notify frontend and AI (without telling user about time)
CHECKPOINTS = [
    {
        "time": 270,  # 4.5 minutes (4min 30sec)
        "frontend_event": True,
        "ai_instruction": "You've been conversing for 4.5 minutes now. Start thinking about wrapping up the conversation naturally in the next 30 seconds, but don't mention time or ending to the student yet.",
        "is_final": False
    },
    {
        "time": 300,  # 5 minutes - HARD CUTOFF
        "frontend_event": True,
        "ai_instruction": None,
        "is_final": True
    }
]


class EnglishTutorAgent(BaseAgent[EnglishTutorContext]):
    """
    English Tutor Agent with dynamic context-based instruction.

    This is the refactored version of the original Assistant class,
    maintaining complete compatibility with existing functionality.
    """

    # Auto-register this agent
    auto_register = True
    registration_name = "english_tutor"

    def __init__(self, *args, **kwargs):
        """Initialize the English Tutor agent with session state tracking."""
        super().__init__(*args, **kwargs)
        self._session_ending = False
        self._session_ended = False

    @property
    def metadata(self) -> AgentMetadata:
        """Get metadata about this agent."""
        return AgentMetadata(
            name="English Tutor",
            version="1.0.0",
            description="AI English tutor for conversational practice",
            supported_languages=["en"],  # Teaches English
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

    async def on_enter(self) -> None:
        """
        Called when agent becomes active in the session.

        Automatically triggered by LiveKit when the agent enters.
        Sends initial greeting and starts checkpoint timers.
        """
        print("🔥 ENGLISH TUTOR: on_enter CALLED!")

        try:
            self.session.generate_reply(user_input="Start by greeting the student warmly by name if provided")

            logger.info(
                f"English Tutor session started for student: "
                f"{self.context.student_name if self.context else 'Unknown'}"
            )

            # Log context details if available
            if self.context:
                logger.info(
                    f"Session config - Proficiency: {self.context.proficiency_level}, "
                    f"Speed: {self.context.speaking_speed}, "
                    f"Correction: {self.context.correction_preference}"
                )

            # Initialize checkpoint timer
            self._session_start_time = time.time()
            self._timer_task = asyncio.create_task(self._elapsed_time_notifier())

            logger.info("English Tutor session initialized with checkpoint timer")
        except Exception as e:
            print(f"❌ ERROR IN on_enter: {e}")
            import traceback
            traceback.print_exc()
            raise

    async def _elapsed_time_notifier(self) -> None:
        """
        Background task that processes time checkpoints and enforces session timeout.

        Uses the CHECKPOINTS array to:
        1. Send time_checkpoint events to frontend at each checkpoint
        2. Silently inform AI about elapsed time (without mentioning to user)
        3. Trigger graceful shutdown at final checkpoint (5min)

        Checkpoints: 180s (3min), 270s (4.5min), 300s (5min - final)
        """
        print("🚀 CHECKPOINT NOTIFIER TASK STARTED!")
        try:
            for idx, checkpoint in enumerate(CHECKPOINTS):
                target_time = checkpoint["time"]

                # Calculate wait time until this checkpoint
                elapsed = time.time() - self._session_start_time
                wait_time = target_time - elapsed

                if wait_time > 0:
                    await asyncio.sleep(wait_time)

                # Check if session is still active
                if not self.session or self._session_ending or self._session_ended:
                    logger.info(f"Session ended before checkpoint {idx + 1}")
                    break

                # Send frontend event if configured
                if checkpoint["frontend_event"]:
                    remaining = MAX_SESSION_DURATION - target_time
                    await self._publish_session_event(
                        event_type="time_checkpoint",
                        status="in_progress" if not checkpoint["is_final"] else "ending",
                        reason="checkpoint",
                        metadata={
                            "elapsed_seconds": target_time,
                            "remaining_seconds": remaining,
                            "checkpoint_index": idx,
                            "total_duration": MAX_SESSION_DURATION,
                            "is_final": checkpoint["is_final"]
                        }
                    )
                    print(f"✅ Sent checkpoint {idx + 1} event to frontend ({target_time}s)")

                # Handle final checkpoint (shutdown) vs regular checkpoint (AI instruction)
                if checkpoint["is_final"]:
                    print(f"⏰ FINAL CHECKPOINT REACHED ({target_time}s)!")
                    logger.warning(f"Session reached final checkpoint at {target_time}s - initiating shutdown")
                    await self._graceful_shutdown()
                    break
                elif checkpoint["ai_instruction"]:
                    # Send AI instruction (without user seeing time mention)
                    try:
                        print(f"⏰ Checkpoint {idx + 1} ({target_time}s): Informing AI silently")
                        self.session.generate_reply(user_input=checkpoint["ai_instruction"])
                        logger.info(f"Checkpoint {idx + 1} AI instruction sent")
                    except Exception as e:
                        logger.warning(f"Failed to send checkpoint {idx + 1} instruction: {e}")

        except asyncio.CancelledError:
            logger.info("Checkpoint notifier task cancelled")
            raise
        except Exception as e:
            logger.error(f"Error in checkpoint notifier: {e}", exc_info=True)

    async def _graceful_shutdown(self) -> None:
        """
        Perform graceful shutdown of the session at the 5-minute mark.

        This method:
        1. Sets session_ending flag to prevent duplicate shutdowns
        2. Sends "session_ending" event to frontend via data channel
        3. Instructs the agent to say a brief goodbye without allowing interruptions
        4. Waits for the actual TTS playout to complete using SpeechHandle
        5. Disconnects the session

        Note: User input is effectively ignored at this point as the agent
        is instructed to deliver its goodbye message and the session ends immediately after.
        """
        if self._session_ending or self._session_ended:
            return

        self._session_ending = True
        logger.info("Starting graceful shutdown sequence")

        try:
            # Step 1: Notify frontend that session is ending
            await self._publish_session_event(
                event_type="session_status",
                status="ending",
                reason="timeout",
                metadata={"duration_seconds": MAX_SESSION_DURATION}
            )
            print("✅ Sent 'session_ending' event to frontend")

            # Step 2: Generate final goodbye message and wait for TTS playout to complete
            if self.session:
                goodbye_instruction = (
                    "Provide a brief, warm closing with feedback for the student as given in your system prompt. "
                    "Do NOT mention that time is up or that the session is ending. "
                    "Keep it under 20 seconds."
                )

                print("👋 Generating goodbye message and waiting for speech to complete")

                # Generate reply returns a SpeechHandle that we can await for playout completion
                speech_handle = self.session.generate_reply(
                    user_input=goodbye_instruction,
                    allow_interruptions=False  # Don't allow interruption during goodbye
                )
                logger.info("Goodbye message generated")

                # Step 3: Wait for the actual audio playout to complete (TTS + playback)
                try:
                    await asyncio.wait_for(speech_handle.wait_for_playout(), timeout=30)
                    logger.info("Goodbye message playout completed")
                except asyncio.TimeoutError:
                    logger.warning("Goodbye playout timed out; proceeding to end session")

            print("🛑 Ending session...")
            self._session_ended = True

            # Delete the room using server API - this disconnects ALL participants
            try:
                job_ctx = get_job_context()
                api_client = api.LiveKitAPI(
                    os.getenv("LIVEKIT_URL"),
                    os.getenv("LIVEKIT_API_KEY"),
                    os.getenv("LIVEKIT_API_SECRET"),
                )
                await api_client.room.delete_room(api.DeleteRoomRequest(
                    room=job_ctx.room.name,
                ))
                logger.info("Room deleted successfully - all participants disconnected")
            except Exception as e:
                logger.debug(f"Could not delete room: {e}")

        except Exception as e:
            logger.error(f"Error during graceful shutdown: {e}", exc_info=True)
            # Even if there's an error, mark as ended to prevent retries
            self._session_ended = True

    async def _on_session_ended_hook(self, session: AgentSession) -> None:
        """
        Called when a session ends.

        Args:
            session: The agent session that is ending
        """
        logger.info("English Tutor session ended")

        # Stop the timing task
        if hasattr(self, '_timer_task'):
            self._timer_task.cancel()
            try:
                await self._timer_task
            except asyncio.CancelledError:
                logger.info("Timer task cancelled successfully")

    async def _validate_context_hook(self, context: EnglishTutorContext) -> bool:
        """
        Validate that the context is valid for English Tutor.

        Args:
            context: The context to validate

        Returns:
            True if context is valid
        """
        # Context validation is done in the context class itself
        # Additional agent-specific validation can be added here
        return True


# For backward compatibility, also provide the original Assistant class name
class Assistant(EnglishTutorAgent):
    """
    Backward compatibility alias for the original Assistant class.

    This ensures existing code using 'Assistant' continues to work.
    """
    pass