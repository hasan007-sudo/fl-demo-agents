"""Session lifecycle management utilities."""

import logging
import os
import asyncio
from typing import Optional

from livekit import api
from livekit.agents.job import get_job_context

logger = logging.getLogger(__name__)


class SessionLifecycleManager:
    """Manages session lifecycle operations like shutdown and room deletion."""

    def __init__(self, agent_name: str = "Agent"):
        self.agent_name = agent_name
        self._session_ending = False
        self._session_ended = False

    @property
    def is_ending(self) -> bool:
        """Check if session is in shutdown process."""
        return self._session_ending

    @property
    def is_ended(self) -> bool:
        """Check if session has ended."""
        return self._session_ended

    def mark_ending(self) -> bool:
        """Mark session as ending. Returns True if this is the first call."""
        if self._session_ending or self._session_ended:
            return False
        self._session_ending = True
        return True

    def mark_ended(self) -> None:
        """Mark session as fully ended."""
        self._session_ended = True

    async def wait_for_speech_playout(
        self,
        speech_handle,
        timeout: int = 30
    ) -> bool:
        """Wait for speech playout to complete."""
        try:
            await asyncio.wait_for(
                speech_handle.wait_for_playout(),
                timeout=timeout
            )
            logger.info(f"{self.agent_name}: Speech playout completed")
            return True
        except asyncio.TimeoutError:
            logger.warning(
                f"{self.agent_name}: Speech playout timed out after {timeout}s"
            )
            return False

    async def delete_room(self) -> bool:
        """Delete the current room, disconnecting all participants."""
        try:
            job_ctx = get_job_context()
            api_client = api.LiveKitAPI(
                os.getenv("LIVEKIT_URL"),
                os.getenv("LIVEKIT_API_KEY"),
                os.getenv("LIVEKIT_API_SECRET"),
            )
            await api_client.room.delete_room(
                api.DeleteRoomRequest(room=job_ctx.room.name)
            )
            logger.info(f"{self.agent_name}: Room deleted successfully")
            return True
        except Exception as e:
            logger.debug(f"{self.agent_name}: Could not delete room: {e}")
            return False

    def reset(self) -> None:
        """Reset lifecycle state."""
        self._session_ending = False
        self._session_ended = False
