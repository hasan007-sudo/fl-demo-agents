"""Session creation for Interview agent."""

import logging
import os
from livekit import rtc
from livekit.agents import (
    JobContext,
    AgentSession,
    RoomInputOptions,
    RoomIO,
    MetricsCollectedEvent,
    metrics,
)
from livekit.plugins import noise_cancellation
from livekit.plugins import simli
from .agent import InterviewAgent
from .context import InterviewAgentContext, InterviewMode
from .prompt_builder import InterviewPromptBuilder
from .config import get_model_config

logger = logging.getLogger("agent")

ENABLE_EVALUATION = os.getenv("ENABLE_DEEPEVAL", "true").lower() == "true"
SIMLI_API_KEY = os.getenv("SIMLI_API_KEY")
SIMLI_FACE_ID = os.getenv("SIMLI_FACE_ID")


async def create_session(ctx: JobContext, context: InterviewAgentContext):
    """Create and start an Interview agent session."""
    logger.info("Creating Interview agent session")

    prompt_builder = InterviewPromptBuilder()
    instructions = prompt_builder.build(context)

    # Get model config - diagnostic mode skips VAD for push-to-talk
    model_config = get_model_config(mode=context.mode)

    # Prewarm TTS connection for diagnostic mode (push-to-talk)
    # This prevents WebSocket timeout issues when TTS isn't used immediately
    if context.mode == InterviewMode.DIAGNOSTIC and "tts" in model_config:
        model_config["tts"].prewarm()
        logger.info("TTS connection prewarmed for diagnostic mode")

    agent = InterviewAgent(
        context=context,
        prompt_builder=prompt_builder,
        **model_config,
    )

    context.job_ctx = ctx

    logger.info(f"Session context initialized: {context.summarize()}")

    # Use manual turn detection for diagnostic mode (push-to-talk)
    is_diagnostic = context.mode == InterviewMode.DIAGNOSTIC
    logger.info(f"Interview mode: {context.mode.value}, is_diagnostic={is_diagnostic}")

    session_kwargs = {
        "userdata": context,
        "resume_false_interruption": True,
        "min_interruption_duration": 0.5,
        "user_away_timeout": 30.0,
        "use_tts_aligned_transcript": True,
    }

    if is_diagnostic:
        session_kwargs["turn_detection"] = "manual"
        logger.info("Diagnostic mode: Using manual turn detection (push-to-talk)")

    session = AgentSession[InterviewAgentContext](**session_kwargs)

    # Add performance logging for diagnostic mode
    if is_diagnostic:
        import time

        @session.on("user_speech_committed")
        def _on_user_speech_committed(msg):
            logger.info(f"[PERF] User speech committed, starting LLM generation...")

        @session.on("agent_started_speaking")
        def _on_agent_started_speaking():
            logger.info(f"[PERF] Agent started speaking (TTS synthesis complete)")

        @session.on("agent_stopped_speaking")
        def _on_agent_stopped_speaking():
            logger.info(f"[PERF] Agent stopped speaking")

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
                    "mode": context.mode.value,
                    "questions": [
                        {"identifier": q.identifier, "text": q.text, "hint": q.hint}
                        for q in context.questions
                    ],
                    "questions_discussed": context.questions_discussed,
                    "topics_discussed": context.topics_discussed,
                    "metadata": {
                        "mode": context.mode.value,
                        "comfortable_language": context.comfortable_language,
                    },
                }

                evaluator = InterviewAgentEvaluator(
                    model=os.getenv("DEEPEVAL_MODEL", "gpt-4o-mini"),
                    verbose=True,
                )

                eval_result = evaluator.evaluate_session(
                    chat_items=chat_items,
                    session_id=ctx.room.name,
                    context_data=context_data,
                )

                if eval_result is None:
                    logger.warning("Evaluation skipped: no conversation turns found")
                    return

                result, transcript, test_case = eval_result

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

    # Create and start Simli avatar session if configured
    avatar = None
    if SIMLI_API_KEY and SIMLI_FACE_ID:
        logger.info(f"Creating Simli avatar session with face: {SIMLI_FACE_ID}")
        avatar = simli.AvatarSession(
            simli_config=simli.SimliConfig(
                api_key=SIMLI_API_KEY,
                face_id=SIMLI_FACE_ID,
            ),
        )
        await avatar.start(session, room=ctx.room)
        logger.info("Simli avatar session started")
    else:
        logger.info("Simli avatar not configured, skipping avatar integration")

    logger.info("Starting session with InterviewAgent")

    # For diagnostic mode (push-to-talk), use RoomIO instead of passing room to session.start()
    if is_diagnostic:
        # Set up RoomIO for push-to-talk - this handles room connection
        room_io = RoomIO(session, room=ctx.room)
        await room_io.start()
        logger.info("RoomIO started for diagnostic push-to-talk mode")

        # Connect to room BEFORE session.start() so on_enter() can publish events
        await ctx.connect()
        logger.info("Connected to room")

        # Start session WITHOUT room parameter - RoomIO handles it
        await session.start(agent=agent)

        # Disable audio input IMMEDIATELY after session starts
        # This prevents any audio from being processed before PTT is activated
        session.input.set_audio_enabled(False)
        logger.info("Audio input disabled immediately for push-to-talk")

        # Register RPC methods for push-to-talk control (after connect)
        @ctx.room.local_participant.register_rpc_method("start_turn")
        async def start_turn(data: rtc.RpcInvocationData):
            """Called when user starts recording."""
            logger.info(f"start_turn RPC called by {data.caller_identity}")
            session.interrupt()
            session.clear_user_turn()
            room_io.set_participant(data.caller_identity)
            session.input.set_audio_enabled(True)
            return "ok"

        @ctx.room.local_participant.register_rpc_method("end_turn")
        async def end_turn(data: rtc.RpcInvocationData):
            """Called when user stops recording."""
            import time
            logger.info(f"end_turn RPC called by {data.caller_identity}")
            start_time = time.time()

            session.input.set_audio_enabled(False)
            logger.info(f"[PERF] Audio disabled at {time.time() - start_time:.3f}s")

            session.commit_user_turn(
                transcript_timeout=3.0,
                stt_flush_duration=0.5,
            )
            logger.info(f"[PERF] User turn committed at {time.time() - start_time:.3f}s")
            return "ok"

        @ctx.room.local_participant.register_rpc_method("cancel_turn")
        async def cancel_turn(data: rtc.RpcInvocationData):
            """Called when user cancels recording."""
            logger.info(f"cancel_turn RPC called by {data.caller_identity}")
            session.input.set_audio_enabled(False)
            session.clear_user_turn()
            return "ok"

        logger.info("Push-to-talk RPC methods registered")
    else:
        # Non-diagnostic modes: normal session start with room
        await session.start(
            agent=agent,
            room=ctx.room,
            room_input_options=RoomInputOptions(
                noise_cancellation=noise_cancellation.BVC(),
            ),
        )
        await ctx.connect()

    logger.info("Interview agent session started successfully")
