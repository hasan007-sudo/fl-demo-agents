"""
Base evaluator class for DeepEval integration.
"""

import logging
from typing import List, Dict, Any, Optional
from dataclasses import dataclass, field
from deepeval import evaluate
from deepeval.test_case import ConversationalTestCase
from deepeval.metrics import BaseMetric

logger = logging.getLogger(__name__)


@dataclass
class EvaluationResult:
    """Results from a DeepEval evaluation run."""

    session_id: str
    overall_score: float
    metrics: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    passed: bool = True
    error: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "session_id": self.session_id,
            "overall_score": self.overall_score,
            "metrics": self.metrics,
            "passed": self.passed,
            "error": self.error,
        }


class BaseEvaluator:
    """
    Base class for DeepEval evaluators.

    Subclass and implement get_metrics() for agent-specific evaluation.
    """

    def __init__(self, model: str = "gpt-4o-mini", verbose: bool = False):
        self.model = model
        self.verbose = verbose

    def get_metrics(self) -> List[BaseMetric]:
        """Override in subclass to define metrics."""
        raise NotImplementedError("Subclass must implement get_metrics()")

    def evaluate(
        self,
        test_case: ConversationalTestCase,
        metrics: Optional[List[BaseMetric]] = None,
    ) -> EvaluationResult:
        """Run evaluation on a test case."""
        if metrics is None:
            metrics = self.get_metrics()

        session_id = (test_case.additional_metadata or {}).get("session_id", "unknown")

        try:
            evaluate(
                test_cases=[test_case],
                metrics=metrics,
            )

            # Extract scores from metrics
            metric_results = {}
            total_score = 0.0
            all_passed = True

            for metric in metrics: # TODO: check metrics values are present
                score = getattr(metric, "score", 0.0) or 0.0
                reason = getattr(metric, "reason", "") or ""
                passed = getattr(metric, "success", score >= metric.threshold)

                metric_results[metric.__class__.__name__] = {
                    "score": score,
                    "threshold": metric.threshold,
                    "passed": passed,
                    "reason": reason,
                }

                total_score += score
                if not passed:
                    all_passed = False

            overall_score = total_score / len(metrics) if metrics else 0.0

            return EvaluationResult(
                session_id=session_id,
                overall_score=overall_score,
                metrics=metric_results,
                passed=all_passed,
            )

        except Exception as e:
            logger.error(f"Evaluation failed for session {session_id}: {e}")
            return EvaluationResult(
                session_id=session_id,
                overall_score=0.0,
                passed=False,
                error=str(e),
            )
