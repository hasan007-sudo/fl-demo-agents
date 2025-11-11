"""
Base context classes for agent context management.

Provides abstract base classes for agent-specific context handling including:
- Context data validation
- Serialization to/from dictionaries
- JSON conversion
"""

from abc import ABC, abstractmethod
from typing import Dict, Any, Optional, TypeVar, Generic, Type
from dataclasses import dataclass, field, asdict
import json
import logging
from enum import Enum

logger = logging.getLogger(__name__)

# Type variable for self-referencing in base class
TContext = TypeVar('TContext', bound='BaseContext')


@dataclass
class BaseContext(ABC):
    """
    Abstract base class for all agent contexts.

    Each agent type extends this to add their specific fields.
    EnglishTutorContext and InterviewContext inherit from this class.
    """

    agent_type: str

    def __post_init__(self):
        """Post-initialization validation."""
        self.validate()

    @abstractmethod
    def validate(self) -> None:
        """
        Validate the context data.

        Raises:
            ValueError: If the context data is invalid
        """
        if not self.agent_type:
            raise ValueError("agent_type is required")

    def to_dict(self) -> Dict[str, Any]:
        """
        Convert context to a dictionary.

        Returns:
            Dictionary representation of the context
        """
        return asdict(self)

    @classmethod
    def from_dict(cls: Type[TContext], data: Dict[str, Any]) -> TContext:
        """
        Create context from a dictionary.

        Args:
            data: Dictionary containing context data

        Returns:
            Context instance

        Raises:
            ValueError: If required fields are missing
        """
        return cls(**data)

    def merge(self: TContext, other: Optional[TContext]) -> TContext:
        """
        Merge this context with another, with other taking precedence.

        Args:
            other: Another context to merge with

        Returns:
            New context with merged data
        """
        if other is None:
            return self

        merged_data = self.to_dict()
        other_data = other.to_dict()

        # Merge dictionaries, with other taking precedence
        for key, value in other_data.items():
            if value is not None:
                merged_data[key] = value

        return self.__class__.from_dict(merged_data)

    def __repr__(self) -> str:
        """String representation of the context."""
        return f"<{self.__class__.__name__} agent_type='{self.agent_type}'>"


class ContextParser(ABC, Generic[TContext]):
    """
    Abstract base class for context parsers.

    Parsers are responsible for extracting context from room metadata
    and transforming them into the appropriate context objects.
    """

    def __init__(self, context_class: Type[TContext]):
        """
        Initialize the parser.

        Args:
            context_class: The context class this parser creates
        """
        self.context_class = context_class
        logger.info(f"Initialized {self.__class__.__name__} for {context_class.__name__}")

    @abstractmethod
    def parse(self, room_metadata: str) -> Optional[TContext]:
        """
        Parse context from room metadata.

        Args:
            room_metadata: Raw room metadata (JSON string)

        Returns:
            Parsed context object or None if parsing fails
        """
        pass

    def parse_json(self, json_str: str) -> Optional[TContext]:
        """
        Parse context from JSON string.

        Args:
            json_str: JSON string containing context data

        Returns:
            Parsed context object or None if parsing fails
        """
        try:
            data = json.loads(json_str)
            return self.parse_dict(data)
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse JSON: {e}")
            return None
        except Exception as e:
            logger.error(f"Unexpected error parsing JSON: {e}")
            return None

    @abstractmethod
    def parse_dict(self, data: Dict[str, Any]) -> Optional[TContext]:
        """
        Parse context from a dictionary.

        Args:
            data: Dictionary containing context data

        Returns:
            Parsed context object or None if parsing fails
        """
        pass

    def validate_required_fields(
        self,
        data: Dict[str, Any],
        required_fields: list[str]
    ) -> bool:
        """
        Validate that all required fields are present.

        Args:
            data: Dictionary to validate
            required_fields: List of required field names

        Returns:
            True if all required fields are present
        """
        missing = [field for field in required_fields if field not in data]
        if missing:
            logger.warning(f"Missing required fields: {missing}")
            return False
        return True

    def transform_field_names(
        self,
        data: Dict[str, Any],
        transformations: Dict[str, str]
    ) -> Dict[str, Any]:
        """
        Transform field names in a dictionary.

        Args:
            data: Original dictionary
            transformations: Mapping of old names to new names

        Returns:
            Dictionary with transformed field names
        """
        transformed = {}
        for key, value in data.items():
            new_key = transformations.get(key, key)
            transformed[new_key] = value
        return transformed

    def extract_nested_field(
        self,
        data: Dict[str, Any],
        path: str,
        default: Any = None
    ) -> Any:
        """
        Extract a nested field using dot notation.

        Args:
            data: Dictionary to extract from
            path: Dot-separated path (e.g., "user.preferences.language")
            default: Default value if path not found

        Returns:
            Extracted value or default
        """
        keys = path.split('.')
        value = data

        for key in keys:
            if isinstance(value, dict) and key in value:
                value = value[key]
            else:
                return default

        return value


class BaseContextBuilder(Generic[TContext]):
    """
    Builder pattern for constructing context objects.

    Provides a fluent interface for building complex contexts step by step.
    """

    def __init__(self, context_class: Type[TContext]):
        """
        Initialize the builder.

        Args:
            context_class: The context class to build
        """
        self.context_class = context_class
        self._data: Dict[str, Any] = {}

    def with_agent_type(self, agent_type: str) -> 'BaseContextBuilder[TContext]':
        """
        Set the agent type.

        Args:
            agent_type: The agent type identifier

        Returns:
            Self for chaining
        """
        self._data['agent_type'] = agent_type
        return self

    def with_session_id(self, session_id: str) -> 'BaseContextBuilder[TContext]':
        """
        Set the session ID.

        Args:
            session_id: The session identifier

        Returns:
            Self for chaining
        """
        self._data['session_id'] = session_id
        return self

    def with_user_id(self, user_id: str) -> 'BaseContextBuilder[TContext]':
        """
        Set the user ID.

        Args:
            user_id: The user identifier

        Returns:
            Self for chaining
        """
        self._data['user_id'] = user_id
        return self

    def with_metadata(
        self,
        metadata: Dict[str, Any]
    ) -> 'BaseContextBuilder[TContext]':
        """
        Set the metadata.

        Args:
            metadata: Metadata dictionary

        Returns:
            Self for chaining
        """
        self._data['metadata'] = metadata
        return self


    def build(self) -> TContext:
        """
        Build the context object.

        Returns:
            The constructed context

        Raises:
            ValueError: If required fields are missing
        """
        return self.context_class.from_dict(self._data)