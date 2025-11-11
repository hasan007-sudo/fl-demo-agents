"""
Interview Preparer Agent implementation.

Conducts mock interviews to help users prepare for job interviews.
"""

from typing import Optional
import logging
import asyncio
import time
import os

from livekit.agents import AgentSession
from livekit.agents.job import get_job_context
from livekit import api
from core.agents.base import BaseAgent, AgentMetadata
from core.prompts.base import BasePromptBuilder
from .context import InterviewContext
from .prompt_builder import InterviewPromptBuilder

logger = logging.getLogger(__name__)

# Session duration constants
MAX_SESSION_DURATION = 900  # 15 minutes in seconds

# Time checkpoint configuration
# Each checkpoint defines when to notify frontend and AI (without telling user about time)
CHECKPOINTS = [
    {
        "time": 0,  # Initial checkpoint - session start
        "frontend_event": True,
        "ai_instruction": None,  # No AI instruction needed at start
        "is_final": False
    },
    {
        "time": 540,  # 9 minutes
        "frontend_event": True,
        "ai_instruction": "You've been conducting the interview for 9 minutes now. Continue asking relevant questions naturally without mentioning the elapsed time to the candidate.",
        "is_final": False
    },
    {
        "time": 810,  # 13.5 minutes (13min 30sec)
        "frontend_event": True,
        "ai_instruction": "You've been conducting the interview for 13.5 minutes now. Start thinking about wrapping up in the next 90 seconds, but don't mention time or ending to the candidate yet.",
        "is_final": False
    },
    {
        "time": 900,  # 15 minutes - HARD CUTOFF
        "frontend_event": True,
        "ai_instruction": None,  # Triggers graceful_shutdown instead
        "is_final": True
    }
]


class InterviewPreparerAgent(BaseAgent[InterviewContext]):
    """
    Interview Preparer Agent for conducting mock interviews.

    Helps users practice for job interviews with realistic scenarios
    and constructive feedback.
    """

    # Auto-register this agent
    auto_register = True
    registration_name = "interview_preparer"

    def __init__(self, *args, **kwargs):
        """Initialize the Interview Preparer agent with session state tracking."""
        super().__init__(*args, **kwargs)
        self._session_ending = False
        self._session_ended = False

    @property
    def metadata(self) -> AgentMetadata:
        """Get metadata about this agent."""
        return AgentMetadata(
            name="Interview Preparer",
            version="1.0.0",
            description="AI interview coach for mock interview practice",
            supported_languages=["en"],  # Can expand to other languages
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

    async def on_enter(self) -> None:
        """
        Called when agent becomes active in the session.

        Automatically triggered by LiveKit when the agent enters.
        Sends initial greeting and starts checkpoint timers.
        """
        print("🔥 INTERVIEW PREPARER: on_enter CALLED!")

        try:
            # Send initial greeting first
            self.session.generate_reply(user_input="Start by greeting the candidate warmly by name if provided")

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
            self._session_start_time = time.time()
            self._timer_task = asyncio.create_task(self._elapsed_time_notifier())

            logger.info("Interview session initialized with checkpoint timer")
        except Exception as e:
            print(f"❌ ERROR IN on_enter: {e}")
            import traceback
            traceback.print_exc()
            raise

    async def _on_session_ended_hook(self, session: AgentSession) -> None:
        """
        Called when an interview session ends.

        Args:
            session: The agent session that is ending
        """
        logger.info("Interview session ended")

        # Stop the timing task
        if hasattr(self, '_timer_task'):
            self._timer_task.cancel()
            try:
                await self._timer_task
            except asyncio.CancelledError:
                logger.info("Timer task cancelled successfully")

        # Could log interview metrics here
        # e.g., number of questions asked, duration, etc.

    async def _elapsed_time_notifier(self) -> None:
        """
        Background task that processes time checkpoints and enforces session timeout.

        Uses the CHECKPOINTS array to:
        1. Send time_checkpoint events to frontend at each checkpoint
        2. Silently inform AI about elapsed time (without mentioning to candidate)
        3. Trigger graceful shutdown at final checkpoint (5min)

        Checkpoints: 180s (3min), 270s (4.5min), 300s (5min - final)
        """
        print("🚀 INTERVIEW CHECKPOINT NOTIFIER TASK STARTED!")
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
                    logger.info(f"Interview session ended before checkpoint {idx + 1}")
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
                    print(f"✅ Sent interview checkpoint {idx + 1} event to frontend ({target_time}s)")

                # Handle final checkpoint (shutdown) vs regular checkpoint (AI instruction)
                if checkpoint["is_final"]:
                    print(f"⏰ FINAL INTERVIEW CHECKPOINT REACHED ({target_time}s)!")
                    logger.warning(f"Interview session reached final checkpoint at {target_time}s - initiating shutdown")
                    await self._graceful_shutdown()
                    break
                elif checkpoint["ai_instruction"]:
                    # Send AI instruction (without candidate seeing time mention)
                    try:
                        print(f"⏰ Interview Checkpoint {idx + 1} ({target_time}s): Informing AI silently")
                        self.session.generate_reply(user_input=checkpoint["ai_instruction"])
                        logger.info(f"Interview checkpoint {idx + 1} AI instruction sent")
                    except Exception as e:
                        logger.warning(f"Failed to send interview checkpoint {idx + 1} instruction: {e}")

        except asyncio.CancelledError:
            logger.info("Interview checkpoint notifier task cancelled")
            raise
        except Exception as e:
            logger.error(f"Error in interview checkpoint notifier: {e}", exc_info=True)

    async def _graceful_shutdown(self) -> None:
        """
        Perform graceful shutdown of the interview session at the 15-minute mark.

        This method:
        1. Sets session_ending flag to prevent duplicate shutdowns
        2. Sends "session_ending" event to frontend via data channel
        3. Instructs the agent to say a brief goodbye with brief feedback
        4. Waits for the actual TTS playout to complete using SpeechHandle
        5. Disconnects the session

        Note: Candidate input is effectively ignored at this point as the agent
        is instructed to deliver its goodbye message and the session ends immediately after.
        """
        if self._session_ending or self._session_ended:
            return

        self._session_ending = True
        logger.info("Starting graceful shutdown sequence for interview session")

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
                    "Provide a brief, warm closing with feedback for the candidate. "
                    "Do NOT mention that time is up or the interview is ending. "
                    "Give one sentence of constructive feedback about their performance, then thank them and wish them well. "
                    "Keep it under 20 seconds."
                )

                print("👋 Generating interview closing message and waiting for speech to complete")

                # Generate reply returns a SpeechHandle that we can await for playout completion
                speech_handle = self.session.generate_reply(
                    user_input=goodbye_instruction,
                    allow_interruptions=False  # Don't allow interruption during goodbye
                )
                logger.info("Interview closing message generated")

                # Step 3: Wait for the actual audio playout to complete (TTS + playback)
                try:
                    await asyncio.wait_for(speech_handle.wait_for_playout(), timeout=30)
                    logger.info("Interview closing message playout completed")
                except asyncio.TimeoutError:
                    logger.warning("Interview closing playout timed out; proceeding to end session")

            # Step 4: End the session
            print("🛑 Ending interview session...")
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

    async def _validate_context_hook(self, context: InterviewContext) -> bool:
        """
        Validate that the context is valid for Interview Preparer.

        Args:
            context: The context to validate

        Returns:
            True if context is valid
        """
        # Context validation is done in the context class itself
        # Additional agent-specific validation can be added here
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