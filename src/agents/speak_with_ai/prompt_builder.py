"""
SpeakWithAI prompt builder with dynamic context.

Supports Jinja2 templates for conversation and feedback agents.
"""

from typing import Dict, Optional, Any
from pathlib import Path
from jinja2 import Environment, FileSystemLoader
from core.prompts.base import BasePromptBuilder
from core.context.base import BaseContext
from .context import SpeakWithAIContext

import logging
logger = logging.getLogger(__name__)


class SpeakWithAIPromptBuilder(BasePromptBuilder):
    """
    Prompt builder for SpeakWithAI using Jinja2 templates.
    """

    # Class-level cached Jinja2 environment
    _jinja_env: Optional[Environment] = None

    def _initialize_sections(self) -> None:
        """No pre-defined sections, we use templates."""
        pass

    def _get_prompts_dir(self) -> Path:
        """Get the prompts directory path."""
        return Path(__file__).parent / "prompts"

    def _get_jinja_env(self) -> Environment:
        """Get or create the shared Jinja2 environment."""
        if SpeakWithAIPromptBuilder._jinja_env is None:
            prompts_dir = self._get_prompts_dir()
            env = Environment(
                loader=FileSystemLoader(str(prompts_dir)),
                trim_blocks=True,
                lstrip_blocks=True,
            )
            SpeakWithAIPromptBuilder._jinja_env = env

        return SpeakWithAIPromptBuilder._jinja_env

    def _render_template(self, template_name: str, context_dict: Dict[str, Any]) -> str:
        """Render a Jinja2 template with context."""
        prompts_dir = self._get_prompts_dir()
        template_path = prompts_dir / template_name

        if not template_path.exists():
            raise FileNotFoundError(
                f"Prompt template '{template_name}' not found at {template_path}."
            )

        env = self._get_jinja_env()
        template = env.get_template(template_name)
        return template.render(**context_dict)

    def build(self, context: BaseContext) -> str:
        """Build prompt using default template."""
        return self.build_for_agent("conversation", context)

    def build_default(self) -> str:
        """Build default prompt when no context is available."""
        return self._render_template("conversation.md", {})

    def build_for_agent(
        self,
        agent_type: str,
        context: Optional[BaseContext] = None
    ) -> str:
        """
        Build prompt for a specific agent type.

        Args:
            agent_type: Type of agent ("conversation" or "feedback")
            context: Optional context to use for building the prompt

        Returns:
            Complete instructions for the specified agent
        """
        valid_types = ["conversation", "feedback"]
        if agent_type not in valid_types:
            raise ValueError(
                f"Unknown agent type: {agent_type}. "
                f"Expected one of: {', '.join(valid_types)}"
            )

        template_name = f"{agent_type}.md"
        logger.info(f"Building prompt for agent: {agent_type} using template: {template_name}")

        context_dict = {}
        if context and isinstance(context, SpeakWithAIContext):
            context_dict = {
                k: v for k, v in context.__dict__.items()
                if k != 'agent_type' and v is not None
            }
            # Add computed properties
            context_dict['questions_summary'] = context.get_questions_summary_for_prompt()
            context_dict['undiscussed_questions'] = context.get_undiscussed_questions()
            logger.debug(f"Context keys: {list(context_dict.keys())}")

        try:
            instructions = self._render_template(template_name, context_dict)
            logger.info(f"Built instructions for {agent_type}. Length: {len(instructions)} chars")
            return instructions
        except FileNotFoundError as e:
            logger.error(f"Template not found for {agent_type}: {e}")
            raise

    def _extract_variables(self, context: BaseContext) -> Dict[str, Any]:
        """Extract variables from context."""
        if isinstance(context, SpeakWithAIContext):
            return {k: v for k, v in context.__dict__.items() if v is not None}
        return {}
