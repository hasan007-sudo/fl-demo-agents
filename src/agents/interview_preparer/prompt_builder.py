"""
Interview Preparer prompt builder.

Creates instructions for conducting mock interviews based on context.
Now supports version-based prompts using Jinja2 templates.
"""

import os
from typing import Dict, Any, Optional
from pathlib import Path
from jinja2 import Environment, FileSystemLoader, TemplateNotFound
from core.prompts.base import BasePromptBuilder
from core.context.base import BaseContext
from .context import InterviewContext

# Question guidelines based on interview type
QUESTION_GUIDELINES: Dict[str, str] = {
    "technical": """- Ask technical questions appropriate for the role and experience level
   - Start with fundamentals, then progress to complex problems
   - Include coding/algorithm questions if relevant
   - Test system design for senior roles
   - Assess problem-solving approach, not just the answer""",
    "behavioral": """- Use STAR method questions (Situation, Task, Action, Result)
   - Ask about past experiences and challenges
   - Focus on leadership, teamwork, conflict resolution
   - Probe for specific examples, not hypotheticals
   - Look for growth mindset and learning from failures""",
    "hr": """- Ask about career goals and motivations
   - Discuss salary expectations appropriately
   - Explore culture fit and work preferences
   - Address any resume gaps or transitions
   - Assess communication skills and professionalism""",
    "case_study": """- Present a realistic business problem
   - Guide through the problem-solving process
   - Ask clarifying questions about their approach
   - Challenge assumptions respectfully
   - Evaluate structured thinking and analysis""",
    "default": "- Ask a mix of behavioral and role-specific questions"
}

# Evaluation criteria based on interview type
EVALUATION_CRITERIA: Dict[str, str] = {
    "technical": """- Technical knowledge and depth
   - Problem-solving methodology
   - Code quality and efficiency
   - Communication of technical concepts
   - Ability to handle ambiguity""",
    "behavioral": """- Specific examples and detail
   - Leadership and initiative
   - Team collaboration
   - Problem resolution skills
   - Learning and adaptability""",
    "manager": """- Leadership experience and style
   - Team building and mentoring
   - Strategic thinking
   - Stakeholder management
   - Decision-making process""",
    "default": """- Relevant experience
   - Communication clarity
   - Problem-solving approach
   - Cultural fit
   - Growth potential"""
}


class InterviewPromptBuilder(BasePromptBuilder):
    """
    Prompt builder for Interview Preparer agent.

    Builds interview instructions based on role, type, and preferences.
    Now supports version-based prompts using Jinja2 templates.
    """

    # Class-level cached Jinja2 environment (thread-safe, reusable)
    _jinja_env: Optional[Environment] = None

    def _initialize_sections(self) -> None:
        """Initialize default prompt sections for interviews."""
        pass

    def _get_prompts_dir(self) -> Path:
        """Get the prompts directory path."""
        return Path(__file__).parent / "prompts"

    def _get_jinja_env(self) -> Environment:
        """
        Get or create the shared Jinja2 environment.

        Creates the environment once and reuses it for all subsequent calls.
        This is thread-safe and enables Jinja2's built-in template caching.

        Returns:
            Configured Jinja2 Environment instance
        """
        if InterviewPromptBuilder._jinja_env is None:
            prompts_dir = self._get_prompts_dir()
            env = Environment(
                loader=FileSystemLoader(str(prompts_dir)),
                trim_blocks=True,
                lstrip_blocks=True,
            )

            # Add dictionaries as global variables for templates
            env.globals.update({
                'QUESTION_GUIDELINES': QUESTION_GUIDELINES,
                'EVALUATION_CRITERIA': EVALUATION_CRITERIA,
            })

            InterviewPromptBuilder._jinja_env = env

        return InterviewPromptBuilder._jinja_env

    def _render_template(self, template_name: str, context_dict: Dict[str, Any]) -> str:
        """
        Render a Jinja2 template with the given context.

        Uses the shared Jinja2 environment for better performance and caching.

        Args:
            template_name: Name of the template file (e.g., 'v1.md', 'default.md')
            context_dict: Context variables to pass to the template

        Returns:
            Rendered template string

        Raises:
            FileNotFoundError: If the template file doesn't exist
        """
        # Verify template file exists before attempting to load
        prompts_dir = self._get_prompts_dir()
        template_path = prompts_dir / template_name

        if not template_path.exists():
            raise FileNotFoundError(
                f"Interview prompt template '{template_name}' not found at {template_path}. "
                f"Please ensure the file exists in the prompts directory."
            )

        # Get the shared Jinja2 environment (cached, thread-safe)
        env = self._get_jinja_env()

        # Load and render template
        template = env.get_template(template_name)
        return template.render(**context_dict)

    def build(self, context: BaseContext) -> str:
        """
        Build interview instructions using version-based Jinja2 templates or legacy dynamic generation.

        If context contains a 'version' field, loads the corresponding template file
        (e.g., 'v1.md' for version='v1'). Otherwise, uses 'default.md' template.

        Args:
            context: Interview context with preferences

        Returns:
            Complete instructions for conducting the interview

        Raises:
            FileNotFoundError: If the specified version template doesn't exist
        """
        import logging
        logger = logging.getLogger(__name__)

        if not isinstance(context, InterviewContext):
            return self.build_default()

        context_dict = {
            k: v for k, v in context.__dict__.items()
            if k != 'agent_type' and v is not None
        }
        logger.debug(f"Converted context to dict with keys: {list(context_dict.keys())}")

        # Determine which template to use
        version = context_dict.get('version')
        if version:
            template_name = f"{version}.md"
            logger.info(f"Using version-based template: {template_name}")
        else:
            template_name = "default.md"
            logger.info("No version specified, using default.md template")

        # Render the template using Jinja2
        try:
            instructions = self._render_template(template_name, context_dict)
            logger.info(f"Built instructions successfully. Length: {len(instructions)} chars")
            return instructions
        except FileNotFoundError as e:
            logger.error(f"Template not found: {e}")
            raise

    def build_default(self) -> str:
        """Build default interview instructions."""
        return """You are an experienced interview coach conducting a mock behavioral interview.

Help the candidate practice their interview skills by:
1. Asking relevant behavioral questions
2. Following up for specific examples
3. Providing constructive feedback
4. Maintaining a professional yet friendly demeanor

Start by introducing yourself and explaining the interview format."""

    def _extract_variables(self, context: BaseContext) -> Dict[str, Any]:
        """Extract variables from context."""
        if isinstance(context, InterviewContext):
            return context.__dict__
        return {}

    def _get_question_guidelines(self, interview_type: str, role: str, level: str) -> str:
        """Get guidelines for question selection based on interview type."""
        if interview_type == "technical":
            return f"""- Ask technical questions appropriate for a {level} {role}
   - Start with fundamentals, then progress to complex problems
   - Include coding/algorithm questions if relevant
   - Test system design for senior roles
   - Assess problem-solving approach, not just the answer"""

        elif interview_type == "behavioral":
            return """- Use STAR method questions (Situation, Task, Action, Result)
   - Ask about past experiences and challenges
   - Focus on leadership, teamwork, conflict resolution
   - Probe for specific examples, not hypotheticals
   - Look for growth mindset and learning from failures"""

        elif interview_type == "hr":
            return """- Ask about career goals and motivations
   - Discuss salary expectations appropriately
   - Explore culture fit and work preferences
   - Address any resume gaps or transitions
   - Assess communication skills and professionalism"""

        elif interview_type == "case_study":
            return """- Present a realistic business problem
   - Guide through the problem-solving process
   - Ask clarifying questions about their approach
   - Challenge assumptions respectfully
   - Evaluate structured thinking and analysis"""

        else:
            return "- Ask a mix of behavioral and role-specific questions"

    def _get_evaluation_criteria(self, interview_type: str, role: str) -> str:
        """Get evaluation criteria based on interview type and role."""
        if interview_type == "technical":
            return """- Technical knowledge and depth
   - Problem-solving methodology
   - Code quality and efficiency
   - Communication of technical concepts
   - Ability to handle ambiguity"""

        elif interview_type == "behavioral":
            return """- Specific examples and detail
   - Leadership and initiative
   - Team collaboration
   - Problem resolution skills
   - Learning and adaptability"""

        elif role and "manager" in role.lower():
            return """- Leadership experience and style
   - Team building and mentoring
   - Strategic thinking
   - Stakeholder management
   - Decision-making process"""

        else:
            return """- Relevant experience
   - Communication clarity
   - Problem-solving approach
   - Cultural fit
   - Growth potential"""