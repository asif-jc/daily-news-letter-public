"""
=== __main__.py ===

Purpose: Run, resume, initialize or inspect the retained news workflow.
Extended Description:
    Parses local settings and invokes workflow.py; never publishes or sends email.
Usage:
    python -m src.news --help
Work Log:
    19/10/2026 -> PostgreSQL-backed news-only MVP.
"""

# ========================================================================
# IMPORTS & CONFIGURATION
# ========================================================================
import argparse
import json
import sys
from pathlib import Path

from dotenv import load_dotenv

from .llm import JsonModel
from .store import NewsStore
from .workflow import run_workflow
from .library import run_library_workflow

# ========================================================================
# PRIMARY EXECUTION
# ========================================================================


def main():
    parser = argparse.ArgumentParser(
        description="Build a retained news-only edition for local review; never publishes."
    )
    parser.add_argument("--env-file", default=".env")
    parser.add_argument(
        "--resume", help="Resume an existing run UUID using its frozen configuration"
    )
    parser.add_argument(
        "--input", type=Path, help="Replay saved normalized RSS observations"
    )
    parser.add_argument(
        "--history", type=Path, help="Explicit reviewed edition history"
    )
    parser.add_argument("--profile", type=Path, help="Versioned editorial profile JSON")
    parser.add_argument(
        "--output-root", type=Path, default=Path(".local/news-editions")
    )
    parser.add_argument(
        "--top-limit", type=int, default=5, help="Legacy workflow resume only"
    )
    parser.add_argument(
        "--quick-limit", type=int, default=10, help="Legacy workflow resume only"
    )
    parser.add_argument(
        "--migrate",
        action="store_true",
        help="Initialize the isolated news schema only",
    )
    parser.add_argument(
        "--stats",
        action="store_true",
        help="Report retained row counts and storage size",
    )
    parser.add_argument("--pool-days", type=int, default=7)
    parser.add_argument("--featured-limit", type=int, default=6)
    parser.add_argument(
        "--include-review-previews",
        action="store_true",
        help="Include unapproved saved editions in the local review archive",
    )
    args = parser.parse_args()
    if args.resume and (args.input or args.history or args.profile):
        parser.error(
            "Resume uses the original input, profile and history; start a new run to change them"
        )
    if (
        Path(".local").resolve() not in args.output_root.resolve().parents
        and args.output_root.resolve() != Path(".local").resolve()
    ):
        parser.error("Review output must remain under ignored .local storage")
    load_dotenv(args.env_file, override=False)
    store = None
    try:
        store = NewsStore.from_env()
        store.migrate()
        if args.migrate:
            print(json.dumps({"migration": "current", "schema_version": 2}))
            return 0
        if args.stats:
            print(json.dumps(store.stats(), indent=2))
            return 0
        model = JsonModel.from_env()
        legacy = bool(
            args.resume
            and store.get_run(args.resume)["config"]["workflow_version"] == 1
        )
        workflow = run_workflow if legacy else run_library_workflow
        extra = (
            {"top_limit": args.top_limit, "quick_limit": args.quick_limit}
            if legacy
            else {
                "pool_days": args.pool_days,
                "featured_limit": args.featured_limit,
                "include_review_previews": args.include_review_previews,
            }
        )
        edition = workflow(
            store,
            model,
            args.output_root,
            run_id=args.resume,
            rows=json.loads(args.input.read_text()) if args.input else None,
            history=json.loads(args.history.read_text()) if args.history else None,
            profile=json.loads(args.profile.read_text()) if args.profile else None,
            **extra,
        )
        print(
            json.dumps(
                {
                    "run_id": edition["run_id"],
                    "status": edition["status"],
                    "counts": edition["counts"],
                    "reader": str(args.output_root / edition["run_id"] / "index.html"),
                    "review": str(args.output_root / edition["run_id"] / "review.html"),
                },
                indent=2,
            )
        )
        return 0
    except Exception as error:
        # Driver errors include host/user details; full connection settings must stay private.
        print(
            f"News workflow failed ({type(error).__name__}); inspect the database run/stage records.",
            file=sys.stderr,
        )
        return 1
    finally:
        if store:
            store.close()


if __name__ == "__main__":
    raise SystemExit(main())
