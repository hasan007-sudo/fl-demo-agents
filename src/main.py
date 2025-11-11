"""
Main entry point with agent routing based on agentType.

This file handles:
1. Parsing room metadata to determine which agent to use
2. Creating the appropriate agent (English Tutor or Interview Preparer)
3. Setting up the session with proper configuration
"""

from livekit.plugins import openai
import logging
import os
import json
from pathlib import Path
from typing import Optional, Dict, Any
from livekit.plugins.google.beta.realtime import RealtimeModel as GoogleRealtimeModel

from dotenv import load_dotenv
from livekit.agents import (
    JobContext,
    JobProcess,
    WorkerOptions,
    AgentSession,
    RoomInputOptions,
    MetricsCollectedEvent,
    cli,
    metrics,
)
from livekit.plugins import noise_cancellation, silero
from openai.types.beta.realtime.session import TurnDetection

# Import core infrastructure
# Use try/except for both direct execution and module execution
try:
    from .core.agents.registry import registry
    from .core.agents.factory import AgentFactory
    from .core.session.voice_manager import VoiceManager
    # from .core.transcripts import TranscriptHandler  # Disabled - LiveKit handles transcripts automatically
    from .agents.english_tutor.agent import EnglishTutorAgent
    from .agents.english_tutor.context import EnglishTutorContext
    from .agents.interview_preparer.agent import InterviewPreparerAgent
    from .agents.interview_preparer.context import InterviewContext
except ImportError:
    from core.agents.registry import registry
    from core.agents.factory import AgentFactory
    from core.session.voice_manager import VoiceManager
    # from core.transcripts import TranscriptHandler  # Disabled - LiveKit handles transcripts automatically
    from agents.english_tutor.agent import EnglishTutorAgent
    from agents.english_tutor.context import EnglishTutorContext
    from agents.interview_preparer.agent import InterviewPreparerAgent
    from agents.interview_preparer.context import InterviewContext

logger = logging.getLogger("agent")

# Load environment variables
env_file = None
for env_name in [".env.local", ".env"]:
    if Path(env_name).exists():
        env_file = env_name
        break
    elif Path(f"../{env_name}").exists():
        env_file = f"../{env_name}"
        break

if env_file:
    load_dotenv(env_file)
    logger.info(f"Loaded environment from {env_file}")
else:
    load_dotenv()


def register_agents():
    """Register all available agents."""
    # Check if already registered to avoid errors on reconnection
    if "english_tutor" not in registry:
        registry.register(
            name="english_tutor",
            agent_class=EnglishTutorAgent,
            is_default=True  # Default to English Tutor for backward compatibility
        )

    if "interview_preparer" not in registry:
        registry.register(
            name="interview_preparer",
            agent_class=InterviewPreparerAgent
        )

    logger.info(f"Registered {len(registry)} agents: {registry.list_agents()}")




def prewarm(proc: JobProcess):
    """Prewarm models for faster startup."""
    proc.userdata["vad"] = silero.VAD.load()
    # Register agents during prewarm
    register_agents()


async def entrypoint(ctx: JobContext):
    """Main entrypoint with agent routing."""
    ctx.log_context_fields = {"room": ctx.room.name}

    # Parse JSON metadata
    metadata_str = ctx.job.room.metadata
    try:
        metadata = json.loads(metadata_str) if metadata_str else {}
    except json.JSONDecodeError as e:
        logger.error(f"Failed to parse room metadata: {e}")
        metadata = {}

    agent_type = metadata.get("agent_type", "english_tutor")
    logger.info(f"Starting session with agent type: {agent_type}")
    logger.info(f"Metadata keys: {list(metadata.keys())}")

    # Create context using agent-specific parser
    if agent_type == "english_tutor":
        context = EnglishTutorContext.from_metadata(metadata)
    else:  # interview_preparer
        context = InterviewContext.from_metadata(metadata)

    logger.info(f"Created context: {context.agent_type}")

    # Select voice based on agent type and metadata
    selected_voice = VoiceManager.get_voice_for_agent(agent_type, context)
    logger.info(f"Selected voice: {selected_voice}")

    # Create agent session with OpenAI Realtime model
    # realtime_model = openai.realtime.RealtimeModel(
    #     # model="gpt-4o-mini-realtime-preview-2024-12-17",
    #     model="gpt-realtime-mini",
    #     voice=selected_voice,
    #     turn_detection=TurnDetection(
    #         type="semantic_vad",
    #         eagerness="low",  # Changed to "relaxed" for better patience with learners
    #         create_response=True,
    #         # interrupt_response=True,
    #     ),
    # )

    realtime_model = GoogleRealtimeModel(
        model="gemini-2.5-flash-native-audio-preview-09-2025",
        voice="Charon",
        temperature=0.8
    )

    logger.info(f"Using Google Gemini Realtime model: {realtime_model.model}")

    session = AgentSession(
        llm=realtime_model,
        resume_false_interruption=True,
        min_interruption_duration=0.5,
        user_away_timeout=30.0
    )

    # Setup metrics collection
    usage_collector = metrics.UsageCollector()

    @session.on("metrics_collected")
    def _on_metrics_collected(ev: MetricsCollectedEvent):
        metrics.log_metrics(ev.metrics)
        usage_collector.collect(ev.metrics)

    async def log_usage():
        summary = usage_collector.get_summary()
        logger.info(f"Usage: {summary}")

    ctx.add_shutdown_callback(log_usage)

    # Create a fresh agent instance for this session
    # This ensures each session gets its own agent with session-specific context
    factory = AgentFactory()
    agent = factory.create(agent_type, context=context)

    if not agent:
        logger.error(f"Failed to create agent: {agent_type}")
        raise ValueError(f"Unable to create agent of type: {agent_type}")

    logger.info(f"Created agent for session: {agent.__class__.__name__}")

    # Start the session with the fresh agent instance
    await session.start(
        agent=agent,
        room=ctx.room,
        room_input_options=RoomInputOptions(
            noise_cancellation=noise_cancellation.BVC(),
        ),
    )

    await ctx.connect()
    logger.info(f"{agent_type} agent session started successfully")


if __name__ == "__main__":
    register_agents()
    options = WorkerOptions(
        entrypoint_fnc=entrypoint,
        prewarm_fnc=prewarm
    )
    cli.run_app(options)