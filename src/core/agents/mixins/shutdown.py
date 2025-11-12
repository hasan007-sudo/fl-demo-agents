"""Graceful shutdown mixin for agents."""

import logging
from abc import ABC, abstractmethod

from ...session.lifecycle import SessionLifecycleManager

logger = logging.getLogger(__name__)


class ShutdownMixin(ABC):
    """Mixin providing graceful session shutdown functionality."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        agent_name = self.metadata.name if hasattr(self, 'metadata') else 'Agent'
        self._lifecycle = SessionLifecycleManager(agent_name)

    def is_session_ending(self) -> bool:
        """Check if session is in shutdown process."""
        return self._lifecycle.is_ending

    def is_session_ended(self) -> bool:
        """Check if session has fully ended."""
        return self._lifecycle.is_ended

    @abstractmethod
    def get_goodbye_instruction(self) -> str:
        """Get the instruction for generating goodbye message."""
        pass

    @abstractmethod
    def get_session_duration(self) -> int:
        """Get the session duration for metadata."""
        pass

    async def _graceful_shutdown(self) -> None:
        """Perform graceful shutdown of the session."""
        if not self._lifecycle.mark_ending():
            logger.debug("Shutdown already in progress, skipping")
            return

        logger.info("Starting graceful shutdown sequence")

        try:
            # Notify frontend
            await self._publish_session_event(
                event_type="session_status",
                status="ending",
                reason="timeout",
                metadata={"duration_seconds": self.get_session_duration()}
            )
            logger.info("Sent session_ending event to frontend")

            # Generate and play goodbye message
            if hasattr(self, 'session') and self.session:
                goodbye_instruction = self.get_goodbye_instruction()

                logger.info("Generating goodbye message")
                speech_handle = self.session.generate_reply(
                    user_input=goodbye_instruction,
                    allow_interruptions=False
                )

                await self._lifecycle.wait_for_speech_playout(
                    speech_handle,
                    timeout=30
                )

            self._lifecycle.mark_ended()
            logger.info("Session marked as ended")

            # Delete room
            await self._lifecycle.delete_room()

        except Exception as e:
            logger.error(f"Error during graceful shutdown: {e}", exc_info=True)
            self._lifecycle.mark_ended()
