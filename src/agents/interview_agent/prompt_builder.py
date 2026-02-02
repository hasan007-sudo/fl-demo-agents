"""
Interview agent prompt builder with dynamic context.
"""

from typing import Dict, Optional, Any
from pathlib import Path
from jinja2 import Environment, FileSystemLoader
from core.prompts.base import BasePromptBuilder
from core.context.base import BaseContext
from .context import InterviewAgentContext, InterviewMode

import logging
logger = logging.getLogger(__name__)


class InterviewPromptBuilder(BasePromptBuilder):
    """Prompt builder for Interview agent using Jinja2 templates."""

    _jinja_env: Optional[Environment] = None

    def _initialize_sections(self) -> None:
        """No pre-defined sections, we use templates."""
        pass

    def _get_prompts_dir(self) -> Path:
        """Get the prompts directory path."""
        return Path(__file__).parent / "prompts"

    def _get_jinja_env(self) -> Environment:
        """Get or create the shared Jinja2 environment."""
        if InterviewPromptBuilder._jinja_env is None:
            prompts_dir = self._get_prompts_dir()
            env = Environment(
                loader=FileSystemLoader(str(prompts_dir)),
                trim_blocks=True,
                lstrip_blocks=True,
            )
            InterviewPromptBuilder._jinja_env = env

        return InterviewPromptBuilder._jinja_env

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
        """Build prompt using appropriate interview template based on mode."""
        # Select template based on mode
        template_name = "interview_practice.md"  # default
        if context and isinstance(context, InterviewAgentContext):
            if context.mode == InterviewMode.MOCK:
                template_name = "interview_mock.md"
            elif context.mode == InterviewMode.DIAGNOSTIC:
                template_name = "interview_diagnostic.md"
            else:
                template_name = "interview_practice.md"
        logger.info(f"Building prompt using template: {template_name}")

        context_dict = {}
        if context and isinstance(context, InterviewAgentContext):
            context_dict = {
                k: v for k, v in context.__dict__.items()
                if k != 'agent_type' and v is not None
            }
            context_dict['questions_summary'] = context.get_questions_summary_for_prompt()
            context_dict['undiscussed_questions'] = context.get_undiscussed_questions()
            logger.debug(f"Context keys: {list(context_dict.keys())}")

        try:
            instructions = self._render_template(template_name, context_dict)
            logger.info(f"Built instructions. Length: {len(instructions)} chars")
            return instructions
        except FileNotFoundError as e:
            logger.error(f"Template not found: {e}")
            raise

    def build_default(self) -> str:
        """Build default prompt when no context is available."""
        return self._render_template("interview_practice.md", {})

    def _extract_variables(self, context: BaseContext) -> Dict[str, Any]:
        """Extract variables from context."""
        if isinstance(context, InterviewAgentContext):
            return {k: v for k, v in context.__dict__.items() if v is not None}
        return {}
