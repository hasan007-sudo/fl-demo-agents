"""
Transcript builder for converting session data to DeepEval test cases.
"""

from typing import List, Dict, Any, Optional
from dataclasses import dataclass, field
from deepeval.test_case import ConversationalTestCase, Turn


@dataclass
class SessionTranscript:
    """Session transcript data for evaluation."""

    session_id: str
    agent_type: str = "speak_with_ai"
    student_name: Optional[str] = None
    email: Optional[str] = None
    questions: List[Dict[str, str]] = field(default_factory=list)
    questions_discussed: List[str] = field(default_factory=list)
    topics_discussed: List[str] = field(default_factory=list)
    conversation_turns: List[Dict[str, str]] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)


class TranscriptBuilder:
    """Converts session data to DeepEval ConversationalTestCase."""

    @staticmethod
    def from_chat_history(
        chat_items: List[Any],
        session_id: str,
        agent_type: str = "speak_with_ai",
        context_data: Optional[Dict[str, Any]] = None,
    ) -> SessionTranscript:
        """Build transcript from LiveKit chat context items."""
        context = context_data or {}

        transcript = SessionTranscript(
            session_id=session_id,
            agent_type=agent_type,
            student_name=context.get("student_name"),
            email=context.get("email"),
            questions=context.get("questions", []),
            questions_discussed=context.get("questions_discussed", []),
            topics_discussed=context.get("topics_discussed", []),
            metadata=context.get("metadata", {}),
        )

        # Pair user inputs with assistant responses
        current_user_input = None
        for item in chat_items:
            role = getattr(item, "role", None)
            content = TranscriptBuilder._extract_content(item)

            if not content:
                continue

            if role == "user":
                current_user_input = content
            elif role == "assistant" and current_user_input is not None:
                transcript.conversation_turns.append({
                    "user": current_user_input,
                    "assistant": content,
                })
                current_user_input = None

        return transcript

    @staticmethod
    def build_test_case(
        transcript: SessionTranscript,
        chatbot_role: Optional[str] = None,
    ) -> ConversationalTestCase:
        """Convert transcript to DeepEval ConversationalTestCase."""
        turns = []

        for turn in transcript.conversation_turns:
            user_content = turn.get("user", "")
            assistant_content = turn.get("assistant", "")

            if user_content:
                turns.append(Turn(role="user", content=user_content))
            if assistant_content:
                turns.append(Turn(role="assistant", content=assistant_content))

        return ConversationalTestCase(
            turns=turns,
            chatbot_role=chatbot_role,
            additional_metadata={
                "session_id": transcript.session_id,
                "agent_type": transcript.agent_type,
                "student_name": transcript.student_name,
                "questions": transcript.questions,
                "questions_discussed": transcript.questions_discussed,
                "topics_discussed": transcript.topics_discussed,
            },
        )

    @staticmethod
    def _extract_content(item: Any) -> Optional[str]:
        """Extract text content from a chat item."""
        content = getattr(item, "content", None)

        if content is None:
            return None

        if isinstance(content, str):
            return content

        # Handle multimodal content (list of parts)
        if isinstance(content, list):
            text_parts = []
            for part in content:
                if isinstance(part, str):
                    text_parts.append(part)
                elif hasattr(part, "text"):
                    text_parts.append(part.text)
            return " ".join(text_parts) if text_parts else None

        return str(content) if content else None
