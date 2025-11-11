"""
Base prompt builder classes for constructing agent instructions.

Provides abstract base classes for building agent-specific prompts from context data.
Each agent type implements its own prompt builder to generate appropriate instructions.
"""

from abc import ABC, abstractmethod
from typing import Dict, Any, Optional, List, Callable
from dataclasses import dataclass
from enum import Enum
import logging
import re

from ..context.base import BaseContext

logger = logging.getLogger(__name__)


class PromptSection(Enum):
    """Standard prompt sections that can be composed."""
    ROLE = "role"
    PERSONALITY = "personality"
    CONTEXT = "context"
    CAPABILITIES = "capabilities"
    CONSTRAINTS = "constraints"
    INSTRUCTIONS = "instructions"
    EXAMPLES = "examples"
    ERROR_HANDLING = "error_handling"
    CLOSING = "closing"


@dataclass
class PromptTemplate:
    """
    A template for a prompt section.

    Attributes:
        section: The section this template belongs to
        template: The template string with {placeholders}
        required: Whether this section is required
        order: The order in which to render this section
    """
    section: PromptSection
    template: str
    required: bool = False
    order: int = 0

    def render(self, variables: Dict[str, Any]) -> str:
        """
        Render the template with variables.

        Args:
            variables: Dictionary of variables to substitute

        Returns:
            Rendered template string
        """
        try:
            return self.template.format(**variables)
        except KeyError as e:
            logger.warning(f"Missing variable in template: {e}")
            # Return template with missing variables as-is
            return self.template


class BasePromptBuilder(ABC):
    """
    Abstract base class for all prompt builders.

    SIMPLE EXPLANATION:
    ==================
    This is like a Mad Libs template for creating AI instructions.
    Each agent fills in the blanks with their specific requirements.

    What it does:
    1. Provides a consistent structure for all agent prompts
    2. Breaks prompts into sections (role, personality, instructions, etc.)
    3. Combines user preferences with agent-specific instructions

    How it works:
    1. Takes context (user preferences) as input
    2. Fills in template sections based on the context
    3. Combines all sections into a complete prompt
    4. Returns the final instructions for the AI

    Example sections:
    - Role: "You are an English tutor"
    - Personality: "Be friendly and encouraging"
    - Instructions: "Correct grammar mistakes"
    - Constraints: "Keep sessions under 5 minutes"

    Each agent (English Tutor, Interview Preparer) creates their own
    specific prompt builder that fills in these sections differently.
    """

    def __init__(self):
        """Initialize the prompt builder."""
        self._sections: Dict[PromptSection, PromptTemplate] = {}
        self._custom_sections: Dict[str, str] = {}
        self._processors: List[Callable[[str], str]] = []
        self._initialize_sections()

    @abstractmethod
    def _initialize_sections(self) -> None:
        """
        Initialize the default sections for this prompt builder.

        Subclasses should override this to set up their default templates.
        """
        pass

    def build(self, context: BaseContext) -> str:
        """
        Build the complete prompt from the context.

        Args:
            context: The context to build the prompt from

        Returns:
            The complete prompt string
        """
        # Extract variables from context
        variables = self._extract_variables(context)

        # Build each section
        sections = []
        for section in sorted(
            self._sections.values(),
            key=lambda s: s.order
        ):
            rendered = self._render_section(section, variables)
            if rendered:
                sections.append(rendered)

        # Add custom sections
        for custom_content in self._custom_sections.values():
            sections.append(custom_content)

        # Combine sections
        prompt = self._combine_sections(sections)

        # Apply post-processors
        for processor in self._processors:
            prompt = processor(prompt)

        return prompt

    @abstractmethod
    def build_default(self) -> str:
        """
        Build a default prompt when no context is available.

        Returns:
            Default prompt string
        """
        pass

    @abstractmethod
    def _extract_variables(self, context: BaseContext) -> Dict[str, Any]:
        """
        Extract variables from the context for template rendering.

        Args:
            context: The context object

        Returns:
            Dictionary of variables for template substitution
        """
        pass

    def _render_section(
        self,
        template: PromptTemplate,
        variables: Dict[str, Any]
    ) -> Optional[str]:
        """
        Render a single section.

        Args:
            template: The template to render
            variables: Variables for substitution

        Returns:
            Rendered section or None if not applicable
        """
        # Check if section should be included
        if not self._should_include_section(template, variables):
            return None

        # Render the template
        rendered = template.render(variables)

        # Apply section-specific formatting
        return self._format_section(template.section, rendered)

    def _should_include_section(
        self,
        template: PromptTemplate,
        variables: Dict[str, Any]
    ) -> bool:
        """
        Determine if a section should be included.

        Args:
            template: The template to check
            variables: Current variables

        Returns:
            True if section should be included
        """
        # Always include required sections
        if template.required:
            return True

        # Check for section-specific conditions
        return self._check_section_conditions(template.section, variables)

    def _check_section_conditions(
        self,
        section: PromptSection,
        variables: Dict[str, Any]
    ) -> bool:
        """
        Check conditions for including a section.

        Args:
            section: The section to check
            variables: Current variables

        Returns:
            True if conditions are met

        Note:
            Subclasses can override for custom logic
        """
        return True

    def _format_section(
        self,
        section: PromptSection,
        content: str
    ) -> str:
        """
        Apply formatting to a section.

        Args:
            section: The section type
            content: The section content

        Returns:
            Formatted content
        """
        # Default formatting - can be overridden
        if section == PromptSection.ROLE:
            return f"# Role\n{content}\n"
        elif section == PromptSection.INSTRUCTIONS:
            return f"# Instructions\n{content}\n"
        elif section == PromptSection.CONSTRAINTS:
            return f"# Constraints\n{content}\n"
        elif section == PromptSection.EXAMPLES:
            return f"# Examples\n{content}\n"
        else:
            return f"{content}\n"

    def _combine_sections(self, sections: List[str]) -> str:
        """
        Combine sections into a complete prompt.

        Args:
            sections: List of rendered sections

        Returns:
            Combined prompt
        """
        return "\n".join(sections).strip()

    def add_section(
        self,
        section: PromptSection,
        template: str,
        required: bool = False,
        order: Optional[int] = None
    ) -> 'BasePromptBuilder':
        """
        Add or update a section template.

        Args:
            section: The section type
            template: The template string
            required: Whether this section is required
            order: The rendering order (auto-assigned if None)

        Returns:
            Self for chaining
        """
        if order is None:
            # Auto-assign order based on section type
            order = list(PromptSection).index(section) * 10

        self._sections[section] = PromptTemplate(
            section=section,
            template=template,
            required=required,
            order=order
        )
        return self

    def add_custom_section(
        self,
        name: str,
        content: str
    ) -> 'BasePromptBuilder':
        """
        Add a custom section not in the standard sections.

        Args:
            name: Name of the custom section
            content: The section content

        Returns:
            Self for chaining
        """
        self._custom_sections[name] = content
        return self

    def add_processor(
        self,
        processor: Callable[[str], str]
    ) -> 'BasePromptBuilder':
        """
        Add a post-processor to transform the final prompt.

        Args:
            processor: Function that transforms the prompt

        Returns:
            Self for chaining
        """
        self._processors.append(processor)
        return self

    def clear_section(self, section: PromptSection) -> 'BasePromptBuilder':
        """
        Remove a section from the prompt.

        Args:
            section: The section to remove

        Returns:
            Self for chaining
        """
        self._sections.pop(section, None)
        return self


class ComposablePromptBuilder(BasePromptBuilder):
    """
    A prompt builder that supports composition of multiple builders.

    This allows for mixing and matching prompt components from
    different sources.
    """

    def __init__(self):
        """Initialize the composable builder."""
        super().__init__()
        self._components: List[BasePromptBuilder] = []

    def add_component(
        self,
        component: BasePromptBuilder
    ) -> 'ComposablePromptBuilder':
        """
        Add a component builder.

        Args:
            component: Builder to add

        Returns:
            Self for chaining
        """
        self._components.append(component)
        return self

    def build(self, context: BaseContext) -> str:
        """
        Build prompt by combining all components.

        Args:
            context: The context object

        Returns:
            Combined prompt
        """
        prompts = []

        # Build from each component
        for component in self._components:
            prompts.append(component.build(context))

        # Add own sections
        prompts.append(super().build(context))

        # Combine all prompts
        return "\n\n".join(filter(None, prompts))

    def _initialize_sections(self) -> None:
        """Initialize sections (empty for composable builder)."""
        pass

    def build_default(self) -> str:
        """Build default prompt from all components."""
        defaults = []

        for component in self._components:
            defaults.append(component.build_default())

        return "\n\n".join(filter(None, defaults))

    def _extract_variables(self, context: BaseContext) -> Dict[str, Any]:
        """Extract variables from context."""
        return context.to_dict()


class TemplatePromptBuilder(BasePromptBuilder):
    """
    A prompt builder that uses external template files.

    Supports loading templates from files and string templates.
    """

    def __init__(self, template_path: Optional[str] = None):
        """
        Initialize with optional template file.

        Args:
            template_path: Path to template file
        """
        self.template_path = template_path
        super().__init__()

    def _initialize_sections(self) -> None:
        """Load template if path provided."""
        if self.template_path:
            self._load_template(self.template_path)

    def _load_template(self, path: str) -> None:
        """
        Load template from file.

        Args:
            path: Path to template file
        """
        try:
            with open(path, 'r') as f:
                template_content = f.read()
                self._parse_template(template_content)
        except Exception as e:
            logger.error(f"Failed to load template from {path}: {e}")

    def _parse_template(self, content: str) -> None:
        """
        Parse template content into sections.

        Args:
            content: Template content
        """
        # Simple section parser - can be enhanced
        section_pattern = r'#\s*(\w+)\s*\n(.*?)(?=\n#|\Z)'
        matches = re.findall(section_pattern, content, re.DOTALL)

        for section_name, section_content in matches:
            # Map to PromptSection enum if possible
            try:
                section = PromptSection(section_name.lower())
                self.add_section(section, section_content.strip())
            except ValueError:
                # Add as custom section
                self.add_custom_section(section_name, section_content.strip())

    def build_default(self) -> str:
        """Build default prompt."""
        return "You are a helpful AI assistant."

    def _extract_variables(self, context: BaseContext) -> Dict[str, Any]:
        """Extract all context variables."""
        return context.to_dict()