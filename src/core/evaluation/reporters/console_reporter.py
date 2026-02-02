"""
Console printer for evaluation results.
"""

from typing import Optional
from core.evaluation.evaluator import EvaluationResult


class ConsolePrinter:
    """Prints evaluation results to console."""

    def __init__(self, use_colors: bool = True):
        self.use_colors = use_colors

    def print(self, result: EvaluationResult) -> None:
        """Print evaluation result to console."""
        self._print_header(result.session_id)

        if result.error:
            self._print_error(result.error)
            return

        for metric_name, metric_data in result.metrics.items():
            self._print_metric(
                name=metric_name,
                score=metric_data.get("score", 0),
                threshold=metric_data.get("threshold", 0.5),
                passed=metric_data.get("passed", False),
                reason=metric_data.get("reason"),
            )

        self._print_overall(result.overall_score, result.passed)

    def _print_header(self, session_id: str) -> None:
        print("\n" + "=" * 60)
        print(f"EVALUATION RESULTS: {session_id}")
        print("=" * 60)

    def _print_metric(
        self,
        name: str,
        score: float,
        threshold: float,
        passed: bool,
        reason: Optional[str] = None,
    ) -> None:
        status = self._colorize("PASS", "green") if passed else self._colorize("FAIL", "red")
        bar = self._score_bar(score)

        print(f"\n{name}:")
        print(f"  Score: {score:.2f} / {threshold:.2f} [{status}]")
        print(f"  {bar}")

        if reason:
            reason_display = reason[:200] + "..." if len(reason) > 200 else reason
            print(f"  Reason: {reason_display}")

    def _print_overall(self, score: float, passed: bool) -> None:
        print("\n" + "-" * 60)
        status = self._colorize("PASSED", "green") if passed else self._colorize("FAILED", "red")
        print(f"OVERALL SCORE: {score:.2f} [{status}]")
        print("=" * 60 + "\n")

    def _print_error(self, error: str) -> None:
        print(self._colorize(f"\nERROR: {error}", "red"))
        print("=" * 60 + "\n")

    def _score_bar(self, score: float, width: int = 20) -> str:
        filled = int(score * width)
        empty = width - filled
        return f"[{'█' * filled}{'░' * empty}] {score * 100:.0f}%"

    def _colorize(self, text: str, color: str) -> str:
        if not self.use_colors:
            return text

        colors = {
            "green": "\033[92m",
            "red": "\033[91m",
            "reset": "\033[0m",
        }
        return f"{colors.get(color, '')}{text}{colors['reset']}"
