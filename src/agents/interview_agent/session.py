"""Session creation for Interview agent."""

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
from .agent import InterviewAgent
from .context import InterviewAgentContext
from .prompt_builder import InterviewPromptBuilder
from .config import get_model_config

logger = logging.getLogger("agent")

ENABLE_EVALUATION = os.getenv("ENABLE_DEEPEVAL", "true").lower() == "true"


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
        user_away_timeout=30.0,
        use_tts_aligned_transcript=True,
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
                from .evaluation import InterviewAgentEvaluator
                from core.evaluation.reporters import ConsolePrinter

                logger.info("Running post-session DeepEval evaluation...")

                chat_items = session._chat_ctx._items if hasattr(session, '_chat_ctx') else []
                if not chat_items:
                    logger.warning("No chat history found for evaluation")
                    return

                context_data = {
                    "student_name": context.student_name,
                    "email": context.email,
                    "mock_interview": context.mock_interview,
                    "questions": [
                        {"identifier": q.identifier, "text": q.text, "hint": q.hint}
                        for q in context.questions
                    ],
                    "questions_discussed": context.questions_discussed,
                    "topics_discussed": context.topics_discussed,
                    "metadata": {
                        "mock_interview": context.mock_interview,
                        "comfortable_language": context.comfortable_language,
                    },
                }

                evaluator = InterviewAgentEvaluator(
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
                    dataset_alias = os.getenv(
                        "DEEPEVAL_DATASET_ALIAS",
                        "interview-agent-sessions"
                    )
                    evaluator.save_to_dataset(
                        transcript=transcript,
                        test_case=test_case,
                        dataset_alias=dataset_alias,
                    )

            except Exception as e:
                logger.error(f"DeepEval evaluation failed: {e}", exc_info=True)

        ctx.add_shutdown_callback(run_evaluation)

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
