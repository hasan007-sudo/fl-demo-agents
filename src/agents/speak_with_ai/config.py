"""SpeakWithAI agent configuration for multi-agent system."""

from core.session.checkpoints import SessionTimingConfig, Checkpoint

# Total session duration
MAX_SESSION_DURATION = 600  # 10 minutes total

# Conversation duration (8 minutes)
CONVERSATION_DURATION = 480  # 8 minutes

# Feedback duration (2 minutes)
FEEDBACK_DURATION = 120  # 2 minutes

CONVERSATION_TIMING_CONFIG = SessionTimingConfig(
    max_duration=CONVERSATION_DURATION,
    checkpoints=[
        Checkpoint(
            time=360,  # 6 minutes - gentle reminder
            frontend_event=True,
            ai_instruction=(
                "You've been conversing for 6 minutes. "
                "You have about 2 more minutes for the conversation phase. "
                "If there are remaining questions you haven't explored, "
                "consider naturally transitioning to one of them."
            ),
            is_final=False
        ),
        Checkpoint(
            time=420,  # 7 minutes - wrap-up warning
            frontend_event=True,
            ai_instruction=(
                "You've been conversing for 7 minutes. "
                "Start wrapping up the current topic naturally. "
                "In about 1 minute, you'll need to transfer to feedback."
            ),
            is_final=False
        ),
        Checkpoint(
            time=480,  # 8 minutes - trigger handoff
            frontend_event=True,
            ai_instruction=(
                "The conversation phase is now complete. "
                "Wait for the user to finish their current statement if they are speaking. "
                "Then IMMEDIATELY call the transfer_to_feedback() function. "
                "Do NOT say goodbye or start new topics - just call the tool."
            ),
            is_final=True
        ),
    ]
)

FEEDBACK_TIMING_CONFIG = SessionTimingConfig(
    max_duration=FEEDBACK_DURATION,
    checkpoints=[]  # No intermediate checkpoints for feedback
)
