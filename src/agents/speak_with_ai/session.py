"""Multi-agent session creation for SpeakWithAI."""

import logging
import os
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
    ConversationAgent,
    FeedbackAgent,
    get_agent_model_config,
)
from .context import SpeakWithAIContext
from .prompt_builder import SpeakWithAIPromptBuilder

logger = logging.getLogger("agent")

ENABLE_EVALUATION = os.getenv("ENABLE_DEEPEVAL", "true").lower() == "true"


async def create_session(ctx: JobContext, context: SpeakWithAIContext):
    """Create and start a multi-agent SpeakWithAI session."""
    logger.info("Creating multi-agent SpeakWithAI session")

    selected_voice = VoiceManager.get_voice_for_agent("speak_with_ai", context, provider="google")
    logger.info(f"Selected voice: {selected_voice}")

    prompt_builder = SpeakWithAIPromptBuilder()
    conversation_instructions = prompt_builder.build_for_agent("conversation", context)
    feedback_instructions = prompt_builder.build_for_agent("feedback", context)

    conversation_config = get_agent_model_config("conversation", selected_voice)
    feedback_config = get_agent_model_config("feedback", selected_voice)

    conversation_agent = ConversationAgent(
        instructions=conversation_instructions,
        **conversation_config,
        context=context,
    )

    feedback_agent = FeedbackAgent(
        instructions=feedback_instructions,
        **feedback_config,
        context=context,
    )

    context.conversation_agent = conversation_agent
    context.feedback_agent = feedback_agent
    context.job_ctx = ctx

    logger.info(f"Session context initialized: {context.summarize()}")

    session = AgentSession[SpeakWithAIContext](
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

    # Post-session evaluation
    if ENABLE_EVALUATION:
        async def run_evaluation():
            try:
                from .evaluation import SpeakWithAIEvaluator
                from core.evaluation.reporters import ConsolePrinter

                logger.info("Running post-session DeepEval evaluation...")

                chat_items = session._chat_ctx._items if hasattr(session, '_chat_ctx') else []
                if not chat_items:
                    logger.warning("No chat history found for evaluation")
                    return

                context_data = {
                    "student_name": context.student_name,
                    "email": context.email,
                    "questions": [
                        {"identifier": q.identifier, "text": q.text, "hint": q.hint}
                        for q in context.questions
                    ],
                    "questions_discussed": context.questions_discussed,
                    "topics_discussed": context.topics_discussed,
                }

                evaluator = SpeakWithAIEvaluator(
                    model=os.getenv("DEEPEVAL_MODEL", "gpt-4o-mini"),
                    verbose=True,
                )

                result, transcript, test_case = evaluator.evaluate_session(
                    chat_items=chat_items,
                    session_id=ctx.room.name,
                    context_data=context_data,
                )

                logger.info(
                    f"DeepEval evaluation complete: "
                    f"overall={result.overall_score:.2f}, passed={result.passed}"
                )
                ConsolePrinter(use_colors=False).print(result)

                # Push to Confident AI dataset
                if os.getenv("DEEPEVAL_SAVE_DATASET", "true").lower() == "true":
                    evaluator.save_to_dataset(
                        transcript=transcript,
                        test_case=test_case,
                        dataset_alias=os.getenv("DEEPEVAL_DATASET_ALIAS", "speak-with-ai-sessions"),
                    )

            except Exception as e:
                logger.error(f"DeepEval evaluation failed: {e}", exc_info=True)

        ctx.add_shutdown_callback(run_evaluation)

    logger.info("Starting session with SpeakWithAIConversationAgent")
    await session.start(
        agent=conversation_agent,
        room=ctx.room,
        room_input_options=RoomInputOptions(
            noise_cancellation=noise_cancellation.BVC(),
        ),
    )

    await ctx.connect()
    logger.info("Multi-agent SpeakWithAI session started successfully")
