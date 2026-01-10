"""Session creation for Interview agent."""

import logging
from livekit.agents import (
    JobContext,
    AgentSession,
    RoomInputOptions,
    MetricsCollectedEvent,
    metrics,
)
from livekit.plugins import noise_cancellation

try:
    from ...core.session.voice_manager import VoiceManager
except ImportError:
    from core.session.voice_manager import VoiceManager

from .agent import InterviewAgent
from .context import InterviewAgentContext
from .prompt_builder import InterviewPromptBuilder
from .config import get_model_config

logger = logging.getLogger("agent")


async def create_session(ctx: JobContext, context: InterviewAgentContext):
    """Create and start an Interview agent session."""
    logger.info("Creating Interview agent session")

    prompt_builder = InterviewPromptBuilder()
    instructions = prompt_builder.build(context)

    model_config = get_model_config()

    agent = InterviewAgent(
        context=context,
        prompt_builder=prompt_builder,
        **model_config,
    )

    context.job_ctx = ctx

    logger.info(f"Session context initialized: {context.summarize()}")

    session = AgentSession[InterviewAgentContext](
        userdata=context,
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

    logger.info("Starting session with InterviewAgent")
    await session.start(
        agent=agent,
        room=ctx.room,
        room_input_options=RoomInputOptions(
            noise_cancellation=noise_cancellation.BVC(),
        ),
    )

    await ctx.connect()
    logger.info("Interview agent session started successfully")
