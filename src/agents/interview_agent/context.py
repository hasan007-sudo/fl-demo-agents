"""
Context definition for Interview agent.

Tracks questions from room metadata and discussion state.
"""

from typing import Optional, List, Dict, Any
from dataclasses import dataclass, field
from core.context.base import BaseContext


@dataclass
class Question:
    """Represents a question for interview guidance."""
    text: str
    hint: str
    identifier: str
    description: str

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Question':
        """Create Question from dictionary."""
        return cls(
            text=data.get("text", ""),
            hint=data.get("hint", ""),
            identifier=data.get("identifier", ""),
            description=data.get("description", ""),
        )


@dataclass
class InterviewAgentContext(BaseContext):
    """
    Context data for Interview agent.

    Stores questions from frontend and tracks discussion state.
    """
    # Frontend context (from room metadata)
    student_name: Optional[str] = None
    email: Optional[str] = None
    gender_preference: Optional[str] = None
    prompt: Optional[str] = None  # Main instructions from room metadata

    # Interview mode: True = realistic mock interview, False = practice with feedback
    mock_interview: bool = False

    # Language preference for practice sessions (not used in mock interviews)
    comfortable_language: Optional[str] = None

    # Questions list from frontend
    questions: List[Question] = field(default_factory=list)

    # Session state (runtime tracking)
    questions_discussed: List[str] = field(default_factory=list)
    current_question_id: Optional[str] = None
    topics_discussed: List[str] = field(default_factory=list)

    # Job context
    job_ctx: Optional[Any] = None

    def __post_init__(self):
        """Initialize with default agent type."""
        if not self.agent_type:
            self.agent_type = "interview_agent"
        super().__post_init__()

    def validate(self):
        """Validate the context data."""
        super().validate()
        if self.questions is None:
            self.questions = []

    def get_question_by_id(self, identifier: str) -> Optional[Question]:
        """Get a question by its identifier."""
        for q in self.questions:
            if q.identifier == identifier:
                return q
        return None

    def set_current_question(self, identifier: str) -> Optional[Question]:
        """
        Set the current question being discussed.

        Args:
            identifier: The question identifier to set as current

        Returns:
            The Question object if found, None otherwise
        """
        question = self.get_question_by_id(identifier)
        if question:
            self.current_question_id = identifier
            return question
        return None

    def mark_question_discussed(self, identifier: str) -> bool:
        """Mark a question as discussed and clear current question."""
        if identifier not in self.questions_discussed:
            question = self.get_question_by_id(identifier)
            if question:
                self.questions_discussed.append(identifier)
                # Clear current question if it matches
                if self.current_question_id == identifier:
                    self.current_question_id = None
                return True
        return False

    def get_questions_for_frontend(self) -> list:
        """
        Get questions list formatted for frontend (without hints).

        Returns:
            List of question dicts with id, text, description
        """
        return [
            {
                "id": q.identifier,
                "text": q.text,
                "description": q.description,
            }
            for q in self.questions
        ]

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
            f"Candidate: {self.student_name or 'Unknown'}, "
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
                f"{i}. {status} ID: \"{q.identifier}\" - {q.text}\n"
                f"   Hint: {q.hint}\n"
                f"   Context: {q.description}"
            )
        return "\n".join(lines)

    @classmethod
    def from_metadata(cls, metadata: Dict[str, Any]) -> 'InterviewAgentContext':
        """Parse InterviewAgentContext from room metadata."""
        from utils.helpers import camel_to_snake

        context_data = {
            camel_to_snake(k): v
            for k, v in metadata.items()
            if k != "agentType" and k != "agent_type"
        }

        nested_context = context_data.get("context", {})
        raw_questions = nested_context.get("questions", [])
        questions = [Question.from_dict(q) for q in raw_questions]

        return cls(
            agent_type="interview_agent",
            student_name=nested_context.get("student_name") or nested_context.get("studentName"),
            email=nested_context.get("email"),
            gender_preference=nested_context.get("gender_preference") or nested_context.get("genderPreference"),
            prompt=nested_context.get("prompt"),
            mock_interview=nested_context.get("mock_interview") or nested_context.get("mockInterview") or False,
            comfortable_language=nested_context.get("comfortable_language") or nested_context.get("comfortableLanguage"),
            questions=questions,
        )
