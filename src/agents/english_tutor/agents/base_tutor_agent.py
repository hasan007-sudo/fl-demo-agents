"""Base class for English Tutor multi-agent system."""

import logging
from abc import abstractmethod
from typing import Optional
from livekit.agents import Agent
from livekit.agents.llm import ChatContext

from ..context import EnglishTutorContext
from ..shared.session_data import EnglishTutorSessionData

logger = logging.getLogger(__name__)


class BaseTutorAgent(Agent):
    """
    Base class for English Tutor agents with shared handoff functionality.

    This base class provides common logic for multi-agent orchestration,
    including chat context preservation during agent handoffs and
    session state management.
    """

    def __init__(
        self,
        instructions: str,
        context: Optional[EnglishTutorContext] = None,
        chat_ctx: Optional[ChatContext] = None,
        **kwargs
    ):
        """
        Initialize the base tutor agent.

        Args:
            instructions: System prompt for this agent
            context: English tutor context from frontend
            chat_ctx: Existing chat context to preserve history
            **kwargs: Additional arguments for Agent (llm, stt, tts, vad)
        """
        super().__init__(
            instructions=instructions,
            chat_ctx=chat_ctx,
            **kwargs
        )
        self.context = context
        logger.info(f"{self.__class__.__name__} initialized")

    async def on_enter(self) -> None:
        """
        Called when agent becomes active in the session.

        Handles chat context preservation from previous agent and
        calls agent-specific entry logic.
        """
        agent_name = self.__class__.__name__
        logger.info(f"{agent_name}: Entering session")

        try:
            # Get session userdata
            userdata: EnglishTutorSessionData = self.session.userdata

            # Update room attributes for tracking
            if userdata.job_ctx and userdata.job_ctx.room:
                await userdata.job_ctx.room.local_participant.set_attributes({
                    "agent": agent_name
                })
                logger.info(f"Set room attribute: agent={agent_name}")

            # Preserve chat context from previous agent
            if userdata.previous_agent:
                logger.info(f"Preserving chat context from previous agent")
                chat_ctx = self.chat_ctx.copy()

                # Truncate and merge previous chat history
                previous_items = self._truncate_chat_ctx(
                    userdata.previous_agent.chat_ctx.items,
                    keep_last_n_messages=10
                )

                # Avoid duplicates
                existing_ids = {item.id for item in chat_ctx.items}
                items_to_add = [
                    item for item in previous_items
                    if item.id not in existing_ids
                ]

                chat_ctx.items.extend(items_to_add)
                logger.info(
                    f"Merged {len(items_to_add)} messages from previous agent "
                    f"(total: {len(chat_ctx.items)})"
                )

                # Add system context about the session state
                chat_ctx.add_message(
                    role="system",
                    content=(
                        f"You are now the {agent_name}. "
                        f"Session state: {userdata.summarize()}"
                    )
                )

                await self.update_chat_ctx(chat_ctx)

            # Call agent-specific entry hook
            await self._on_enter_hook()

        except Exception as e:
            logger.error(f"Error in {agent_name}.on_enter: {e}", exc_info=True)
            raise

    @abstractmethod
    async def _on_enter_hook(self) -> None:
        """
        Agent-specific entry logic.

        Implement this in subclasses to define what happens when
        the agent becomes active (e.g., send greeting, start feedback).
        """
        pass

    def _truncate_chat_ctx(
        self,
        items: list,
        keep_last_n_messages: int = 10,
        keep_function_call: bool = True
    ) -> list:
        """
        Truncate chat context to keep only relevant recent history.

        This prevents the context from growing too large during handoffs
        while preserving important conversation history.

        Args:
            items: List of chat items to truncate
            keep_last_n_messages: Number of recent messages to keep
            keep_function_call: Whether to preserve function call messages

        Returns:
            Truncated list of chat items
        """
        if not items:
            return []

        # Filter items
        filtered_items = []
        for item in items:
            # Always keep system messages
            if item.role == "system":
                filtered_items.append(item)
                continue

            # Keep function calls if specified
            if keep_function_call and hasattr(item, "tool_calls") and item.tool_calls:
                filtered_items.append(item)
                continue

            # Keep regular messages
            filtered_items.append(item)

        # Keep only last N messages (excluding system)
        system_items = [item for item in filtered_items if item.role == "system"]
        other_items = [item for item in filtered_items if item.role != "system"]

        # Truncate non-system items
        truncated_other = other_items[-keep_last_n_messages:] if other_items else []

        # Combine: system messages + last N other messages
        result = system_items + truncated_other

        logger.debug(
            f"Truncated context: {len(items)} -> {len(result)} items "
            f"({len(system_items)} system, {len(truncated_other)} conversation)"
        )

        return result

    async def _transfer_to_agent(self, agent_name: str) -> Agent:
        """
        Transfer control to another agent.

        Updates session userdata to track the handoff and returns
        the target agent instance.

        Args:
            agent_name: Name of target agent ("conversation" or "feedback")

        Returns:
            The target agent instance

        Raises:
            ValueError: If agent_name is not recognized
        """
        userdata: EnglishTutorSessionData = self.session.userdata
        userdata.previous_agent = self

        logger.info(f"Transferring from {self.__class__.__name__} to {agent_name}")

        if agent_name == "feedback":
            return userdata.feedback_agent
        elif agent_name == "conversation":
            return userdata.conversation_agent
        else:
            raise ValueError(
                f"Unknown agent: {agent_name}. "
                f"Expected 'conversation' or 'feedback'"
            )
