"""Multi-agent session creation for English Tutor."""

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

from .agents import (
    ConversationPartnerAgent,
    FeedbackProviderAgent,
    get_agent_model_config,
)
from .context import EnglishTutorContext
from .prompt_builder import EnglishTutorPromptBuilder

logger = logging.getLogger("agent")


async def create_session(ctx: JobContext, context: EnglishTutorContext):
    """Create and start a multi-agent English Tutor session."""
    logger.info("Creating multi-agent English Tutor session")

    selected_voice = VoiceManager.get_voice_for_agent("english_tutor", context, provider="google")
    logger.info(f"Selected voice: {selected_voice}")

    prompt_builder = EnglishTutorPromptBuilder()
    conversation_instructions = prompt_builder.build_for_agent("conversation_partner", context)
    feedback_instructions = prompt_builder.build_for_agent("feedback_provider", context)

    conversation_config = get_agent_model_config("conversation_partner", selected_voice)
    feedback_config = get_agent_model_config("feedback_provider", selected_voice)

    conversation_agent = ConversationPartnerAgent(
        instructions=conversation_instructions,
        **conversation_config,
        context=context,
    )

    feedback_agent = FeedbackProviderAgent(
        instructions=feedback_instructions,
        **feedback_config,
        context=context,
    )

    context.conversation_agent = conversation_agent
    context.feedback_agent = feedback_agent
    context.job_ctx = ctx

    logger.info(f"Session context initialized: {context.summarize()}")

    session = AgentSession[EnglishTutorContext](
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

    logger.info("Starting session with ConversationPartnerAgent")
    await session.start(
        agent=conversation_agent,
        room=ctx.room,
        room_input_options=RoomInputOptions(
            noise_cancellation=noise_cancellation.BVC(),
        ),
    )

    await ctx.connect()
    logger.info("Multi-agent English Tutor session started successfully")
