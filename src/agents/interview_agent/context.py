"""
Context definition for Interview agent.

Tracks questions from room metadata and discussion state.
"""

from typing import Optional, List, Dict, Any
from dataclasses import dataclass, field
from enum import Enum
from core.context.base import BaseContext


class InterviewMode(str, Enum):
    """Interview session modes."""
    MOCK = "mock"           # Realistic mock interview, no feedback
    PRACTICE = "practice"   # Practice with coaching and feedback
    DIAGNOSTIC = "diagnostic"  # Diagnostic mode with real-time feedback and hints


@dataclass
class Question:
    """Represents a question for interview guidance."""
    text: str
    hint: str
    identifier: str
    description: str

    @classmethod
    def from_dict(cls, data: Any) -> 'Question':
        """Create Question from dictionary or string."""
        # Handle case where data is just a string (the question text)
        if isinstance(data, str):
            return cls(
                text=data,
                hint="",
                identifier=data[:20].replace(" ", "_").lower(),  # Generate simple identifier
                description="",
            )
        # Handle dictionary format
        identifier = data.get("identifier") or data.get("id")
        if not isinstance(identifier, str):
            identifier = ""
        identifier = identifier.strip()
        if not identifier:
            identifier = data.get("text", "")[:20].replace(" ", "_").lower()

        return cls(
            text=data.get("text", ""),
            hint=data.get("hint", ""),
            identifier=identifier,
            description=data.get("description", ""),
        )


@dataclass
class ResumeTranscriptTurn:
    """Represents a finalized transcript turn restored during session resume."""

    role: str
    text: str
    turn_id: str = ""
    question_id: Optional[str] = None
    timestamp: Optional[str] = None
    is_final: bool = True

    @classmethod
    def from_dict(
        cls,
        data: Any,
        valid_question_ids: set[str],
    ) -> Optional["ResumeTranscriptTurn"]:
        """Parse a resume transcript turn from metadata payload."""
        if not isinstance(data, dict):
            return None

        role = data.get("role")
        text = data.get("text")
        is_final = data.get("is_final", data.get("isFinal", False))

        if role not in {"user", "assistant"}:
            return None
        if not isinstance(text, str) or not text.strip():
            return None
        if not bool(is_final):
            return None

        question_id = data.get("question_id", data.get("questionId"))
        if question_id is not None:
            if not isinstance(question_id, str):
                return None
            if question_id not in valid_question_ids:
                return None

        turn_id = data.get("turn_id", data.get("turnId", ""))
        if not isinstance(turn_id, str):
            turn_id = ""

        timestamp = data.get("timestamp")
        if not isinstance(timestamp, str):
            timestamp = None

        return cls(
            role=role,
            text=text.strip(),
            turn_id=turn_id,
            question_id=question_id,
            timestamp=timestamp,
            is_final=True,
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

    # Interview mode: mock, practice, or diagnostic
    mode: InterviewMode = InterviewMode.PRACTICE

    # Language preference for practice sessions (not used in mock interviews)
    comfortable_language: Optional[str] = None

    # Questions list from frontend
    questions: List[Question] = field(default_factory=list)

    # Session state (runtime tracking)
    questions_discussed: List[str] = field(default_factory=list)
    current_question_id: Optional[str] = None
    topics_discussed: List[str] = field(default_factory=list)
    is_resumed: bool = False
    resume_transcript_turns: List[ResumeTranscriptTurn] = field(default_factory=list)
    resume_rejected_reason: Optional[str] = None

    # Job context
    job_ctx: Optional[Any] = None

    # Whether UI feedback is shown to user (diagnostic mode)
    is_feedback_enabled: bool = True

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
        if self.questions_discussed is None:
            self.questions_discussed = []
        if self.resume_transcript_turns is None:
            self.resume_transcript_turns = []

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

    def get_current_question(self) -> Optional[Question]:
        """Get the currently active question."""
        if self.current_question_id:
            return self.get_question_by_id(self.current_question_id)
        return None

    @classmethod
    def _parse_mode(cls, nested_context: Dict[str, Any]) -> InterviewMode:
        """
        Parse interview mode from metadata.
        """
        mode_str = nested_context.get("mode")
        if mode_str:
            try:
                return InterviewMode(mode_str.lower())
            except ValueError:
                pass

        # Default to practice mode
        return InterviewMode.PRACTICE

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
        valid_question_ids = {q.identifier for q in questions if q.identifier}

        resume_state_raw = nested_context.get("resume_state", nested_context.get("resumeState"))
        resume_state_provided = resume_state_raw is not None
        resume_state = resume_state_raw if isinstance(resume_state_raw, dict) else {}
        had_schema_issues = resume_state_provided and not isinstance(resume_state_raw, dict)
        had_question_mismatch = False

        raw_discussed = resume_state.get("questions_discussed", resume_state.get("questionsDiscussed", []))
        questions_discussed: List[str] = []
        if isinstance(raw_discussed, list):
            for identifier in raw_discussed:
                if not isinstance(identifier, str):
                    had_schema_issues = True
                    continue
                if identifier not in valid_question_ids:
                    had_question_mismatch = True
                    continue
                if identifier in questions_discussed:
                    continue
                questions_discussed.append(identifier)
        elif raw_discussed is not None:
            had_schema_issues = True

        current_question_id = resume_state.get("current_question_id", resume_state.get("currentQuestionId"))
        if not isinstance(current_question_id, str):
            if current_question_id is not None:
                had_schema_issues = True
            current_question_id = None
        if current_question_id and current_question_id not in valid_question_ids:
            had_question_mismatch = True
            current_question_id = None
        if current_question_id and current_question_id in questions_discussed:
            current_question_id = None

        raw_turns = resume_state.get("transcript_turns", resume_state.get("transcriptTurns", []))
        resume_transcript_turns: List[ResumeTranscriptTurn] = []
        if isinstance(raw_turns, list):
            for raw_turn in raw_turns:
                if not isinstance(raw_turn, dict):
                    had_schema_issues = True
                    continue
                raw_question_id = raw_turn.get("question_id", raw_turn.get("questionId"))
                if raw_question_id is not None and not isinstance(raw_question_id, str):
                    had_schema_issues = True
                    continue
                if isinstance(raw_question_id, str) and raw_question_id not in valid_question_ids:
                    had_question_mismatch = True
                    continue
                parsed_turn = ResumeTranscriptTurn.from_dict(
                    data=raw_turn,
                    valid_question_ids=valid_question_ids,
                )
                if parsed_turn:
                    resume_transcript_turns.append(parsed_turn)
                else:
                    had_schema_issues = True
        elif raw_turns is not None:
            had_schema_issues = True

        is_resumed = bool(
            questions_discussed or current_question_id or resume_transcript_turns
        )
        resume_rejected_reason: Optional[str] = None
        if resume_state_provided and not is_resumed:
            if had_schema_issues:
                resume_rejected_reason = "invalid_schema"
            elif had_question_mismatch:
                resume_rejected_reason = "question_mismatch"

        # Parse is_feedback_enabled (default True, supports both snake_case and camelCase)
        is_feedback_enabled = nested_context.get("is_feedback_enabled")
        if is_feedback_enabled is None:
            is_feedback_enabled = nested_context.get("isFeedbackEnabled", True)

        return cls(
            agent_type="interview_agent",
            student_name=nested_context.get("student_name") or nested_context.get("studentName"),
            email=nested_context.get("email"),
            gender_preference=nested_context.get("gender_preference") or nested_context.get("genderPreference"),
            prompt=nested_context.get("prompt"),
            mode=cls._parse_mode(nested_context),
            comfortable_language=nested_context.get("comfortable_language") or nested_context.get("comfortableLanguage"),
            questions=questions,
            questions_discussed=questions_discussed,
            current_question_id=current_question_id,
            is_resumed=is_resumed,
            resume_transcript_turns=resume_transcript_turns,
            resume_rejected_reason=resume_rejected_reason,
            is_feedback_enabled=is_feedback_enabled,
        )
