"""Batch evaluation pipeline for processing Opik traces.

This module provides:
1. Fetch traces from Opik
2. Extract conversation history from traces
3. Run DeepEval metrics on each conversation
4. Send scores back to Opik

Usage:
    from core.evaluation.batch_pipeline import BatchEvaluationPipeline

    pipeline = BatchEvaluationPipeline()
    results = pipeline.run(limit=100)
"""

import logging
from dataclasses import dataclass
from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta

from .conversation_evaluator import ConversationEvaluator, EvaluationResult

logger = logging.getLogger(__name__)


@dataclass
class TraceEvaluation:
    """Evaluation result for a single trace."""
    trace_id: str
    session_id: Optional[str]
    evaluation: EvaluationResult
    evaluated_at: datetime


class BatchEvaluationPipeline:
    """
    Pipeline for batch evaluating Opik traces.

    This pipeline:
    1. Fetches recent traces from Opik
    2. Extracts conversation history from each trace
    3. Runs DeepEval metrics on the conversations
    4. Sends evaluation scores back to Opik

    Example:
        pipeline = BatchEvaluationPipeline(
            project_name="livekit-agents",
            metrics=["topic_adherence", "engagement"],
        )

        # Evaluate last 24 hours of traces
        results = pipeline.run(
            hours_back=24,
            limit=100,
            skip_evaluated=True,
        )

        print(f"Evaluated {len(results)} traces")
        print(f"Average score: {pipeline.get_average_score(results)}")
    """

    def __init__(
        self,
        project_name: Optional[str] = None,
        metrics: Optional[List[str]] = None,
        model: str = "gpt-4o-mini",
    ):
        """
        Initialize the batch evaluation pipeline.

        Args:
            project_name: Opik project name (default: from env OPIK_PROJECT_NAME)
            metrics: List of metric names to evaluate
            model: LLM model for evaluation
        """
        import os
        self.project_name = project_name or os.getenv("OPIK_PROJECT_NAME", "livekit-agents")
        self.evaluator = ConversationEvaluator(
            metrics=metrics,
            send_to_opik=True,
            model=model,
        )
        logger.info(f"Initialized batch pipeline for project: {self.project_name}")

    def _get_opik_client(self):
        """Get Opik client instance."""
        try:
            import opik
            return opik.Opik()
        except ImportError:
            raise ImportError("Opik package not installed. Run: pip install opik")

    def _extract_conversation_from_trace(
        self,
        trace: Dict[str, Any]
    ) -> List[Dict[str, str]]:
        """
        Extract conversation history from an Opik trace.

        Args:
            trace: Opik trace data

        Returns:
            List of message dicts with "role" and "content"
        """
        conversation = []

        # Extract from spans
        spans = trace.get("spans", [])
        for span in spans:
            span_name = span.get("name", "")

            # Look for LLM spans with input/output
            if "llm" in span_name.lower() or "agent" in span_name.lower():
                input_data = span.get("input", {})
                output_data = span.get("output", {})

                # Extract user input
                if isinstance(input_data, dict):
                    user_content = input_data.get("content") or input_data.get("text") or str(input_data)
                    if user_content:
                        conversation.append({
                            "role": "user",
                            "content": user_content,
                        })
                elif isinstance(input_data, str):
                    conversation.append({
                        "role": "user",
                        "content": input_data,
                    })

                # Extract assistant output
                if isinstance(output_data, dict):
                    assistant_content = output_data.get("content") or output_data.get("text") or str(output_data)
                    if assistant_content:
                        conversation.append({
                            "role": "assistant",
                            "content": assistant_content,
                        })
                elif isinstance(output_data, str):
                    conversation.append({
                        "role": "assistant",
                        "content": output_data,
                    })

        # Also check trace-level input/output
        trace_input = trace.get("input")
        trace_output = trace.get("output")

        if trace_input and not conversation:
            conversation.append({
                "role": "user",
                "content": str(trace_input),
            })
        if trace_output and not any(m["role"] == "assistant" for m in conversation):
            conversation.append({
                "role": "assistant",
                "content": str(trace_output),
            })

        return conversation

    def fetch_traces(
        self,
        hours_back: int = 24,
        limit: int = 100,
        skip_evaluated: bool = True,
    ) -> List[Dict[str, Any]]:
        """
        Fetch traces from Opik.

        Args:
            hours_back: How many hours back to fetch
            limit: Maximum number of traces to fetch
            skip_evaluated: Skip traces that already have evaluation scores

        Returns:
            List of trace data dicts
        """
        client = self._get_opik_client()

        # Calculate time range
        end_time = datetime.utcnow()
        start_time = end_time - timedelta(hours=hours_back)

        logger.info(
            f"Fetching traces from {start_time} to {end_time} "
            f"(limit: {limit}, skip_evaluated: {skip_evaluated})"
        )

        try:
            # Fetch traces from Opik
            traces = client.get_traces(
                project_name=self.project_name,
                limit=limit,
                start_time=start_time,
                end_time=end_time,
            )

            # Filter out already evaluated traces if requested
            if skip_evaluated:
                traces = [
                    t for t in traces
                    if not self._has_evaluation_score(t)
                ]

            logger.info(f"Found {len(traces)} traces to evaluate")
            return traces

        except Exception as e:
            logger.error(f"Failed to fetch traces: {e}")
            return []

    def _has_evaluation_score(self, trace: Dict[str, Any]) -> bool:
        """Check if a trace already has evaluation scores."""
        feedback = trace.get("feedback", [])
        for f in feedback:
            if f.get("name", "").startswith(("Topic Adherence", "Engagement", "overall_")):
                return True
        return False

    def evaluate_trace(self, trace: Dict[str, Any]) -> Optional[TraceEvaluation]:
        """
        Evaluate a single trace.

        Args:
            trace: Opik trace data

        Returns:
            TraceEvaluation result or None if evaluation failed
        """
        trace_id = trace.get("id")
        session_id = trace.get("session_id") or trace.get("thread_id")

        if not trace_id:
            logger.warning("Trace missing ID, skipping")
            return None

        # Extract conversation
        conversation = self._extract_conversation_from_trace(trace)

        if not conversation:
            logger.warning(f"No conversation found in trace {trace_id}")
            return None

        logger.info(f"Evaluating trace {trace_id} ({len(conversation)} messages)")

        # Run evaluation
        result = self.evaluator.evaluate_sync(
            conversation=conversation,
            trace_id=trace_id,
            metadata={
                "trace_id": trace_id,
                "session_id": session_id,
            },
        )

        return TraceEvaluation(
            trace_id=trace_id,
            session_id=session_id,
            evaluation=result,
            evaluated_at=datetime.utcnow(),
        )

    def run(
        self,
        hours_back: int = 24,
        limit: int = 100,
        skip_evaluated: bool = True,
    ) -> List[TraceEvaluation]:
        """
        Run batch evaluation on recent traces.

        Args:
            hours_back: How many hours back to fetch traces
            limit: Maximum number of traces to evaluate
            skip_evaluated: Skip traces that already have scores

        Returns:
            List of TraceEvaluation results
        """
        logger.info("Starting batch evaluation pipeline...")

        # Fetch traces
        traces = self.fetch_traces(
            hours_back=hours_back,
            limit=limit,
            skip_evaluated=skip_evaluated,
        )

        if not traces:
            logger.info("No traces to evaluate")
            return []

        # Evaluate each trace
        results = []
        for i, trace in enumerate(traces):
            logger.info(f"Processing trace {i+1}/{len(traces)}")
            try:
                result = self.evaluate_trace(trace)
                if result:
                    results.append(result)
            except Exception as e:
                logger.error(f"Failed to evaluate trace: {e}")

        logger.info(f"Batch evaluation complete: {len(results)} traces evaluated")
        return results

    @staticmethod
    def get_average_score(results: List[TraceEvaluation]) -> float:
        """Calculate average overall score across evaluations."""
        if not results:
            return 0.0
        scores = [r.evaluation.overall_score for r in results]
        return sum(scores) / len(scores)

    @staticmethod
    def get_pass_rate(results: List[TraceEvaluation]) -> float:
        """Calculate pass rate across evaluations."""
        if not results:
            return 0.0
        passed = sum(1 for r in results if r.evaluation.passed)
        return passed / len(results)

    def print_summary(self, results: List[TraceEvaluation]):
        """Print a summary of evaluation results."""
        if not results:
            print("No evaluation results to summarize")
            return

        print("\n" + "=" * 60)
        print("BATCH EVALUATION SUMMARY")
        print("=" * 60)
        print(f"Traces evaluated: {len(results)}")
        print(f"Average score: {self.get_average_score(results):.2f}")
        print(f"Pass rate: {self.get_pass_rate(results) * 100:.1f}%")
        print()

        # Per-metric summary
        metric_scores = {}
        for result in results:
            for metric in result.evaluation.metrics:
                if metric.name not in metric_scores:
                    metric_scores[metric.name] = []
                metric_scores[metric.name].append(metric.score)

        print("Per-Metric Scores:")
        for name, scores in metric_scores.items():
            avg = sum(scores) / len(scores)
            print(f"  {name}: {avg:.2f}")

        print("=" * 60 + "\n")


def run_batch_evaluation(
    hours_back: int = 24,
    limit: int = 100,
    project_name: Optional[str] = None,
) -> List[TraceEvaluation]:
    """
    Convenience function to run batch evaluation.

    Args:
        hours_back: Hours of traces to evaluate
        limit: Maximum traces to evaluate
        project_name: Opik project name

    Returns:
        List of TraceEvaluation results
    """
    pipeline = BatchEvaluationPipeline(project_name=project_name)
    results = pipeline.run(hours_back=hours_back, limit=limit)
    pipeline.print_summary(results)
    return results
