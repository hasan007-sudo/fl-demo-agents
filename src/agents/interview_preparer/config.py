"""Interview Preparer agent configuration."""

from core.session.checkpoints import SessionTimingConfig, Checkpoint

MAX_SESSION_DURATION = 900  # 15 minutes

TIMING_CONFIG = SessionTimingConfig(
    max_duration=MAX_SESSION_DURATION,
    checkpoints=[
        Checkpoint(
            time=810,  # 13.5 minutes
            frontend_event=True,
            ai_instruction=(
                "You've been conducting the interview for 13.5 minutes now. "
                "Start thinking about wrapping up in the next 90 seconds, "
                "but don't mention time or ending to the candidate yet."
            ),
            is_final=False
        ),
        Checkpoint(
            time=900,  # 15 minutes - HARD CUTOFF
            frontend_event=True,
            ai_instruction=None,
            is_final=True
        )
    ]
)

GOODBYE_INSTRUCTION = (
    "Provide a brief, warm closing with feedback for the candidate. "
    "Do NOT mention that time is up or the interview is ending. "
    "Give one sentence of constructive feedback about their performance, "
    "then thank them and wish them well. "
    "Keep it under 20 seconds."
)
