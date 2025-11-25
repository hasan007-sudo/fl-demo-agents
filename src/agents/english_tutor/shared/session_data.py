"""Shared session data for English Tutor multi-agent orchestration."""

from dataclasses import dataclass, field
from typing import Optional, List, Any


@dataclass
class EnglishTutorSessionData:
    """
    Shared data across ConversationPartnerAgent and FeedbackProviderAgent.

    This dataclass stores all session state that needs to be preserved
    during agent handoffs, including user profile, conversation history,
    and agent references.
    """

    # User profile (from context)
    student_name: Optional[str] = None
    proficiency_level: Optional[str] = None
    comfortable_language: Optional[str] = None
    learning_goal: Optional[str] = None

    # Conversation tracking
    topics_discussed: List[str] = field(default_factory=list)
    conversation_start_time: Optional[float] = None

    # Speaking metrics (for future analytics - not used by agents)
    total_words_spoken: int = 0
    user_speaking_duration: float = 0.0  # seconds

    # Agent references for handoff
    conversation_agent: Optional[Any] = None
    feedback_agent: Optional[Any] = None
    previous_agent: Optional[Any] = None

    # Job context
    job_ctx: Optional[Any] = None

    def calculate_wpm(self) -> float:
        """
        Calculate words per minute based on speaking metrics.

        Returns:
            Words per minute, or 0.0 if no speaking duration recorded.
        """
        if self.user_speaking_duration > 0:
            return (self.total_words_spoken / self.user_speaking_duration) * 60
        return 0.0

    def add_topic(self, topic: str) -> None:
        """
        Add a new topic to the list of discussed topics.

        Args:
            topic: Brief description of the topic.
        """
        if topic and topic not in self.topics_discussed:
            self.topics_discussed.append(topic)

    def summarize(self) -> str:
        """
        Generate a summary string for system messages.

        Returns:
            Summary of session state for AI context.
        """
        topics_str = ", ".join(self.topics_discussed[:3]) if self.topics_discussed else "None yet"
        return (
            f"Student: {self.student_name or 'Unknown'}, "
            f"Level: {self.proficiency_level or 'Unknown'}, "
            f"Topics: {topics_str}"
        )
