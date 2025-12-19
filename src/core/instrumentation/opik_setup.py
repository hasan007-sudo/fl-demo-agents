"""Opik observability setup using OpenTelemetry.

Opik by Comet ML provides LLM tracing and evaluation with:
- 7-14x faster performance than alternatives
- Unlimited team members on free tier
- 60-day data retention
- Official LiveKit integration

Docs: https://www.comet.com/docs/opik/integrations/livekit
"""

from agents.interview_preparer.context import InterviewContext
from agents.english_tutor.context import EnglishTutorContext
from livekit.agents.job import JobContext
import os
import logging
from typing import Dict, Any
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from livekit.agents.telemetry import set_tracer_provider

logger = logging.getLogger(__name__)

_tracer_provider: TracerProvider | None = None


def setup_opik(metadata: Dict[str, Any] | None = None) -> bool:
    """
    Configure Opik tracing via OpenTelemetry. Call once at startup.

    Args:
        metadata: Optional dict with trace attributes for session grouping

    Required env vars: OPIK_API_KEY
    Optional:
        - OPIK_WORKSPACE (default: "default")
        - OPIK_HOST (default: "https://www.comet.com")
        - OPIK_PROJECT_NAME (for organizing traces)

    For self-hosted: Set OPIK_HOST to your instance URL (e.g., http://localhost:5173)
    """
    global _tracer_provider

    api_key = os.getenv("OPIK_API_KEY")
    workspace = os.getenv("OPIK_WORKSPACE", "default")
    host = os.getenv("OPIK_HOST", "https://www.comet.com")
    project_name = os.getenv("OPIK_PROJECT_NAME", "livekit-agents")

    # Check if self-hosted (no API key needed for local)
    is_self_hosted = "localhost" in host or "127.0.0.1" in host

    if not api_key and not is_self_hosted:
        logger.warning("OPIK_API_KEY not found - tracing disabled. Get your key at https://www.comet.com")
        return False

    # Setup OTEL exporter with Opik endpoint
    if is_self_hosted:
        # Self-hosted: No auth needed
        otel_endpoint = f"{host}/api/v1/private/otel"
        otel_headers = ""
        logger.info(f"Configuring Opik for self-hosted instance: {host}")
    else:
        # Opik Cloud: Use API key auth
        otel_endpoint = f"{host}/opik/api/v1/private/otel"
        otel_headers = f"Authorization={api_key},Comet-Workspace={workspace}"
        logger.info(f"Configuring Opik Cloud (workspace: {workspace})")

    os.environ["OTEL_EXPORTER_OTLP_ENDPOINT"] = otel_endpoint
    if otel_headers:
        os.environ["OTEL_EXPORTER_OTLP_HEADERS"] = otel_headers

    # Add project name to metadata for trace organization
    if metadata is None:
        metadata = {}
    metadata["opik.project_name"] = project_name

    _tracer_provider = TracerProvider()
    _tracer_provider.add_span_processor(BatchSpanProcessor(OTLPSpanExporter()))

    # Pass metadata to LiveKit's tracer provider for session grouping
    set_tracer_provider(_tracer_provider, metadata=metadata)

    session_id = metadata.get("opik.session.id") if metadata else None
    logger.info(f"Opik tracing enabled (project: {project_name}, session: {session_id})")
    return True


def flush_traces():
    """Flush pending traces on shutdown."""
    if _tracer_provider:
        _tracer_provider.force_flush()
        logger.info("Opik traces flushed")


def setup_opik_for_session(
    ctx: JobContext,
    context: EnglishTutorContext | InterviewContext
) -> None:
    """
    Extract user information from context and setup Opik tracing.

    This creates a trace with:
    - Session grouping by user email/name
    - Agent type labeling
    - User identification for analytics

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

    # Build Opik metadata for session grouping and trace naming
    user_identifier = user_email or user_name or ctx.room.name
    session_identifier = "-".join(filter(None, [trace_prefix, user_email or None, user_name or None]))

    # Opik uses thread_id for conversation grouping
    opik_metadata = {
        "opik.session.id": session_identifier,
        "opik.trace.name": session_identifier,
        "opik.user.id": user_identifier,
        "opik.thread_id": ctx.room.name,  # Group by room for conversation threads
        "opik.tags": f"agent_type:{agent_type}",
    }

    logger.info(
        f"Setting up Opik for {agent_type}: "
        f"session_identifier={session_identifier}"
    )

    # Setup Opik tracing
    if setup_opik(metadata=opik_metadata):
        ctx.add_shutdown_callback(flush_traces)
        logger.info("Opik tracing configured successfully")
    else:
        logger.warning("Opik tracing not configured - check OPIK_API_KEY")
