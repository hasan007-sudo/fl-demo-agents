"""Interview agent configuration."""

from livekit.plugins import deepgram
from typing import Dict, Any, Optional
from livekit.plugins import silero, openai, sarvam
from livekit.plugins.turn_detector.multilingual import MultilingualModel
from core.session.checkpoints import SessionTimingConfig, Checkpoint
from .context import InterviewMode

# =============================================================================
# SESSION TIMING CONFIGURATIONS
# =============================================================================

# Practice session: 5 minutes total
PRACTICE_TIMING_CONFIG = SessionTimingConfig(
    max_duration=300,  # 5 minutes
    checkpoints=[
        Checkpoint(
            time=180,  # 3 minutes
            frontend_event=True,
            ai_instruction=(
                "3 minutes elapsed. You have 2 minutes remaining in this practice session. "
                "Continue naturally but be mindful of time."
            ),
            is_final=False
        ),
        Checkpoint(
            time=270,  # 4.5 minutes
            frontend_event=True,
            ai_instruction=(
                "30 seconds remaining. Wrap up the current discussion and "
                "prepare to end the session."
            ),
            is_final=False
        ),
        Checkpoint(
            time=300,  # 5 minutes - session end
            frontend_event=True,
            ai_instruction=None,
            is_final=True
        ),
    ]
)

# Mock interview: 10 minutes total
MOCK_INTERVIEW_TIMING_CONFIG = SessionTimingConfig(
    max_duration=600,  # 10 minutes
    checkpoints=[
        Checkpoint(
            time=300,  # 5 minutes
            frontend_event=True,
            ai_instruction=(
                "You are halfway through the interview (5 minutes elapsed). "
                "Ensure you're making good progress through the key questions."
            ),
            is_final=False
        ),
        Checkpoint(
            time=480,  # 8 minutes
            frontend_event=True,
            ai_instruction=(
                "Only 2 minutes remaining. Begin wrapping up the current topic "
                "and prepare to conclude the interview professionally."
            ),
            is_final=False
        ),
        Checkpoint(
            time=540,  # 9 minutes
            frontend_event=True,
            ai_instruction=(
                "1 minute remaining. Conclude your current question and "
                "prepare your closing remarks."
            ),
            is_final=False
        ),
        Checkpoint(
            time=600,  # 10 minutes - session end
            frontend_event=True,
            ai_instruction=None,
            is_final=True
        ),
    ]
)

# Diagnostic mode: 5 minutes per activity (same as practice for now)
DIAGNOSTIC_TIMING_CONFIG = SessionTimingConfig(
    max_duration=300,  # 5 minutes
    checkpoints=[
        Checkpoint(
            time=270,  # 4.5 minutes
            frontend_event=True,
            ai_instruction=(
                "30 seconds remaining. Let's wrap up this activity."
            ),
            is_final=False
        ),
        Checkpoint(
            time=300,  # 5 minutes - session end
            frontend_event=True,
            ai_instruction=None,
            is_final=True
        ),
    ]
)


def get_timing_config(mode: InterviewMode = InterviewMode.PRACTICE) -> SessionTimingConfig:
    """
    Get the timing configuration based on interview mode.

    Args:
        mode: InterviewMode enum

    Returns:
        SessionTimingConfig for the session type
    """
    if mode == InterviewMode.MOCK:
        return MOCK_INTERVIEW_TIMING_CONFIG
    elif mode == InterviewMode.DIAGNOSTIC:
        return DIAGNOSTIC_TIMING_CONFIG
    else:
        return PRACTICE_TIMING_CONFIG


def get_model_config(
    voice: Optional[str] = None,
    mode: InterviewMode = InterviewMode.PRACTICE
) -> Dict[str, Any]:
    """
    Get model configuration for Interview agent.

    Args:
        voice: Optional voice override for TTS
        mode: Interview mode (affects turn detection settings)

    Returns:
        Dictionary of model configuration
    """
    config: Dict[str, Any] = {
        "llm": openai.LLM(model="gpt-4o-mini"),
        # "stt": sarvam.STT(
        #     language="en-IN",
        #     model="saarika:v2.5",
        #     high_vad_sensitivity=True,  # Faster silence detection (0.5s vs 1s)
        # ),
        "stt": deepgram.STTv2(
            model="flux-general-en",
            eager_eot_threshold=0.4,
        ),
        "tts": sarvam.TTS(
            target_language_code="en-IN",
            speaker=voice or "manisha",
            model="bulbul:v2",
            pace=0.9,
        ),
    }

    # For diagnostic mode (push-to-talk), don't add VAD or turn_detection
    # The session handles turn detection manually via RPC
    if mode != InterviewMode.DIAGNOSTIC:
        config["vad"] = silero.VAD.load()  # Keep for speech detection
        config["turn_detection"] = MultilingualModel()  # LM-based turn detection

    return config
