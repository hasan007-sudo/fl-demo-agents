"""
Agent factory for creating agent instances.

Handles:
- Agent selection from registry
- Agent instantiation with context
"""

from typing import Type, Optional, Dict, Any, Callable
import logging
from pathlib import Path

from .base import BaseAgent
from .registry import registry
from ..context.base import BaseContext

logger = logging.getLogger(__name__)


class AgentFactory:
    """
    Factory for creating properly configured agent instances.

    Handles:
    - Agent selection from registry by type
    - Agent instantiation with context
    """

    def __init__(
        self,
        registry_instance: Optional[Any] = None
    ):
        """
        Initialize the factory.

        Args:
            registry_instance: Optional registry instance (defaults to global)
        """
        self.registry = registry_instance or registry
        self._creation_hooks: list[Callable] = []

        logger.info("AgentFactory initialized")

    def create(
        self,
        agent_type: str,
        context: Optional[BaseContext] = None,
        **kwargs
    ) -> Optional[BaseAgent]:
        """
        Create an agent instance.

        Args:
            agent_type: Type of agent to create
            context: Optional context for the agent
            **kwargs: Additional arguments for agent constructor

        Returns:
            Configured agent instance or None if creation fails
        """
        logger.info(f"Creating agent of type: {agent_type}")

        # Get agent registration
        registration = self.registry.get(agent_type)
        if not registration:
            logger.error(f"Agent type '{agent_type}' not found in registry")
            return None

        try:
            # Add context if provided
            if context:
                kwargs['context'] = context

            # Create agent instance
            if registration.factory_func:
                agent = registration.factory_func(**kwargs)
            else:
                agent = registration.agent_class(**kwargs)

            # Run creation hooks. For now we don't have any
            for hook in self._creation_hooks:
                hook(agent)

            logger.info(
                f"Successfully created agent: {agent_type} "
                f"(class={agent.__class__.__name__})"
            )
            return agent

        except Exception as e:
            logger.error(f"Failed to create agent '{agent_type}': {e}")
            return None

    def create_from_room_metadata(
        self,
        metadata: str,
        fallback_type: Optional[str] = None
    ) -> Optional[BaseAgent]:
        """
        Create an agent from LiveKit room metadata.

        Args:
            metadata: JSON string from room metadata
            fallback_type: Agent type to use if not specified in metadata

        Returns:
            Agent instance or None
        """
        import json

        try:
            # Parse metadata
            data = json.loads(metadata)

            # Extract agent type
            agent_type = data.get('agent_type') or data.get('agentType')
            if not agent_type and fallback_type:
                agent_type = fallback_type

            if not agent_type:
                logger.error("No agent type specified in metadata")
                return None

            # Extract context based on agent type
            context = self._parse_context_for_agent(agent_type, data)

            # Create the agent
            return self.create(agent_type, context=context)

        except json.JSONDecodeError as e:
            logger.error(f"Invalid JSON in room metadata: {e}")
            return None
        except Exception as e:
            logger.error(f"Failed to create agent from metadata: {e}")
            return None

    def _parse_context_for_agent(
        self,
        agent_type: str,
        data: Dict[str, Any]
    ) -> Optional[BaseContext]:
        """
        Parse context specific to an agent type.

        Args:
            agent_type: Type of agent
            data: Raw context data

        Returns:
            Parsed context or None
        """
        # Get the agent class
        registration = self.registry.get(agent_type)
        if not registration:
            return None

        # Get context parser for this agent type
        # This is where agent-specific context parsing happens
        # Each agent can have its own context structure

        # For now, we'll return None and let each agent handle its own parsing
        # This maintains backward compatibility with existing agents
        return None

    def create_with_builder(
        self,
        agent_type: str
    ) -> 'AgentBuilder':
        """
        Create an agent using the builder pattern.

        Args:
            agent_type: Type of agent to build

        Returns:
            Agent builder instance
        """
        return AgentBuilder(self, agent_type)

    def add_creation_hook(
        self,
        hook: Callable[[BaseAgent], None]
    ) -> None:
        """
        Add a hook to be called after agent creation.

        Args:
            hook: Function to call with created agent
        """
        self._creation_hooks.append(hook)

    def create_default(
        self,
        context: Optional[BaseContext] = None,
        **kwargs
    ) -> Optional[BaseAgent]:
        """
        Create the default agent.

        Args:
            context: Optional context
            **kwargs: Additional arguments

        Returns:
            Default agent instance or None
        """
        agents = self.registry.list_agents()
        if not agents:
            logger.error("No agents registered")
            return None

        # Try to find default agent
        for agent_name in agents:
            registration = self.registry.get(agent_name)
            if registration and registration.is_default:
                return self.create(agent_name, context=context, **kwargs)

        # Fall back to first registered agent
        return self.create(agents[0], context=context, **kwargs)


class AgentBuilder:
    """
    Builder pattern for constructing agents with complex configuration.
    """

    def __init__(self, factory: AgentFactory, agent_type: str):
        """
        Initialize the builder.

        Args:
            factory: The factory to use for creation
            agent_type: Type of agent to build
        """
        self.factory = factory
        self.agent_type = agent_type
        self.context: Optional[BaseContext] = None
        self.config: Dict[str, Any] = {}
        self.kwargs: Dict[str, Any] = {}

    def with_context(self, context: BaseContext) -> 'AgentBuilder':
        """
        Set the context for the agent.

        Args:
            context: Agent context

        Returns:
            Self for chaining
        """
        self.context = context
        return self

    def with_config(self, config: Dict[str, Any]) -> 'AgentBuilder':
        """
        Set configuration overrides.

        Args:
            config: Configuration dictionary

        Returns:
            Self for chaining
        """
        self.config.update(config)
        return self

    def with_parameter(self, key: str, value: Any) -> 'AgentBuilder':
        """
        Set a single parameter.

        Args:
            key: Parameter name
            value: Parameter value

        Returns:
            Self for chaining
        """
        self.kwargs[key] = value
        return self

    def build(self) -> Optional[BaseAgent]:
        """
        Build the agent with accumulated configuration.

        Returns:
            Configured agent instance
        """
        return self.factory.create(
            self.agent_type,
            context=self.context,
            config_override=self.config,
            **self.kwargs
        )


class MultiAgentFactory:
    """
    Factory that can create different types of agents based on strategy.
    """

    def __init__(self):
        """Initialize the multi-agent factory."""
        self.factories: Dict[str, AgentFactory] = {}
        self.default_factory = AgentFactory()

    def register_factory(
        self,
        name: str,
        factory: AgentFactory
    ) -> None:
        """
        Register a specialized factory.

        Args:
            name: Name for this factory
            factory: The factory instance
        """
        self.factories[name] = factory
        logger.info(f"Registered factory: {name}")

    def create_agent(
        self,
        agent_type: str,
        factory_name: Optional[str] = None,
        **kwargs
    ) -> Optional[BaseAgent]:
        """
        Create an agent using appropriate factory.

        Args:
            agent_type: Type of agent
            factory_name: Specific factory to use
            **kwargs: Arguments for agent creation

        Returns:
            Agent instance
        """
        # Select factory
        if factory_name and factory_name in self.factories:
            factory = self.factories[factory_name]
        else:
            factory = self.default_factory

        # Create agent
        return factory.create(agent_type, **kwargs)


# Global factory instance
default_factory = AgentFactory()