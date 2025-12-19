#!/usr/bin/env python3
"""
CLI tool for evaluating conversation quality.

Usage:
    # Evaluate a single conversation from JSON file
    python -m evaluate conversation path/to/conversation.json

    # Run batch evaluation on recent Opik traces
    python -m evaluate batch --hours 24 --limit 100

    # Evaluate with specific metrics
    python -m evaluate batch --metrics topic_adherence engagement
"""

import argparse
import json
import logging
import sys
from pathlib import Path

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent))

from core.evaluation import (
    ConversationEvaluator,
    evaluate_tutoring_session,
)
from core.evaluation.batch_pipeline import (
    BatchEvaluationPipeline,
    run_batch_evaluation,
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


def evaluate_conversation_file(file_path: str, metrics: list = None):
    """Evaluate a conversation from a JSON file."""
    path = Path(file_path)
    if not path.exists():
        print(f"Error: File not found: {file_path}")
        sys.exit(1)

    with open(path) as f:
        data = json.load(f)

    # Support both list of messages and dict with "conversation" key
    if isinstance(data, list):
        conversation = data
    elif isinstance(data, dict) and "conversation" in data:
        conversation = data["conversation"]
    elif isinstance(data, dict) and "messages" in data:
        conversation = data["messages"]
    else:
        print("Error: JSON must be a list of messages or dict with 'conversation'/'messages' key")
        sys.exit(1)

    print(f"\nEvaluating conversation from {file_path}")
    print(f"Messages: {len(conversation)}")
    print("-" * 50)

    results = evaluate_tutoring_session(conversation, metrics=metrics)

    print(f"\nOverall Score: {results.overall_score:.2f}")
    print(f"Passed: {'Yes' if results.passed else 'No'}")
    print("\nMetric Scores:")
    for metric in results.metrics:
        status = "PASS" if metric.passed else "FAIL"
        print(f"  {metric.name}: {metric.score:.2f} [{status}]")
        if metric.reason:
            print(f"    Reason: {metric.reason[:100]}...")

    return results


def evaluate_batch(hours: int, limit: int, metrics: list = None, project: str = None):
    """Run batch evaluation on Opik traces."""
    print(f"\nRunning batch evaluation")
    print(f"  Hours back: {hours}")
    print(f"  Limit: {limit}")
    print(f"  Project: {project or 'default'}")
    print("-" * 50)

    pipeline = BatchEvaluationPipeline(
        project_name=project,
        metrics=metrics,
    )

    results = pipeline.run(
        hours_back=hours,
        limit=limit,
        skip_evaluated=True,
    )

    pipeline.print_summary(results)
    return results


def main():
    parser = argparse.ArgumentParser(
        description="Evaluate conversation quality using DeepEval metrics"
    )
    subparsers = parser.add_subparsers(dest="command", help="Command to run")

    # Conversation evaluation command
    conv_parser = subparsers.add_parser(
        "conversation",
        help="Evaluate a single conversation from JSON file"
    )
    conv_parser.add_argument(
        "file",
        help="Path to JSON file with conversation"
    )
    conv_parser.add_argument(
        "--metrics",
        nargs="+",
        choices=[
            "topic_adherence",
            "engagement",
            "learning_effectiveness",
            "role_adherence",
            "conversation_completeness",
        ],
        help="Specific metrics to evaluate"
    )

    # Batch evaluation command
    batch_parser = subparsers.add_parser(
        "batch",
        help="Run batch evaluation on Opik traces"
    )
    batch_parser.add_argument(
        "--hours",
        type=int,
        default=24,
        help="Hours of traces to evaluate (default: 24)"
    )
    batch_parser.add_argument(
        "--limit",
        type=int,
        default=100,
        help="Maximum traces to evaluate (default: 100)"
    )
    batch_parser.add_argument(
        "--project",
        help="Opik project name"
    )
    batch_parser.add_argument(
        "--metrics",
        nargs="+",
        choices=[
            "topic_adherence",
            "engagement",
            "learning_effectiveness",
            "role_adherence",
            "conversation_completeness",
        ],
        help="Specific metrics to evaluate"
    )

    # Demo command
    demo_parser = subparsers.add_parser(
        "demo",
        help="Run a demo evaluation on sample conversation"
    )

    args = parser.parse_args()

    if args.command == "conversation":
        evaluate_conversation_file(args.file, args.metrics)

    elif args.command == "batch":
        evaluate_batch(
            hours=args.hours,
            limit=args.limit,
            metrics=args.metrics,
            project=args.project,
        )

    elif args.command == "demo":
        # Demo with sample conversation
        sample_conversation = [
            {
                "role": "user",
                "content": "Hello, I want to practice my English speaking skills."
            },
            {
                "role": "assistant",
                "content": "Hello! That's wonderful that you want to improve your English speaking. I'd be happy to help you practice. What topics interest you? We could talk about your hobbies, your work, travel, or anything else you'd like to discuss."
            },
            {
                "role": "user",
                "content": "I like to talk about travel. I went to Japan last year."
            },
            {
                "role": "assistant",
                "content": "Oh, Japan is a fantastic destination! Tell me more about your trip. What cities did you visit, and what was your favorite experience there? Take your time and try to describe it in as much detail as you can."
            },
            {
                "role": "user",
                "content": "I visit Tokyo and Kyoto. Tokyo is very big city with many people. I like the temples in Kyoto very much."
            },
            {
                "role": "assistant",
                "content": "Great job describing your trip! I noticed a small grammar point we can work on: instead of 'I visit,' we say 'I visited' when talking about the past. So: 'I visited Tokyo and Kyoto.' Also, we'd say 'Tokyo is a very big city' - adding 'a' before the adjective. The temples in Kyoto are indeed beautiful! Can you tell me which temple was your favorite?"
            },
        ]

        print("\n" + "=" * 60)
        print("DEMO EVALUATION")
        print("=" * 60)
        print("\nSample conversation:")
        for msg in sample_conversation:
            role = msg["role"].upper()
            content = msg["content"][:80] + "..." if len(msg["content"]) > 80 else msg["content"]
            print(f"  [{role}]: {content}")

        print("\nRunning evaluation...")
        results = evaluate_tutoring_session(sample_conversation)

        print(f"\nOverall Score: {results.overall_score:.2f}")
        print(f"Passed: {'Yes' if results.passed else 'No'}")
        print("\nMetric Scores:")
        for metric in results.metrics:
            status = "PASS" if metric.passed else "FAIL"
            print(f"  {metric.name}: {metric.score:.2f} [{status}]")

    else:
        parser.print_help()


if __name__ == "__main__":
    main()
