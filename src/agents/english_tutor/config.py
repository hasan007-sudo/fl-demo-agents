"""English Tutor agent configuration for multi-agent system."""

from core.session.checkpoints import SessionTimingConfig, Checkpoint

# =============================================================================
# MULTI-AGENT SESSION TIMING
# =============================================================================

# Total session duration
MAX_SESSION_DURATION = 300  # 5 minutes total

# Conversation Partner duration (4 minutes)
CONVERSATION_PARTNER_DURATION = 240  # 4 minutes

# Feedback Provider duration (1 minute)
FEEDBACK_PROVIDER_DURATION = 30  # 1 minute


# =============================================================================
# CONVERSATION PARTNER TIMING CONFIG
# =============================================================================

CONVERSATION_TIMING_CONFIG = SessionTimingConfig(
    max_duration=CONVERSATION_PARTNER_DURATION,
    checkpoints=[
        Checkpoint(
            time=210,  # 3.5 minutes - gentle reminder
            frontend_event=True,
            ai_instruction=(
                "You've been conversing for 3.5 minutes. "
                "Continue the conversation naturally. "
                "In about 30 seconds, you'll need to transfer to feedback."
                # "In about 5 seconds, you'll need to transfer to feedback."
            ),
            is_final=False
        ),
        Checkpoint(
            time=240,  # 4 minutes - trigger handoff
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


# =============================================================================
# FEEDBACK PROVIDER TIMING CONFIG
# =============================================================================

FEEDBACK_TIMING_CONFIG = SessionTimingConfig(
    max_duration=FEEDBACK_PROVIDER_DURATION,
    checkpoints=[]
)


# =============================================================================
# LEGACY SUPPORT (for backward compatibility)
# =============================================================================

# Keep old TIMING_CONFIG for any legacy code that might reference it
TIMING_CONFIG = SessionTimingConfig(
    max_duration=MAX_SESSION_DURATION,
    checkpoints=[
        Checkpoint(
            time=270,  # 4.5 minutes
            frontend_event=True,
            ai_instruction=(
                "You've been conversing for 4.5 minutes now. "
                "Start thinking about wrapping up the conversation naturally "
                "in the next 30 seconds, but don't mention time or ending "
                "to the student yet."
            ),
            is_final=True
        ),
        Checkpoint(
            time=300,  # 5 minutes - HARD CUTOFF
            frontend_event=True,
            ai_instruction=None,
            is_final=True
        )
    ]
)
