"""Session timing utilities."""

import time
import asyncio
import logging
from typing import Optional, Callable, Awaitable

from .checkpoints import SessionTimingConfig, Checkpoint

logger = logging.getLogger(__name__)


class SessionTimer:
    """Manages session timing and checkpoint notifications."""

    def __init__(
        self,
        config: SessionTimingConfig,
        agent_name: str = "Agent"
    ):
        self.config = config
        self.agent_name = agent_name
        self._start_time: Optional[float] = None
        self._timer_task: Optional[asyncio.Task] = None

    def start(
        self,
        on_checkpoint: Callable[[Checkpoint, int], Awaitable[None]],
        on_final_checkpoint: Callable[[], Awaitable[None]],
        is_session_active: Callable[[], bool]
    ) -> None:
        """Start the timer and begin monitoring checkpoints."""
        self._start_time = time.time()
        self._timer_task = asyncio.create_task(
            self._checkpoint_monitor(
                on_checkpoint,
                on_final_checkpoint,
                is_session_active
            )
        )
        logger.info(f"{self.agent_name}: Session timer started")

    async def stop(self) -> None:
        """Stop the timer and cancel checkpoint monitoring."""
        if self._timer_task:
            self._timer_task.cancel()
            try:
                await self._timer_task
            except asyncio.CancelledError:
                logger.info(f"{self.agent_name}: Timer task cancelled")

    def elapsed_time(self) -> float:
        """Get elapsed time since session start in seconds."""
        if self._start_time is None:
            return 0.0
        return time.time() - self._start_time

    async def _checkpoint_monitor(
        self,
        on_checkpoint: Callable[[Checkpoint, int], Awaitable[None]],
        on_final_checkpoint: Callable[[], Awaitable[None]],
        is_session_active: Callable[[], bool]
    ) -> None:
        """Background task that monitors and processes checkpoints."""
        logger.info(f"{self.agent_name}: Checkpoint monitor started")

        try:
            for idx, checkpoint in enumerate(self.config.checkpoints):
                elapsed = self.elapsed_time()
                wait_time = checkpoint.time - elapsed

                if wait_time > 0:
                    await asyncio.sleep(wait_time)

                if not is_session_active():
                    logger.info(
                        f"{self.agent_name}: Session ended before checkpoint {idx + 1}"
                    )
                    break

                if checkpoint.is_final:
                    logger.warning(
                        f"{self.agent_name}: Final checkpoint reached at {checkpoint.time}s"
                    )
                    await on_final_checkpoint()
                    break
                else:
                    logger.info(
                        f"{self.agent_name}: Processing checkpoint {idx + 1} at {checkpoint.time}s"
                    )
                    await on_checkpoint(checkpoint, idx)

        except asyncio.CancelledError:
            logger.info(f"{self.agent_name}: Checkpoint monitor cancelled")
            raise
        except Exception as e:
            logger.error(
                f"{self.agent_name}: Error in checkpoint monitor: {e}",
                exc_info=True
            )
