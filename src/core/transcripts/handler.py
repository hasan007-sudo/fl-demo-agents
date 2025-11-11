"""
Transcript handler for broadcasting conversation transcripts via LiveKit data channel.

This module provides functionality to capture and broadcast transcripts from
OpenAI Realtime model conversations to connected clients.
"""

import json
import logging
import uuid
from datetime import datetime
from typing import Optional, Dict, Any
from enum import Enum

from livekit.agents import AgentSession
from livekit.agents.llm import ChatMessage


logger = logging.getLogger(__name__)


class TranscriptRole(str, Enum):
    """Role identifiers for transcript messages."""
    USER = "user"
    ASSISTANT = "assistant"


class TranscriptHandler:
    """
    Handles transcript broadcasting for agent conversations.

    Captures transcripts from OpenAI Realtime model and broadcasts them
    to connected clients via LiveKit data channel in a standardized format.
    """

    def __init__(self, session: Optional[AgentSession] = None):
        """
        Initialize the transcript handler.

        Args:
            session: Optional AgentSession for broadcasting transcripts
        """
        self.session = session
        self._transcript_buffer: Dict[str, Dict[str, Any]] = {}
        self._enabled = True

    def set_session(self, session: AgentSession) -> None:
        """
        Set or update the agent session.

        Args:
            session: The AgentSession to use for broadcasting
        """
        self.session = session
        logger.debug("Session set for transcript handler")

    def enable(self) -> None:
        """Enable transcript broadcasting."""
        self._enabled = True
        logger.info("Transcript broadcasting enabled")

    def disable(self) -> None:
        """Disable transcript broadcasting."""
        self._enabled = False
        logger.info("Transcript broadcasting disabled")

    async def broadcast_transcript(
        self,
        role: TranscriptRole,
        text: str,
        is_final: bool = False,
        turn_id: Optional[str] = None,
        timestamp: Optional[datetime] = None
    ) -> None:
        """
        Broadcast a transcript message via the data channel.

        Args:
            role: The speaker role (user or assistant)
            text: The transcript text
            is_final: Whether this is the final version of the transcript
            turn_id: Unique identifier for this conversation turn
            timestamp: Optional timestamp (defaults to current time)
        """
        if not self._enabled:
            return

        if not self.session:
            logger.warning("No session available for transcript broadcasting")
            return

        # Generate turn_id if not provided
        if turn_id is None:
            turn_id = str(uuid.uuid4())

        # Use current timestamp if not provided
        if timestamp is None:
            timestamp = datetime.utcnow()

        # Create transcript message
        transcript_message = {
            "type": "transcript",
            "role": role.value,
            "text": text,
            "timestamp": timestamp.isoformat(),
            "isFinal": is_final,
            "turn_id": turn_id
        }

        # Update buffer for streaming transcripts
        if not is_final:
            self._transcript_buffer[turn_id] = transcript_message
        else:
            # Clear from buffer when finalized
            self._transcript_buffer.pop(turn_id, None)

        try:
            # Get the room from the session
            room = self.session.room
            if room and room.local_participant:
                # Serialize and send via data channel
                message_json = json.dumps(transcript_message)
                await room.local_participant.publish_data(
                    message_json.encode('utf-8'),
                    reliable=True
                )
                logger.debug(f"Broadcast transcript: role={role.value}, turn_id={turn_id}, is_final={is_final}")
            else:
                logger.warning("Room or local participant not available for data publishing")

        except Exception as e:
            logger.error(f"Error broadcasting transcript: {e}")

    async def handle_user_speech(
        self,
        text: str,
        is_final: bool = False,
        turn_id: Optional[str] = None
    ) -> None:
        """
        Handle user speech transcription.

        Args:
            text: The transcribed user speech
            is_final: Whether this is the final transcription
            turn_id: Optional turn identifier
        """
        await self.broadcast_transcript(
            role=TranscriptRole.USER,
            text=text,
            is_final=is_final,
            turn_id=turn_id
        )

    async def handle_assistant_speech(
        self,
        text: str,
        is_final: bool = False,
        turn_id: Optional[str] = None
    ) -> None:
        """
        Handle assistant speech transcription.

        Args:
            text: The assistant's response text
            is_final: Whether this is the final version
            turn_id: Optional turn identifier
        """
        await self.broadcast_transcript(
            role=TranscriptRole.ASSISTANT,
            text=text,
            is_final=is_final,
            turn_id=turn_id
        )

    async def handle_llm_message(self, message: ChatMessage) -> None:
        """
        Handle an LLM message and extract transcript if applicable.

        Args:
            message: The ChatMessage to process
        """
        if hasattr(message, 'role') and hasattr(message, 'content'):
            # Determine role
            role = TranscriptRole.ASSISTANT if message.role in ['assistant', 'system'] else TranscriptRole.USER

            # Extract text content
            text = ""
            if isinstance(message.content, str):
                text = message.content
            elif isinstance(message.content, list):
                # Handle multi-part content
                text_parts = []
                for part in message.content:
                    if isinstance(part, str):
                        text_parts.append(part)
                    elif hasattr(part, 'text'):
                        text_parts.append(part.text)
                text = " ".join(text_parts)

            if text:
                await self.broadcast_transcript(
                    role=role,
                    text=text,
                    is_final=True
                )

    def clear_buffer(self) -> None:
        """Clear the transcript buffer."""
        self._transcript_buffer.clear()
        logger.debug("Transcript buffer cleared")

    def get_buffer_size(self) -> int:
        """Get the current size of the transcript buffer."""
        return len(self._transcript_buffer)