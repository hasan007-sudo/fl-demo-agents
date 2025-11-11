"""
English Tutor prompt builder with dynamic context.

This maintains 100% compatibility with the existing prompt building logic.
All dictionaries, templates, and logic remain exactly the same.
Now supports version-based prompts using Jinja2 templates.
"""

import os
from typing import Dict, Optional, Any
from pathlib import Path
from jinja2 import Environment, FileSystemLoader, TemplateNotFound
from core.prompts.base import BasePromptBuilder
from core.context.base import BaseContext
from .context import EnglishTutorContext

# CEFR proficiency level descriptions
PROFICIENCY_DESCRIPTIONS: Dict[str, str] = {
    "A1": "absolute beginner (basic phrases and simple sentences)",
    "A2": "elementary (basic conversations about familiar topics)",
    "B1": "intermediate (comfortable with everyday topics, some complexity)",
    "B2": "upper intermediate (fluent in most situations, handles abstract topics)",
    "C1": "advanced (fluent and spontaneous, sophisticated expression)",
    "C2": "mastery (near-native fluency, nuanced and precise communication)",
}

# Supported language names for comfortable language feature
LANGUAGE_NAMES: Dict[str, str] = {
    "hindi": "Hindi",
    "tamil": "Tamil",
    "telugu": "Telugu",
    "malayalam": "Malayalam",
    "kannada": "Kannada",
    "bengali": "Bengali",
    "marathi": "Marathi",
    "gujarati": "Gujarati",
    "punjabi": "Punjabi",
    "odia": "Odia",
}

# Speaking speed instructions
SPEED_INSTRUCTIONS: Dict[str, str] = {
    "very_slow": "Speak very slowly and clearly. Pause between sentences to give the user time to process. Enunciate each word carefully.",
    "slow": "Speak at a slower-than-normal pace with clear enunciation. Give the user time to follow along.",
    "fast": "Speak at a natural native pace, but maintain clarity. This will help the user practice listening at real-world speeds.",
}

# Correction preference instructions
CORRECTION_INSTRUCTIONS: Dict[str, str] = {
    "immediately": "When the user makes a mistake, gently correct it immediately by modeling the correct form in your response. Do this naturally without being disruptive.",
    "let_me_finish": "Let the user complete their thoughts without interruption. After they finish speaking, provide gentle corrections if they made any significant mistakes. Frame corrections positively.",
    "major_only": "Only correct major mistakes that impede understanding. Let minor errors slide to maintain conversational flow and build confidence. Focus on communication over perfection.",
    "focus_on_fluency": "Prioritize fluency and confidence over accuracy. Rarely correct mistakes unless they significantly impact meaning. Celebrate their efforts to speak and express themselves.",
}

# Vocabulary guidance based on CEFR level
VOCAB_GUIDANCE: Dict[str, str] = {
    "A1": "Use very simple, everyday vocabulary and short, basic sentences. Speak slowly and clearly. Be extremely patient and give lots of encouragement. Focus on building confidence with basic phrases.",
    "A2": "Use simple vocabulary and straightforward sentence structures. Introduce slightly challenging words with context. Be patient and encouraging. Help them expand from basic to elementary communication.",
    "B1": "Use standard vocabulary with occasional challenging words slightly above their level. Use natural expressions but avoid complex idioms. Help them stretch their abilities while remaining supportive.",
    "B2": "Use natural vocabulary including some idioms and colloquial expressions. Challenge them with more complex sentence structures and abstract topics. Maintain an encouraging but slightly more demanding approach.",
    "C1": "Use sophisticated vocabulary and natural expressions freely. Include idioms, phrasal verbs, and nuanced language. Engage in complex, abstract discussions while maintaining an encouraging tone.",
    "C2": "Use advanced vocabulary, subtle expressions, and complex structures. Challenge them with nuanced concepts, wordplay, and sophisticated topics. Focus on refinement and native-like precision.",
}


def build_tutor_instructions(context: Optional[Dict] = None) -> str:
    """
    Build optimized realtime instruction prompt for the spoken English tutor agent.
    Keeps all adaptive and procedural logic, but reformatted for OpenAI Realtime models.
    """

    if context is None:
        context = {}

    student_name = context.get("student_name", "")
    proficiency = context.get("proficiency_level", "B1")
    gender_pref = context.get("gender_preference", "no_preference")
    speaking_speed = context.get("speaking_speed", "normal")
    interests = context.get("interests", [])
    goals = context.get("learning_goals", [])
    comfortable_lang = context.get("comfortable_language", "")
    tutor_styles = context.get("tutor_styles", ["encouraging"])
    correction_pref = context.get("correction_preference", "let_me_finish")

    proficiency_desc = PROFICIENCY_DESCRIPTIONS.get(proficiency, PROFICIENCY_DESCRIPTIONS["B1"])
    correction_text = CORRECTION_INSTRUCTIONS.get(correction_pref, CORRECTION_INSTRUCTIONS["let_me_finish"])
    vocab_text = VOCAB_GUIDANCE.get(proficiency, VOCAB_GUIDANCE["B1"])
    speed_text = SPEED_INSTRUCTIONS.get(speaking_speed) if speaking_speed != "normal" else None
    styles_text = " and ".join(tutor_styles) if tutor_styles else "encouraging"

    # ----------------------
    # Build concise persona
    # ----------------------
    persona_intro = "You are an expert spoken English tutor conducting a realtime voice lesson."
    if gender_pref == "male":
        persona_intro += " You sound like a friendly, professional male tutor."
    elif gender_pref == "female":
        persona_intro += " You sound like a friendly, professional female tutor."
    persona_intro += f" Your style is {styles_text}, adaptive, and encouraging."

    # ----------------------
    # Student context summary
    # ----------------------
    profile = f"The student’s English level is {proficiency} ({proficiency_desc})."
    if student_name:
        profile += f" Their name is {student_name}."
    if interests:
        profile += f" Their interests include {', '.join(interests)}."
    if goals:
        profile += f" Their learning goals are {', '.join(goals)}."
    if comfortable_lang:
        profile += f" They are comfortable in {comfortable_lang.title()}."
    if speaking_speed != "normal":
        profile += f" They prefer a {speaking_speed.replace('_', ' ')} speaking speed."
    profile += f" Correction preference: {correction_pref.replace('_', ' ')}."

    # ----------------------
    # Core teaching rules
    # ----------------------
    rules = [
        "Start naturally and maintain a warm, human conversational rhythm.",
        "Only greet once at the very beginning of the session.",
        "If the user interrupts, speaks first, or wants to discuss something specific, skip any planned greeting or transition and engage with their topic immediately.",
        "Adapt naturally to the student’s tone and energy. Avoid robotic pacing or repetition.",
        "Keep 95% of conversation in English, unless the student is truly struggling or requests to switch languages.",
        "Respond concisely to allow the student to speak more; aim for them to speak 60–70% of the time.",
        "Encourage them gently, use natural reinforcement like 'That’s great!' or 'Good job!'",
        "Never overuse praise or repeat greetings or introductions.",
    ]

    # ----------------------
    # Ice breaker (if applicable)
    # ----------------------
    ice_breaker = ""
    if comfortable_lang:
        ice_breaker = (
            f"Begin the session with a 30-second warm-up in {comfortable_lang.title()} to build comfort and rapport. "
            f"Greet {student_name or 'the student'} warmly in {comfortable_lang.title()} once at the start. "
            "Then have a short, casual chat about how they’re doing or something light. "
            "If they interrupt or want to skip to English, follow their lead immediately. "
            "After about 30 seconds, transition naturally into English with a line such as 'Now, let’s practice your English together. Are you ready?'. "
            "Make the transition feel smooth and natural, never abrupt."
        )

    # ----------------------
    # Early conversation focus
    # ----------------------
    first_minutes = (
        "Within the first 3 minutes in English, establish that this session helps them improve their English. "
        "If you already did the ice breaker, do not greet again. If not, start with a single brief greeting. "
        "Immediately ask an open-ended question about one of their interests. "
        "Show genuine curiosity and active listening. Build on their responses with follow-up questions. "
        "Provide positive feedback on strengths such as vocabulary, fluency, or pronunciation. "
        "Introduce one small speaking technique naturally (for example, asking them to elaborate or describe in more detail). "
        "Create an early moment of success where they notice their own fluency improving."
    )

    # ----------------------
    # Interests logic
    # ----------------------
    if interests and len(interests) > 1:
        interest_logic = (
            f"The student has multiple interests: {', '.join(interests)}. "
            "Never ask about all of them at once. Focus on one interest at a time. "
            "Start with the first one or whichever seems most engaging. "
            "After discussing one deeply for 1–2 minutes, transition naturally to the next interest. "
            "Prioritize depth and engagement over covering all topics quickly."
        )
    elif interests:
        interest_logic = f"The student’s main interest is {interests[0]}. Focus deeply on that topic and explore it from multiple angles."
    else:
        interest_logic = "The student’s interests are unknown. Ask exploratory questions to discover topics that engage them, then build the conversation around those."

    # ----------------------
    # Correction and vocabulary
    # ----------------------
    learning_guidance = (
        f"Vocabulary should match their level ({proficiency}). {vocab_text} "
        f"Correction style: {correction_text} "
        "Encourage risk-taking and fluency, not perfection. "
        "Only interrupt to correct if that’s consistent with their correction preference."
    )
    if speed_text:
        learning_guidance += f" Adjust your speaking pace accordingly: {speed_text}"

    # ----------------------
    # Closing sequence (critical)
    # ----------------------
    closing = (
        "The total session lasts 5 minutes. Begin the closing sequence exactly at 4 minutes and 40 seconds. "
        "At that moment, politely interrupt if needed and say: 'I'm sorry to interrupt, but I'm running out of time. Let's connect next time.' "
        "If time permits, give one brief positive comment about their progress (under 15 seconds). "
        "Never extend past 4:55. Do not start new topics after 4:40. "
        "This ensures a graceful end before the system closes automatically."
    )

    # ----------------------
    # Final assembly
    # ----------------------
    return (
        f"{persona_intro} {profile} "
        "Follow these behavioral principles carefully during the realtime conversation. "
        + " ".join(rules)
        + " "
        + (ice_breaker + " " if ice_breaker else "")
        + first_minutes + " "
        + interest_logic + " "
        + learning_guidance + " "
        + closing + " "
        "Speak naturally, adaptively, and like a real human tutor at all times."
    )

class EnglishTutorPromptBuilder(BasePromptBuilder):
    """
    Prompt builder for English Tutor that supports version-based Jinja2 templates.

    This wrapper maintains complete backward compatibility while integrating
    with the new architecture. Supports both version-based prompts from .md files
    and the legacy dynamic prompt generation.
    """

    # Class-level cached Jinja2 environment (thread-safe, reusable)
    _jinja_env: Optional[Environment] = None

    def _initialize_sections(self) -> None:
        """No pre-defined sections, we use templates."""
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
        if EnglishTutorPromptBuilder._jinja_env is None:
            prompts_dir = self._get_prompts_dir()
            env = Environment(
                loader=FileSystemLoader(str(prompts_dir)),
                trim_blocks=True,
                lstrip_blocks=True,
            )

            # Add dictionaries as global variables for templates
            env.globals.update({
                'PROFICIENCY_DESCRIPTIONS': PROFICIENCY_DESCRIPTIONS,
                'LANGUAGE_NAMES': LANGUAGE_NAMES,
                'SPEED_INSTRUCTIONS': SPEED_INSTRUCTIONS,
                'CORRECTION_INSTRUCTIONS': CORRECTION_INSTRUCTIONS,
                'VOCAB_GUIDANCE': VOCAB_GUIDANCE,
            })

            EnglishTutorPromptBuilder._jinja_env = env

        return EnglishTutorPromptBuilder._jinja_env

    def _render_template(self, template_name: str, context_dict: Dict[str, Any]) -> str:
        prompts_dir = self._get_prompts_dir()
        template_path = prompts_dir / template_name

        if not template_path.exists():
            raise FileNotFoundError(
                f"Prompt template '{template_name}' not found at {template_path}. "
                f"Please ensure the file exists in the prompts directory."
            )

        env = self._get_jinja_env()

        # Load and render template
        template = env.get_template(template_name)
        return template.render(**context_dict)

    def build(self, context: BaseContext) -> str:
        """
        Build prompt using version-based Jinja2 templates or legacy dynamic generation.

        If context contains a 'version' field, loads the corresponding template file
        (e.g., 'v1.md' for version='v1'). Otherwise, uses 'default.md' template.

        Args:
            context: The English Tutor context

        Returns:
            Complete instructions for the agent

        Raises:
            FileNotFoundError: If the specified version template doesn't exist
        """
        import logging
        logger = logging.getLogger(__name__)

        # Convert context to dictionary
        if isinstance(context, EnglishTutorContext):
            # Convert dataclass to dict, excluding base fields
            context_dict = {
                k: v for k, v in context.__dict__.items()
                if k != 'agent_type' and v is not None
            }
            logger.debug(f"Converted context to dict with keys: {list(context_dict.keys())}")
        else:
            context_dict = {}
            logger.warning(f"Context is not EnglishTutorContext, got: {type(context)}")

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
        """Build default prompt when no context is available."""
        return self._render_template("default.md", {})

    def _extract_variables(self, context: BaseContext) -> Dict[str, Any]:
        """Extract variables from context."""
        if isinstance(context, EnglishTutorContext):
            return {
                k: v for k, v in context.__dict__.items()
                if v is not None
            }
        return {}
