"""
Agent registry for managing and discovering available agents.

Singleton registry that:
- Maintains a registry of all agent types
- Maps agent names to their implementation classes
- Supports agent discovery and instantiation
"""

from typing import Dict, Type, Optional, List, Callable, Any
from dataclasses import dataclass
import logging
import importlib
import inspect
from pathlib import Path

from .base import BaseAgent, AgentMetadata

logger = logging.getLogger(__name__)


@dataclass
class AgentRegistration:
    """Information about a registered agent."""
    agent_class: Type[BaseAgent]
    metadata: AgentMetadata
    factory_func: Optional[Callable[..., BaseAgent]] = None
    is_default: bool = False

    def create_instance(self, **kwargs) -> BaseAgent:
        """
        Create an instance of this agent.

        Args:
            **kwargs: Arguments to pass to the agent constructor

        Returns:
            Agent instance
        """
        if self.factory_func:
            return self.factory_func(**kwargs)
        return self.agent_class(**kwargs)


class AgentRegistry:
    """
    Centralized registry for all available agents.

    This singleton class maintains a registry of all agent types
    and provides methods for registration, discovery, and creation.
    """

    _instance: Optional['AgentRegistry'] = None
    _agents: Dict[str, AgentRegistration] = {}
    _default_agent: Optional[str] = None
    _initialized: bool = False

    def __new__(cls) -> 'AgentRegistry':
        """Ensure singleton instance."""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        """Initialize the registry once."""
        if not self._initialized:
            self._agents = {}
            self._default_agent = None
            self._initialized = True
            logger.info("AgentRegistry initialized")

    def register(
        self,
        name: str,
        agent_class: Type[BaseAgent],
        factory_func: Optional[Callable[..., BaseAgent]] = None,
        is_default: bool = False
    ) -> None:
        """
        Register an agent with the registry.

        Args:
            name: Unique name for the agent
            agent_class: The agent class
            factory_func: Optional factory function for creating instances
            is_default: Whether this should be the default agent

        Raises:
            ValueError: If agent with name already exists
        """
        if name in self._agents:
            raise ValueError(f"Agent '{name}' is already registered")

        # Get metadata from agent class
        try:
            # Create temporary instance to get metadata
            temp_instance = agent_class()
            metadata = temp_instance.metadata
        except Exception as e:
            logger.warning(f"Could not get metadata for {name}: {e}")
            # Create default metadata
            metadata = AgentMetadata(
                name=name,
                version="1.0.0",
                description=f"{name} agent",
                supported_languages=["en"],
                capabilities=[]
            )

        # Create registration
        registration = AgentRegistration(
            agent_class=agent_class,
            metadata=metadata,
            factory_func=factory_func,
            is_default=is_default
        )

        self._agents[name] = registration

        # Set as default if specified
        if is_default:
            self._default_agent = name

        logger.info(
            f"Registered agent '{name}' "
            f"(default={is_default}, has_factory={factory_func is not None})"
        )

    def register_decorator(
        self,
        name: str,
        **kwargs
    ) -> Callable[[Type[BaseAgent]], Type[BaseAgent]]:
        """
        Decorator for registering agents.

        Usage:
            @registry.register_decorator("my_agent")
            class MyAgent(BaseAgent):
                ...

        Args:
            name: Name to register the agent under
            **kwargs: Additional registration arguments

        Returns:
            Decorator function
        """
        def decorator(agent_class: Type[BaseAgent]) -> Type[BaseAgent]:
            self.register(name, agent_class, **kwargs)
            return agent_class
        return decorator

    def unregister(self, name: str) -> None:
        """
        Remove an agent from the registry.

        Args:
            name: Name of the agent to remove

        Raises:
            KeyError: If agent not found
        """
        if name not in self._agents:
            raise KeyError(f"Agent '{name}' not found in registry")

        del self._agents[name]

        # Clear default if it was this agent
        if self._default_agent == name:
            self._default_agent = None

        logger.info(f"Unregistered agent '{name}'")

    def get(self, name: str) -> Optional[AgentRegistration]:
        """
        Get an agent registration by name.

        Args:
            name: Name of the agent

        Returns:
            AgentRegistration or None if not found
        """
        return self._agents.get(name)

    def get_agent_class(self, name: str) -> Optional[Type[BaseAgent]]:
        """
        Get an agent class by name.

        Args:
            name: Name of the agent

        Returns:
            Agent class or None if not found
        """
        registration = self.get(name)
        return registration.agent_class if registration else None

    def create_agent(
        self,
        name: str,
        **kwargs
    ) -> Optional[BaseAgent]:
        """
        Create an agent instance by name.

        Args:
            name: Name of the agent
            **kwargs: Arguments to pass to agent constructor

        Returns:
            Agent instance or None if not found
        """
        registration = self.get(name)
        if not registration:
            logger.error(f"Agent '{name}' not found in registry")
            return None

        try:
            return registration.create_instance(**kwargs)
        except Exception as e:
            logger.error(f"Failed to create agent '{name}': {e}")
            return None

    def get_default_agent(self) -> Optional[BaseAgent]:
        """
        Create an instance of the default agent.

        Returns:
            Default agent instance or None
        """
        if not self._default_agent:
            logger.warning("No default agent configured")
            return None

        return self.create_agent(self._default_agent)

    def list_agents(self) -> List[str]:
        """
        List all registered agent names.

        Returns:
            List of agent names
        """
        return list(self._agents.keys())

    def get_agent_info(self, name: str) -> Optional[Dict[str, Any]]:
        """
        Get detailed information about an agent.

        Args:
            name: Name of the agent

        Returns:
            Dictionary with agent information or None
        """
        registration = self.get(name)
        if not registration:
            return None

        return {
            "name": name,
            "class": registration.agent_class.__name__,
            "module": registration.agent_class.__module__,
            "metadata": registration.metadata.to_dict(),
            "has_factory": registration.factory_func is not None,
            "is_default": registration.is_default
        }

    def get_all_agents_info(self) -> Dict[str, Dict[str, Any]]:
        """
        Get information about all registered agents.

        Returns:
            Dictionary mapping names to agent information
        """
        return {
            name: self.get_agent_info(name)
            for name in self.list_agents()
        }

    def auto_discover(self, package_path: str) -> int:
        """
        Auto-discover and register agents from a package.

        Looks for classes that:
        1. Inherit from BaseAgent
        2. Have a class attribute 'auto_register = True'
        3. Are not abstract classes

        Args:
            package_path: Path to package to scan (e.g., 'src.agents')

        Returns:
            Number of agents discovered and registered
        """
        discovered = 0

        try:
            # Import the package
            package = importlib.import_module(package_path)
            package_dir = Path(package.__file__).parent

            # Scan for Python modules
            for module_path in package_dir.glob("**/*.py"):
                if module_path.name.startswith("_"):
                    continue

                # Construct module name
                relative_path = module_path.relative_to(package_dir)
                module_name = str(relative_path)[:-3].replace("/", ".").replace("\\", ".")
                full_module_name = f"{package_path}.{module_name}"

                try:
                    # Import the module
                    module = importlib.import_module(full_module_name)

                    # Scan for agent classes
                    for name, obj in inspect.getmembers(module, inspect.isclass):
                        if (
                            issubclass(obj, BaseAgent) and
                            obj != BaseAgent and
                            getattr(obj, "auto_register", False)
                        ):
                            # Get registration name
                            reg_name = getattr(obj, "registration_name", name.lower())

                            # Register the agent
                            try:
                                self.register(reg_name, obj)
                                discovered += 1
                                logger.info(f"Auto-discovered agent: {reg_name}")
                            except ValueError:
                                # Already registered
                                pass

                except ImportError as e:
                    logger.debug(f"Could not import {full_module_name}: {e}")
                    continue

        except Exception as e:
            logger.error(f"Error during auto-discovery: {e}")

        logger.info(f"Auto-discovered {discovered} agents from {package_path}")
        return discovered

    def clear(self) -> None:
        """Clear all registered agents."""
        self._agents.clear()
        self._default_agent = None
        logger.info("Cleared all agent registrations")

    def __contains__(self, name: str) -> bool:
        """Check if an agent is registered."""
        return name in self._agents

    def __len__(self) -> int:
        """Get the number of registered agents."""
        return len(self._agents)

    def __repr__(self) -> str:
        """String representation."""
        return (
            f"<AgentRegistry agents={len(self._agents)} "
            f"default='{self._default_agent}'>"
        )


# Global registry instance
registry = AgentRegistry()