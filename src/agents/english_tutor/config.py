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
FEEDBACK_PROVIDER_DURATION = 60  # 1 minute


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
            ),
            is_final=False
        ),
        Checkpoint(
            time=240,  # 4 minutes - trigger handoff
            frontend_event=True,
            ai_instruction=(
                "Time to transition to feedback. "
                "Use the transfer_to_feedback() tool now to hand off "
                "to the Feedback Provider."
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
    checkpoints=[
        Checkpoint(
            time=50,  # 50 seconds - wrap up warning
            frontend_event=True,
            ai_instruction=(
                "You have 10 seconds remaining. "
                "Begin your English closing statement now if you haven't already."
            ),
            is_final=False
        ),
        Checkpoint(
            time=60,  # 1 minute - end session
            frontend_event=True,
            ai_instruction=(
                "Session ending now. Call finalize_session() immediately."
            ),
            is_final=True
        ),
    ]
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

GOODBYE_INSTRUCTION = (
    "Provide a brief, warm closing with feedback for the student "
    "as given in your system prompt. "
    "Do NOT mention that time is up or that the session is ending. "
    "Keep it under 20 seconds."
)


# =============================================================================
# GOODBYE INSTRUCTIONS (per agent)
# =============================================================================

CONVERSATION_GOODBYE = "Transition smoothly to feedback phase using transfer_to_feedback() tool."

FEEDBACK_GOODBYE = (
    "Provide final closing statement as per your system prompt, "
    "then call finalize_session(). Keep it under 20 seconds."
)
