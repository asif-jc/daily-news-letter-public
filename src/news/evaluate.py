"""
=== evaluate.py ===

Purpose: Measure event grouping against labeled regression cases.
Extended Description:
    Synthetic case evaluation only; live editorial review remains separate.
Usage:
    python -m src.news.evaluate --env-file .env
Work Log:
    19/10/2026 -> PostgreSQL-backed news-only MVP.
"""

# ========================================================================
# IMPORTS & CONFIGURATION
# ========================================================================
import argparse
import hashlib
import json
from datetime import datetime, timezone
from itertools import combinations
from pathlib import Path

from dotenv import load_dotenv

from .events import group_events
from .grouping import GROUP_PAIR_PROMPT, group_events_bounded
from .llm import JsonModel, prompt_versions

# ========================================================================
# GROUPING EVALUATION
# ========================================================================


def evaluate_grouping(model, fixture_path, legacy=False):
    cases = json.loads(Path(fixture_path).read_text())
    results = []
    for case in cases:
        articles = [
            {
                "id": id,
                "title": title,
                "description": description,
                "source": "Example",
                "category": "world",
                "published": datetime.now(timezone.utc).isoformat(),
            }
            for id, title, description in case["articles"]
        ]
        expected = {
            tuple(sorted(pair))
            for group in case["groups"]
            for pair in combinations(group, 2)
        }
        try:
            groups = (
                group_events(articles, model, case.get("history"))
                if legacy
                else group_events_bounded(
                    articles, model, case.get("history") or {"stories": []}
                )
            )
            actual = {
                tuple(sorted(pair))
                for group in groups
                for pair in combinations(group["source_ids"], 2)
            }
            novelty = {id: g["novelty"] for g in groups for id in g["source_ids"]}
            novelty_errors = {
                id: {"expected": n, "actual": novelty[id]}
                for id, n in case.get("novelty", {}).items()
                if novelty[id] != n
            }
            results.append(
                {
                    "case": case["name"],
                    "passed": actual == expected and not novelty_errors,
                    "false_merges": sorted(actual - expected),
                    "missed_pairs": sorted(expected - actual),
                    "novelty_errors": novelty_errors,
                    "groups": groups,
                }
            )
        except (ValueError, RuntimeError) as error:
            results.append(
                {
                    "case": case["name"],
                    "passed": False,
                    "error_type": type(error).__name__,
                }
            )
    return {
        "case_count": len(cases),
        "passed": sum(r["passed"] for r in results),
        "prompt_sha256": (
            prompt_versions()["group_events"]
            if legacy
            else hashlib.sha256(GROUP_PAIR_PROMPT.encode()).hexdigest()
        ),
        "results": results,
    }


# ========================================================================
# PRIMARY EXECUTION
# ========================================================================


def main():
    parser = argparse.ArgumentParser(
        description="Run labeled grouping cases through the configured LLM"
    )
    parser.add_argument("--env-file", default=".env")
    parser.add_argument("--fixtures", default="tests/fixtures/news_grouping.json")
    parser.add_argument("--output", default=".local/grouping-evaluation.json")
    parser.add_argument(
        "--legacy",
        action="store_true",
        help="Evaluate original version-1 grouping instead",
    )
    args = parser.parse_args()
    load_dotenv(args.env_file)
    model = JsonModel.from_env(audit_dir=Path(".local/grouping-model-audit"))
    result = evaluate_grouping(model, args.fixtures, legacy=args.legacy)
    target = Path(args.output)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(result, indent=2) + "\n")
    print(
        json.dumps(
            {
                "cases": result["case_count"],
                "passed": result["passed"],
                "output": str(target),
            }
        )
    )
    return 0 if result["case_count"] == result["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
