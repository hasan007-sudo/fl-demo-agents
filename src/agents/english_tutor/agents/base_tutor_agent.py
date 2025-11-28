"""Base class for English Tutor multi-agent system."""

from livekit.agents.voice.agent import Agent
import logging
from abc import abstractmethod
from typing import Optional
from livekit.agents import AgentSession
from livekit.agents.llm import ChatContext
from core.agents.base import BaseAgent
from core.agents.mixins.timing import TimingMixin
from core.session.checkpoints import SessionTimingConfig, Checkpoint
from core.prompts.base import BasePromptBuilder
from ..context import EnglishTutorContext

logger = logging.getLogger(__name__)

TRUNCATE_CHAT_CTX = 30

class BaseTutorAgent(TimingMixin, BaseAgent[EnglishTutorContext]):
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
        # Store instructions before calling super()
        self._external_instructions = instructions
        
        # Initialize BaseAgent (which will call _build_instructions)
        super().__init__(
            context=context,
            prompt_builder=None,  # We use external instructions
            chat_ctx=chat_ctx,
            **kwargs
        )
        logger.info(f"{self.__class__.__name__} initialized")

    def _create_default_prompt_builder(self) -> BasePromptBuilder:
        """Not used - we receive instructions externally."""
        return None  # type: ignore

    def _get_default_instructions(self) -> str:
        """Return the externally provided instructions."""
        return self._external_instructions

    async def _on_session_ended_hook(self, session: AgentSession) -> None:
        """Hook for session end logic."""
        logger.info(f"{self.__class__.__name__}: Session ended")
        # Subclasses can override if needed

    async def _validate_context_hook(self, context: EnglishTutorContext) -> bool:
        """Validate the English tutor context."""
        # Basic validation - context should exist
        return context is not None

    @abstractmethod
    def get_timing_config(self) -> SessionTimingConfig:
        """Get the timing configuration for this agent."""
        pass

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
            userdata: EnglishTutorContext = self.session.userdata

            # Update room attributes for tracking
            if userdata.job_ctx and userdata.job_ctx.room and userdata.job_ctx.room.isconnected():
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
                    keep_last_n_messages=TRUNCATE_CHAT_CTX
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
                        f"You are now a {agent_name}. "
                        f"Session state: {userdata.summarize()}"
                    )
                )

                await self.update_chat_ctx(chat_ctx)

            # Call agent-specific entry hook
            await self._on_enter_hook()

            # Initialize timing after agent-specific setup
            self._init_timing()
            logger.info(f"{agent_name}: Timing initialized")

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
            if hasattr(item, 'role') and item.role == "system":
                filtered_items.append(item)
                continue

            # Keep function/tool calls if specified
            if keep_function_call:
                # Check for tool_calls attribute (newer API)
                if hasattr(item, "tool_calls") and item.tool_calls:
                    filtered_items.append(item)
                    continue
                # Check for function_calls attribute (older API)
                if hasattr(item, "function_calls") and item.function_calls:
                    filtered_items.append(item)
                    continue

            # Keep regular messages (must have role attribute)
            if hasattr(item, 'role'):
                filtered_items.append(item)

        # Keep only last N messages (excluding system)
        system_items = [item for item in filtered_items if hasattr(item, 'role') and item.role == "system"]
        other_items = [item for item in filtered_items if not hasattr(item, 'role') or item.role != "system"]

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
        userdata: EnglishTutorContext = self.session.userdata
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

    async def _on_checkpoint_reached(self, checkpoint: Checkpoint, idx: int) -> None:
        """
        Handle regular checkpoint by queuing AI instruction.
        
        This is called for non-final checkpoints to give the agent
        guidance about timing (e.g., "wrap up soon").
        """
        if checkpoint.ai_instruction:
            try:
                agent_name = self.__class__.__name__
                logger.info(f"{agent_name}: Checkpoint {idx + 1} reached - queuing AI instruction")
                await self.session.generate_reply(instructions=checkpoint.ai_instruction)
                # await self._queue_checkpoint_instruction(checkpoint.ai_instruction)
            except Exception as e:
                logger.warning(f"Failed to queue checkpoint {idx + 1} instruction: {e}")

    async def _queue_checkpoint_instruction(self, instruction: str) -> None:
        """
        Insert the checkpoint instruction into the chat context as a system message.
        
        This ensures the instruction is available for the agent's reasoning
        without triggering an immediate (and potentially interruptive) reply.
        """
        system_msg = {
            "role": "system",
            "content": instruction,
        }
        
        # Update the session's chat context (adds the message and persists it)
        # Note: chat_ctx.add_message returns a new ChatContext instance
        chat_ctx = self.chat_ctx.copy()
        chat_ctx.add_message(**system_msg)
        self.update_chat_ctx(chat_ctx)
        logger.info(f"Context updated after checkpoint instruction: {instruction}")

    async def _on_session_timeout(self, checkpoint: Checkpoint, idx: int) -> None:
        """
        Handle final checkpoint that triggers agent handoff.
        
        For ConversationPartner: triggers transfer_to_feedback()
        """
        agent_name = self.__class__.__name__
        logger.warning(f"{agent_name}: Final checkpoint reached - triggering handoff. Checkpoint => {checkpoint.time}")
        
        try:
            await self.session.generate_reply(instructions=checkpoint.ai_instruction)
            logger.info(f"{agent_name}: Handoff instruction sent")
            
        except Exception as e:
            logger.error(f"{agent_name}: Failed to trigger handoff: {e}", exc_info=True)
