"""Main entry point with agent routing based on agentType."""

from livekit.agents.worker import AgentServer
from asyncio.tasks import sleep
import logging
import json
from pathlib import Path

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
from livekit.plugins.google.realtime import RealtimeModel as GoogleRealtimeModel

try:
    from .core.agents.registry import registry
    from .core.agents.factory import AgentFactory
    from .core.session.voice_manager import VoiceManager
    from .core.instrumentation.langfuse_setup import setup_langfuse_for_session
    from .agents.english_tutor import EnglishTutorContext, create_session as create_english_tutor_session
    from .agents.speak_with_ai import SpeakWithAIContext, create_session as create_speak_with_ai_session
    from .agents.interview_agent import InterviewAgentContext, create_session as create_interview_agent_session
    from .agents.interview_preparer.agent import InterviewPreparerAgent
    from .agents.interview_preparer.context import InterviewContext
except ImportError:
    from core.agents.registry import registry
    from core.agents.factory import AgentFactory
    from core.session.voice_manager import VoiceManager
    from core.instrumentation.langfuse_setup import setup_langfuse_for_session
    from agents.english_tutor import EnglishTutorContext, create_session as create_english_tutor_session
    from agents.speak_with_ai import SpeakWithAIContext, create_session as create_speak_with_ai_session
    from agents.interview_agent import InterviewAgentContext, create_session as create_interview_agent_session
    from agents.interview_preparer.agent import InterviewPreparerAgent
    from agents.interview_preparer.context import InterviewContext

logger = logging.getLogger("agent")

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
else:
    load_dotenv()


def register_agents():
    if "interview_preparer" not in registry:
        registry.register(name="interview_preparer", agent_class=InterviewPreparerAgent)
    logger.info(f"Registered {len(registry)} agents: {registry.list_agents()}")


def prewarm(proc: JobProcess):
    proc.userdata["vad"] = silero.VAD.load()
    register_agents()


async def entrypoint(ctx: JobContext):
    ctx.log_context_fields = {"room": ctx.room.name}
    metadata_str = ctx.job.room.metadata
    try:
        metadata = json.loads(metadata_str) if metadata_str else {}
    except json.JSONDecodeError as e:
        logger.error(f"Failed to parse room metadata: {e}")
        metadata = {}

    agent_type = metadata.get("agent_type", "speak_with_ai")
    logger.info(f"Starting session with agent type: {agent_type}")

    if agent_type == "english_tutor":
        context = EnglishTutorContext.from_metadata(metadata)
        setup_langfuse_for_session(ctx, context)
        await create_english_tutor_session(ctx, context)

    elif agent_type == "speak_with_ai":
        context = SpeakWithAIContext.from_metadata(metadata)
        setup_langfuse_for_session(ctx, context)
        await create_speak_with_ai_session(ctx, context)

    elif agent_type == "interview_agent":
        context = InterviewAgentContext.from_metadata(metadata)
        setup_langfuse_for_session(ctx, context)
        await create_interview_agent_session(ctx, context)

    else:
        # Interview preparer
        context = InterviewContext.from_metadata(metadata)
        setup_langfuse_for_session(ctx, context)

        selected_voice = VoiceManager.get_voice_for_agent(agent_type, context, provider="google")
        realtime_model = GoogleRealtimeModel(
            model="gemini-2.5-flash-native-audio-preview-09-2025",
            voice=selected_voice,
            temperature=0.8
        )

        session = AgentSession(
            llm=realtime_model,
            resume_false_interruption=True,
            min_interruption_duration=0.5,
            user_away_timeout=30.0
        )

        usage_collector = metrics.UsageCollector()

        @session.on("metrics_collected")
        def _on_metrics_collected(ev: MetricsCollectedEvent):
            metrics.log_metrics(ev.metrics)
            usage_collector.collect(ev.metrics)

        async def log_usage():
            summary = usage_collector.get_summary()
            logger.info(f"Usage: {summary}")

        ctx.add_shutdown_callback(log_usage)

        factory = AgentFactory()
        agent = factory.create(agent_type, context=context)
        if not agent:
            raise ValueError(f"Unable to create agent of type: {agent_type}")

        await session.start(
            agent=agent,
            room=ctx.room,
            room_input_options=RoomInputOptions(noise_cancellation=noise_cancellation.BVC()),
        )
        await ctx.connect()
        logger.info(f"{agent_type} agent session started successfully")


if __name__ == "__main__":
    register_agents()
    cli.run_app(WorkerOptions(entrypoint_fnc=entrypoint, prewarm_fnc=prewarm, shutdown_process_timeout=100))
