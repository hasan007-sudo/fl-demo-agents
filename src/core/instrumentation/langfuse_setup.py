"""Langfuse observability setup using OpenTelemetry."""

from agents.interview_preparer.context import InterviewContext
from agents.english_tutor.context import EnglishTutorContext
from livekit.agents.job import JobContext
import os
import base64
import logging
from typing import Dict, Any
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from livekit.agents.telemetry import set_tracer_provider

logger = logging.getLogger(__name__)

_tracer_provider: TracerProvider | None = None


def setup_langfuse(metadata: Dict[str, Any] | None = None) -> bool:
    """
    Configure Langfuse tracing. Call once at startup.

    Args:
        metadata: Optional dict with Langfuse attributes:
            - "langfuse.session.id": Groups traces by session (e.g., room name)
            - "langfuse.trace.name": Names the trace in the UI

    Required env vars: LANGFUSE_PUBLIC_KEY, LANGFUSE_SECRET_KEY
    Optional: LANGFUSE_HOST (default: https://us.cloud.langfuse.com)
    """
    global _tracer_provider

    public_key = os.getenv("LANGFUSE_PUBLIC_KEY")
    secret_key = os.getenv("LANGFUSE_SECRET_KEY")
    host = os.getenv("LANGFUSE_HOST", "https://us.cloud.langfuse.com")

    if not public_key or not secret_key:
        logger.warning("Langfuse credentials not found - tracing disabled")
        return False

    # Setup OTEL exporter with Langfuse auth
    auth = base64.b64encode(f"{public_key}:{secret_key}".encode()).decode()
    os.environ["OTEL_EXPORTER_OTLP_ENDPOINT"] = f"{host}/api/public/otel"
    os.environ["OTEL_EXPORTER_OTLP_HEADERS"] = f"Authorization=Basic {auth}"

    _tracer_provider = TracerProvider()
    _tracer_provider.add_span_processor(BatchSpanProcessor(OTLPSpanExporter()))

    # Pass metadata to LiveKit's tracer provider for session grouping
    set_tracer_provider(_tracer_provider, metadata=metadata)

    session_id = metadata.get("langfuse.session.id") if metadata else None
    logger.info(f"Langfuse tracing enabled (host: {host}, session: {session_id})")
    return True


async def flush_traces():
    """Flush pending traces on shutdown."""
    if _tracer_provider:
        _tracer_provider.force_flush()

def setup_langfuse_for_session(
    ctx: JobContext,
    context: EnglishTutorContext | InterviewContext
) -> None:
    """
    Extract user information from context and setup Langfuse tracing.
    Args:
        ctx: Job context from LiveKit
        context: Either EnglishTutorContext or InterviewContext instance
    """
    if isinstance(context, EnglishTutorContext):
        user_email = context.email
        user_name = context.student_name
        agent_type = "english_tutor"
        trace_prefix = "Eng-Tutor"
    elif isinstance(context, InterviewContext):
        user_email = context.email
        user_name = context.candidate_name
        agent_type = "interview_preparer"
        trace_prefix = "Int-Prep"
    else:
        logger.warning(f"Unknown context type: {type(context)}")
        user_email = None
        user_name = None
        agent_type = "unknown"
        trace_prefix = "Unknown"

    # Build Langfuse metadata for session grouping and trace naming
    user_identifier = user_email or user_name or ctx.room.name
    session_identifier = "-".join(filter(None, [trace_prefix, user_email or None, user_name or None]))

    langfuse_metadata = {
        "langfuse.session.id": session_identifier,
        "langfuse.trace.name": session_identifier,
        "langfuse.user.id": user_identifier,
    }

    logger.info(
        f"Setting up Langfuse for {agent_type}: "
        f"session_identifier={session_identifier}"
    )

    # Setup Langfuse tracing
    if setup_langfuse(metadata=langfuse_metadata):
        ctx.add_shutdown_callback(flush_traces)
        logger.info("Langfuse tracing configured successfully")
    else:
        logger.warning("Langfuse tracing not configured")

