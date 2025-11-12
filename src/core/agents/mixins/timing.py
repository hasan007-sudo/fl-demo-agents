"""Timing mixin for agents with session time limits and checkpoints."""

import logging
from typing import Optional
from abc import ABC, abstractmethod

from ...session.timing import SessionTimer
from ...session.checkpoints import (
    SessionTimingConfig,
    Checkpoint,
    create_checkpoint_metadata
)

logger = logging.getLogger(__name__)


class TimingMixin(ABC):
    """Mixin providing session timing and checkpoint functionality."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._timer: Optional[SessionTimer] = None

    @abstractmethod
    def get_timing_config(self) -> SessionTimingConfig:
        """Get the timing configuration for this agent."""
        pass

    def _init_timing(self) -> None:
        """Initialize and start the session timer."""
        config = self.get_timing_config()
        agent_name = self.metadata.name if hasattr(self, 'metadata') else 'Agent'

        self._timer = SessionTimer(config, agent_name)
        self._timer.start(
            on_checkpoint=self._handle_checkpoint,
            on_final_checkpoint=self._handle_final_checkpoint,
            is_session_active=self._is_session_active_for_timing
        )

        logger.info(f"{agent_name}: Timing initialized with {len(config.checkpoints)} checkpoints")

    async def _stop_timing(self) -> None:
        """Stop the session timer."""
        if self._timer:
            await self._timer.stop()

    def _is_session_active_for_timing(self) -> bool:
        """Check if session is still active for timing purposes."""
        if not hasattr(self, 'session') or not self.session:
            return False

        if hasattr(self, 'is_session_ending'):
            return not self.is_session_ending() and not self.is_session_ended()

        return True

    async def _handle_checkpoint(self, checkpoint: Checkpoint, idx: int) -> None:
        """Handle a regular (non-final) checkpoint."""
        config = self.get_timing_config()

        if checkpoint.frontend_event:
            metadata = create_checkpoint_metadata(
                checkpoint, idx, config.max_duration
            )
            await self._publish_session_event(
                event_type="time_checkpoint",
                status="in_progress",
                reason="checkpoint",
                metadata=metadata
            )
            logger.info(f"Sent checkpoint {idx + 1} event to frontend ({checkpoint.time}s)")

        if checkpoint.ai_instruction:
            await self._on_checkpoint_reached(checkpoint, idx)

    async def _handle_final_checkpoint(self) -> None:
        """Handle the final checkpoint (triggers shutdown)."""
        config = self.get_timing_config()
        final_cp = config.get_final_checkpoint()

        if final_cp and final_cp.frontend_event:
            idx = config.checkpoints.index(final_cp)
            metadata = create_checkpoint_metadata(
                final_cp, idx, config.max_duration
            )
            await self._publish_session_event(
                event_type="time_checkpoint",
                status="ending",
                reason="checkpoint",
                metadata=metadata
            )

        await self._on_session_timeout()

    @abstractmethod
    async def _on_checkpoint_reached(self, checkpoint: Checkpoint, idx: int) -> None:
        """Called when a regular checkpoint is reached."""
        pass

    @abstractmethod
    async def _on_session_timeout(self) -> None:
        """Called when the session reaches its time limit."""
        pass
