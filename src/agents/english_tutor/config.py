"""English Tutor agent configuration."""

from core.session.checkpoints import SessionTimingConfig, Checkpoint

MAX_SESSION_DURATION = 300  # 5 minutes

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
