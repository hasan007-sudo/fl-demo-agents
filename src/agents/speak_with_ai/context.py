"""
Context definition for SpeakWithAI agent.

Tracks questions from room metadata and discussion state.
"""

from typing import Optional, List, Dict, Any
from dataclasses import dataclass, field
from core.context.base import BaseContext


@dataclass
class Question:
    """Represents a question for conversation guidance."""
    text: str
    hint: str
    identifier: str
    description: str
    eval_prompt: str

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Question':
        """Create Question from dictionary."""
        return cls(
            text=data.get("text", ""),
            hint=data.get("hint", ""),
            identifier=data.get("identifier", ""),
            description=data.get("description", ""),
            eval_prompt=data.get("evalPrompt", data.get("eval_prompt", ""))
        )


@dataclass
class SpeakWithAIContext(BaseContext):
    """
    Context data for SpeakWithAI agent.

    Stores questions from frontend and tracks discussion state.
    """
    # =============================================================================
    # FRONTEND CONTEXT (from room metadata)
    # =============================================================================
    student_name: Optional[str] = None
    gender_preference: Optional[str] = None  # "male" or "female" for voice selection

    # Questions list from frontend
    questions: List[Question] = field(default_factory=list)

    # =============================================================================
    # SESSION STATE (runtime tracking for multi-agent orchestration)
    # =============================================================================
    # Track which questions were discussed (by identifier)
    questions_discussed: List[str] = field(default_factory=list)

    # Current question being explored
    current_question_id: Optional[str] = None

    # General topics that emerged during conversation
    topics_discussed: List[str] = field(default_factory=list)

    # Agent references for handoff
    conversation_agent: Optional[Any] = None
    feedback_agent: Optional[Any] = None
    previous_agent: Optional[Any] = None

    # Job context
    job_ctx: Optional[Any] = None

    def __post_init__(self):
        """Initialize with default agent type."""
        if not self.agent_type:
            self.agent_type = "speak_with_ai"
        super().__post_init__()

    def validate(self):
        """Validate the context data."""
        super().validate()
        # Questions list is optional but should be a list
        if self.questions is None:
            self.questions = []

    def get_question_by_id(self, identifier: str) -> Optional[Question]:
        """Get a question by its identifier."""
        for q in self.questions:
            if q.identifier == identifier:
                return q
        return None

    def mark_question_discussed(self, identifier: str) -> bool:
        """
        Mark a question as discussed.

        Args:
            identifier: The question identifier

        Returns:
            True if question was found and marked, False otherwise
        """
        if identifier not in self.questions_discussed:
            question = self.get_question_by_id(identifier)
            if question:
                self.questions_discussed.append(identifier)
                return True
        return False

    def get_undiscussed_questions(self) -> List[Question]:
        """Get list of questions not yet discussed."""
        return [
            q for q in self.questions
            if q.identifier not in self.questions_discussed
        ]

    def add_topic(self, topic: str) -> None:
        """Add a discussed topic to tracking."""
        if topic and topic not in self.topics_discussed:
            self.topics_discussed.append(topic)

    def summarize(self) -> str:
        """Generate a summary string for system messages."""
        discussed_count = len(self.questions_discussed)
        total_count = len(self.questions)
        topics_str = ", ".join(self.topics_discussed[:3]) if self.topics_discussed else "None yet"

        return (
            f"Student: {self.student_name or 'Unknown'}, "
            f"Questions: {discussed_count}/{total_count} explored, "
            f"Topics: {topics_str}"
        )

    def get_questions_summary_for_prompt(self) -> str:
        """Get a formatted summary of questions for the AI prompt."""
        if not self.questions:
            return "No specific questions provided."

        lines = []
        for i, q in enumerate(self.questions, 1):
            status = "[DISCUSSED]" if q.identifier in self.questions_discussed else "[AVAILABLE]"
            lines.append(
                f"{i}. {status} {q.text}\n"
                f"   Hint: {q.hint}\n"
                f"   Context: {q.description}"
            )
        return "\n".join(lines)

    @classmethod
    def from_metadata(cls, metadata: Dict[str, Any]) -> 'SpeakWithAIContext':
        """
        Parse SpeakWithAIContext from room metadata.

        Args:
            metadata: Room metadata dictionary from frontend

        Returns:
            SpeakWithAIContext instance
        """
        from utils.helpers import camel_to_snake

        # Convert camelCase keys to snake_case, exclude agentType
        context_data = {
            camel_to_snake(k): v
            for k, v in metadata.items()
            if k != "agentType" and k != "agent_type"
        }

        # Extract the nested context object if present
        nested_context = context_data.get("context", {})

        # Parse questions from the context
        raw_questions = nested_context.get("questions", [])
        questions = [Question.from_dict(q) for q in raw_questions]

        return cls(
            agent_type="speak_with_ai",
            student_name=nested_context.get("student_name") or nested_context.get("studentName"),
            gender_preference=nested_context.get("gender_preference") or nested_context.get("genderPreference"),
            questions=questions,
        )
