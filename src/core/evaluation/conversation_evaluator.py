"""Conversation quality evaluator using DeepEval metrics.

This module provides:
1. ConversationEvaluator - Main class for evaluating tutoring sessions
2. evaluate_tutoring_session - Quick function for single evaluations
3. Integration with Opik for score tracking

Usage:
    from core.evaluation import ConversationEvaluator, evaluate_tutoring_session

    # Quick evaluation
    results = evaluate_tutoring_session(conversation_history)

    # Full evaluator with Opik integration
    evaluator = ConversationEvaluator(send_to_opik=True)
    results = await evaluator.evaluate(conversation_history, trace_id="xxx")
"""

import logging
from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional
import os

from deepeval import evaluate
from deepeval.test_case import LLMTestCase

from .metrics import (
    TopicAdherenceMetric,
    EngagementMetric,
    LearningEffectivenessMetric,
    RoleAdherenceMetric,
    ConversationCompletenessMetric,
)

logger = logging.getLogger(__name__)


@dataclass
class MetricResult:
    """Result of a single metric evaluation."""
    name: str
    score: float
    passed: bool
    reason: str
    threshold: float


@dataclass
class EvaluationResult:
    """Complete evaluation results for a conversation."""
    overall_score: float
    passed: bool
    metrics: List[MetricResult] = field(default_factory=list)
    conversation_length: int = 0
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "overall_score": self.overall_score,
            "passed": self.passed,
            "conversation_length": self.conversation_length,
            "metrics": [
                {
                    "name": m.name,
                    "score": m.score,
                    "passed": m.passed,
                    "reason": m.reason,
                    "threshold": m.threshold,
                }
                for m in self.metrics
            ],
            "metadata": self.metadata,
        }


class ConversationEvaluator:
    """
    Evaluates English tutoring conversation quality using DeepEval metrics.

    Metrics evaluated:
    - Topic Adherence: Does the tutor stay on topic?
    - Engagement: Is the conversation engaging and encouraging?
    - Learning Effectiveness: Does the tutoring help the student learn?
    - Role Adherence: Does the tutor maintain appropriate persona?
    - Conversation Completeness: Are student needs addressed?

    Example:
        evaluator = ConversationEvaluator()
        conversation = [
            {"role": "user", "content": "Hello, I want to practice English"},
            {"role": "assistant", "content": "Great! Let's start..."},
        ]
        results = evaluator.evaluate_sync(conversation)
        print(f"Overall score: {results.overall_score}")
    """

    def __init__(
        self,
        metrics: Optional[List[str]] = None,
        send_to_opik: bool = False,
        model: str = "gpt-4o-mini",
    ):
        """
        Initialize the evaluator.

        Args:
            metrics: List of metric names to use. If None, uses all metrics.
                Options: "topic_adherence", "engagement", "learning_effectiveness",
                         "role_adherence", "conversation_completeness"
            send_to_opik: Whether to send scores to Opik dashboard
            model: LLM model to use for evaluation (default: gpt-4o-mini for cost)
        """
        self.send_to_opik = send_to_opik
        self.model = model

        # Initialize selected metrics
        all_metrics = {
            "topic_adherence": TopicAdherenceMetric,
            "engagement": EngagementMetric,
            "learning_effectiveness": LearningEffectivenessMetric,
            "role_adherence": RoleAdherenceMetric,
            "conversation_completeness": ConversationCompletenessMetric,
        }

        if metrics is None:
            metrics = list(all_metrics.keys())

        self.metrics = []
        for metric_name in metrics:
            if metric_name in all_metrics:
                metric = all_metrics[metric_name]()
                metric.model = model  # Set the evaluation model
                self.metrics.append(metric)
            else:
                logger.warning(f"Unknown metric: {metric_name}")

        logger.info(f"Initialized evaluator with {len(self.metrics)} metrics")

    def _format_conversation(
        self,
        conversation: List[Dict[str, str]]
    ) -> tuple[str, str]:
        """
        Format conversation history into input/output for evaluation.

        Args:
            conversation: List of message dicts with "role" and "content"

        Returns:
            Tuple of (user_inputs, assistant_outputs)
        """
        user_inputs = []
        assistant_outputs = []

        for msg in conversation:
            role = msg.get("role", "")
            content = msg.get("content", "")

            if role in ("user", "human"):
                user_inputs.append(content)
            elif role in ("assistant", "ai", "tutor"):
                assistant_outputs.append(content)

        return (
            "\n---\n".join(user_inputs),
            "\n---\n".join(assistant_outputs),
        )

    def evaluate_sync(
        self,
        conversation: List[Dict[str, str]],
        trace_id: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> EvaluationResult:
        """
        Evaluate a conversation synchronously.

        Args:
            conversation: List of message dicts with "role" and "content"
            trace_id: Optional Opik trace ID to attach scores to
            metadata: Optional metadata to include in results

        Returns:
            EvaluationResult with scores for all metrics
        """
        if not conversation:
            logger.warning("Empty conversation provided for evaluation")
            return EvaluationResult(
                overall_score=0.0,
                passed=False,
                metadata=metadata or {},
            )

        # Format conversation for evaluation
        user_input, assistant_output = self._format_conversation(conversation)

        if not assistant_output:
            logger.warning("No assistant responses in conversation")
            return EvaluationResult(
                overall_score=0.0,
                passed=False,
                conversation_length=len(conversation),
                metadata=metadata or {},
            )

        # Create test case
        test_case = LLMTestCase(
            input=user_input,
            actual_output=assistant_output,
        )

        # Run evaluation
        logger.info(f"Evaluating conversation with {len(self.metrics)} metrics...")
        metric_results = []
        scores = []

        for metric in self.metrics:
            try:
                metric.measure(test_case)
                result = MetricResult(
                    name=metric.name,
                    score=metric.score,
                    passed=metric.is_successful(),
                    reason=metric.reason or "",
                    threshold=metric.threshold,
                )
                metric_results.append(result)
                scores.append(metric.score)
                logger.info(
                    f"  {metric.name}: {metric.score:.2f} "
                    f"({'PASS' if result.passed else 'FAIL'})"
                )
            except Exception as e:
                logger.error(f"Error evaluating {metric.name}: {e}")
                metric_results.append(MetricResult(
                    name=metric.name,
                    score=0.0,
                    passed=False,
                    reason=f"Evaluation error: {str(e)}",
                    threshold=0.7,
                ))
                scores.append(0.0)

        # Calculate overall score
        overall_score = sum(scores) / len(scores) if scores else 0.0
        passed = all(r.passed for r in metric_results)

        result = EvaluationResult(
            overall_score=overall_score,
            passed=passed,
            metrics=metric_results,
            conversation_length=len(conversation),
            metadata=metadata or {},
        )

        # Send to Opik if enabled
        if self.send_to_opik and trace_id:
            self._send_to_opik(trace_id, result)

        return result

    def _send_to_opik(self, trace_id: str, result: EvaluationResult):
        """Send evaluation scores to Opik."""
        try:
            import opik

            client = opik.Opik()

            # Send each metric as a score
            for metric_result in result.metrics:
                client.log_traces_feedback(
                    trace_ids=[trace_id],
                    feedback={
                        "name": metric_result.name,
                        "value": metric_result.score,
                        "reason": metric_result.reason,
                    }
                )

            # Send overall score
            client.log_traces_feedback(
                trace_ids=[trace_id],
                feedback={
                    "name": "overall_conversation_quality",
                    "value": result.overall_score,
                    "reason": f"Passed: {result.passed}",
                }
            )

            logger.info(f"Sent evaluation scores to Opik (trace: {trace_id})")

        except ImportError:
            logger.warning("Opik package not installed - scores not sent")
        except Exception as e:
            logger.error(f"Failed to send scores to Opik: {e}")


def evaluate_tutoring_session(
    conversation: List[Dict[str, str]],
    metrics: Optional[List[str]] = None,
    model: str = "gpt-4o-mini",
) -> EvaluationResult:
    """
    Quick function to evaluate a tutoring conversation.

    Args:
        conversation: List of message dicts with "role" and "content"
        metrics: Optional list of metrics to use
        model: LLM model for evaluation

    Returns:
        EvaluationResult with all scores

    Example:
        conversation = [
            {"role": "user", "content": "Can you help me with English?"},
            {"role": "assistant", "content": "Of course! What would you like to practice?"},
        ]
        results = evaluate_tutoring_session(conversation)
        print(f"Score: {results.overall_score}")
    """
    evaluator = ConversationEvaluator(metrics=metrics, model=model)
    return evaluator.evaluate_sync(conversation)
