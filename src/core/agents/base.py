"""
Base agent abstract class for all AI agents in the system.

Provides common functionality for all agents including:
- Session lifecycle management
- Context and prompt builder integration
- Agent metadata and capabilities
"""

from abc import ABC, abstractmethod
from typing import Optional, Dict, Any, TypeVar, Generic
from dataclasses import dataclass
import logging
import json
from datetime import datetime

from livekit.agents import Agent, AgentSession
from livekit.agents.job import get_job_context
from ..context.base import BaseContext
from ..prompts.base import BasePromptBuilder


logger = logging.getLogger(__name__)

# Type variable for context types
TContext = TypeVar('TContext', bound=BaseContext)


@dataclass
class AgentMetadata:
    """Metadata about an agent type."""
    name: str
    version: str
    description: str
    supported_languages: list[str]
    capabilities: list[str]

    def to_dict(self) -> Dict[str, Any]:
        """Convert metadata to dictionary."""
        return {
            "name": self.name,
            "version": self.version,
            "description": self.description,
            "supported_languages": self.supported_languages,
            "capabilities": self.capabilities
        }


class BaseAgent(ABC, Agent, Generic[TContext]):
    """
    Abstract base class for all agents in the system.

    Provides common agent functionality including session management,
    context handling, and instruction building. All agent types
    (EnglishTutor, InterviewPreparer) extend this class.

    Attributes:
        context: Agent-specific context data from frontend
        prompt_builder: Builds instructions from context
        session: Current LiveKit session
        metadata: Agent metadata (name, version, capabilities)
    """

    def __init__(
        self,
        context: Optional[TContext] = None,
        prompt_builder: Optional[BasePromptBuilder] = None,
        **kwargs
    ):
        """
        Initialize the base agent.

        Args:
            context: Optional context specific to this agent type
            prompt_builder: Optional prompt builder for custom instructions
            **kwargs: Additional arguments passed to parent Agent class
        """
        self._context = context
        self._prompt_builder = prompt_builder or self._create_default_prompt_builder()

        # Build initial instructions
        instructions = self._build_instructions()

        # Initialize parent Agent class
        super().__init__(instructions=instructions, **kwargs)

        logger.info(f"Initialized {self.__class__.__name__} with context: {context}")

    @property
    @abstractmethod
    def metadata(self) -> AgentMetadata:
        """
        Get metadata about this agent type.

        Returns:
            AgentMetadata containing information about the agent
        """
        pass

    @property
    def context(self) -> Optional[TContext]:
        """Get the current context."""
        return self._context

    @context.setter
    def context(self, value: Optional[TContext]) -> None:
        """
        Set the context and rebuild instructions if needed.

        Args:
            value: The new context value
        """
        self._context = value
        self._on_context_updated()

    @property
    def prompt_builder(self) -> BasePromptBuilder:
        """Get the prompt builder."""
        return self._prompt_builder

    @abstractmethod
    def _create_default_prompt_builder(self) -> BasePromptBuilder:
        """
        Create the default prompt builder for this agent type.

        Returns:
            A prompt builder instance specific to this agent
        """
        pass

    def _build_instructions(self) -> str:
        """
        Build the instruction prompt for the agent.

        Returns:
            The complete instruction string
        """
        if self._prompt_builder and self._context:
            return self._prompt_builder.build(self._context)
        elif self._prompt_builder:
            # Build with default/empty context
            return self._prompt_builder.build_default()
        else:
            return self._get_default_instructions()

    @abstractmethod
    def _get_default_instructions(self) -> str:
        """
        Get default instructions when no context is available.

        Returns:
            Default instruction string for this agent type
        """
        pass

    def _on_context_updated(self) -> None:
        """
        Called when the context is updated.

        Subclasses can override this to perform additional actions
        when the context changes.
        """
        # Rebuild instructions with new context
        self.instructions = self._build_instructions()
        logger.debug(f"Context updated for {self.__class__.__name__}")

    @abstractmethod
    async def on_enter(self) -> None:
        """
        Called when the agent becomes the active agent in a session.

        This is a LiveKit lifecycle method that is automatically called
        when the agent enters and becomes active. Use this for initialization
        logic like starting timers, sending initial greetings, etc.

        The session is accessible via self.session property (inherited from
        LiveKit's Agent base class). LiveKit automatically manages the session
        lifecycle, so no manual setup is needed.
        """
        pass

    async def on_session_ended(self, session: AgentSession) -> None:
        """
        Called when a session ends.

        Args:
            session: The agent session that is ending
        """
        logger.info(f"Session ending for {self.__class__.__name__}")
        await self._on_session_ended_hook(session)

    @abstractmethod
    async def _on_session_ended_hook(self, session: AgentSession) -> None:
        """
        Hook for agent-specific session end logic.

        Args:
            session: The agent session that is ending
        """
        pass

    async def validate_context(self) -> bool:
        """
        Validate that the current context is valid for this agent.

        Returns:
            True if context is valid, False otherwise
        """
        if self._context is None:
            return True  # No context is valid for some agents

        return await self._validate_context_hook(self._context)

    @abstractmethod
    async def _validate_context_hook(self, context: TContext) -> bool:
        """
        Hook for agent-specific context validation.

        Args:
            context: The context to validate

        Returns:
            True if context is valid, False otherwise
        """
        pass

    def get_capabilities(self) -> list[str]:
        """
        Get the list of capabilities this agent supports.

        Returns:
            List of capability strings
        """
        return self.metadata.capabilities

    def supports_language(self, language: str) -> bool:
        """
        Check if this agent supports a specific language.

        Args:
            language: Language code (e.g., 'en', 'es', 'fr')

        Returns:
            True if the language is supported
        """
        return language.lower() in [
            lang.lower() for lang in self.metadata.supported_languages
        ]

    async def _publish_session_event(
        self,
        event_type: str,
        status: str,
        reason: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> None:
        """
        Publish a session event to the frontend via LiveKit data channel.

        This method sends custom session events (like session_ending, session_ended)
        to the frontend React application, allowing it to respond to session lifecycle
        changes with UI updates or other actions.

        Args:
            event_type: Type of event (e.g., "session_status", "session_update")
            status: Status value (e.g., "ending", "ended", "warning")
            reason: Optional reason for the event (e.g., "timeout", "user_request")
            metadata: Optional additional metadata to include in the event

        Example event structure:
            {
                "type": "session_status",
                "status": "ending",
                "reason": "timeout",
                "timestamp": "2025-11-11T10:30:00.000Z",
                "metadata": {...}
            }
        """
        job_ctx = get_job_context()
        room = job_ctx.room
        if not room:
            logger.warning(f"Cannot publish event {event_type}: No active session or room")
            return

        event_data = {
            "type": event_type,
            "status": status,
            "timestamp": datetime.utcnow().isoformat() + "Z"
        }

        if reason:
            event_data["reason"] = reason

        if metadata:
            event_data["metadata"] = metadata

        try:
            message_json = json.dumps(event_data)
            await room.local_participant.publish_data(
                message_json.encode('utf-8'),
                reliable=True
            )
            logger.info(f"Published session event: {event_type} - {status}")
        except Exception as e:
            logger.error(f"Failed to publish session event: {e}")

    def __repr__(self) -> str:
        """String representation of the agent."""
        return (
            f"<{self.__class__.__name__} "
            f"name='{self.metadata.name}' "
            f"version='{self.metadata.version}' "
            f"has_context={self._context is not None}>"
        )


