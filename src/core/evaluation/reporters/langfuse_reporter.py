"""
Langfuse reporter for evaluation results.

Pushes evaluation scores to Langfuse as trace annotations/scores.
"""

import os
import logging
from typing import Optional

from langfuse import Langfuse

from core.evaluation.evaluator import EvaluationResult

logger = logging.getLogger(__name__)


class LangfuseReporter:
    """
    Reports evaluation results to Langfuse.

    Pushes metric scores as Langfuse scores attached to traces.
    """

    def __init__(
        self,
        public_key: Optional[str] = None,
        secret_key: Optional[str] = None,
        host: Optional[str] = None,
    ):
        """
        Initialize Langfuse reporter.

        Uses environment variables if credentials not provided:
        - LANGFUSE_PUBLIC_KEY
        - LANGFUSE_SECRET_KEY
        - LANGFUSE_HOST (optional, defaults to cloud)

        Args:
            public_key: Langfuse public key
            secret_key: Langfuse secret key
            host: Langfuse host URL
        """
        self.public_key = public_key or os.getenv("LANGFUSE_PUBLIC_KEY")
        self.secret_key = secret_key or os.getenv("LANGFUSE_SECRET_KEY")
        self.host = host or os.getenv("LANGFUSE_HOST", "https://us.cloud.langfuse.com")

        self._client: Optional[Langfuse] = None

    @property
    def client(self) -> Optional[Langfuse]:
        """Lazy-load Langfuse client."""
        if self._client is None and self.public_key and self.secret_key:
            try:
                self._client = Langfuse(
                    public_key=self.public_key,
                    secret_key=self.secret_key,
                    host=self.host,
                )
                logger.info("Langfuse client initialized for evaluation reporting")
            except Exception as e:
                logger.warning(f"Failed to initialize Langfuse client: {e}")
        return self._client

    def report(
        self,
        result: EvaluationResult,
        trace_id: Optional[str] = None,
    ) -> bool:
        """
        Push evaluation results to Langfuse.

        Args:
            result: EvaluationResult to report
            trace_id: Optional trace ID to attach scores to.
                     Uses session_id if not provided.

        Returns:
            True if successfully reported, False otherwise
        """
        if not self.client:
            logger.warning("Langfuse client not available - skipping report")
            return False

        trace_id = trace_id or result.session_id

        try:
            # Report each metric as a separate score
            for metric_name, metric_data in result.metrics.items():
                self.client.score(
                    trace_id=trace_id,
                    name=f"deepeval_{metric_name.lower()}",
                    value=metric_data.get("score", 0),
                    comment=metric_data.get("reason", ""),
                    data_type="NUMERIC",
                )

            # Report overall score
            self.client.score(
                trace_id=trace_id,
                name="deepeval_overall",
                value=result.overall_score,
                comment=f"Passed: {result.passed}",
                data_type="NUMERIC",
            )

            # Report pass/fail status
            self.client.score(
                trace_id=trace_id,
                name="deepeval_passed",
                value=1.0 if result.passed else 0.0,
                data_type="BOOLEAN",
            )

            # Flush to ensure scores are sent
            self.client.flush()

            logger.info(
                f"Reported evaluation to Langfuse: session={result.session_id}, "
                f"overall={result.overall_score:.2f}, passed={result.passed}"
            )
            return True

        except Exception as e:
            logger.error(f"Failed to report to Langfuse: {e}")
            return False

    def report_error(
        self,
        session_id: str,
        error: str,
        trace_id: Optional[str] = None,
    ) -> bool:
        """
        Report evaluation error to Langfuse.

        Args:
            session_id: Session identifier
            error: Error message
            trace_id: Optional trace ID

        Returns:
            True if successfully reported
        """
        if not self.client:
            return False

        trace_id = trace_id or session_id

        try:
            self.client.score(
                trace_id=trace_id,
                name="deepeval_error",
                value=0.0,
                comment=error,
                data_type="NUMERIC",
            )
            self.client.flush()
            return True
        except Exception as e:
            logger.error(f"Failed to report error to Langfuse: {e}")
            return False

    def shutdown(self) -> None:
        """Flush and shutdown Langfuse client."""
        if self._client:
            try:
                self._client.flush()
                self._client.shutdown()
            except Exception as e:
                logger.warning(f"Error during Langfuse shutdown: {e}")
