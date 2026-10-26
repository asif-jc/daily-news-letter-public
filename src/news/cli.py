"""Operate private news processing and explicit reader-only publication steps.
Deployment belongs to GitHub Pages; only confirm-publication changes delivery history.
"""

import argparse
import json
import sys
import traceback
from datetime import datetime, timezone
from pathlib import Path

from dotenv import load_dotenv

from .llm import JsonModel
from .publication import (
    export_publication,
    confirm_publication,
    verify_release_directory,
)
from .store import NewsStore
from .workflow import run_workflow

# ========================================================================
# COMMAND CONTRACTS
# ========================================================================


def command_parser():
    parser = argparse.ArgumentParser(
        description="Retained news processing and verified static publication."
    )
    parser.add_argument(
        "--env-file", default=".env", help="Ignored private runtime settings"
    )
    commands = parser.add_subparsers(dest="command", required=True)
    build = commands.add_parser(
        "build", help="Build or resume a private review edition"
    )
    build.add_argument("--resume", help="Run UUID; uses frozen inputs and prompts")
    build.add_argument("--profile", type=Path)
    build.add_argument(
        "--article-holds",
        type=Path,
        help="Private JSON article IDs and reasons to withhold in a new run",
    )
    build.add_argument("--pool-days", type=int)
    build.add_argument("--featured-limit", type=int)
    build.add_argument("--output-root", type=Path, default=Path(".local/news-editions"))
    build.add_argument("--include-review-previews", action="store_true")
    commands.add_parser("migrate", help="Apply news-schema migrations only")
    commands.add_parser("stats", help="Inspect retained row counts and storage")
    export = commands.add_parser(
        "export", help="Export a reader-only candidate, without recording publication"
    )
    export.add_argument("--run", required=True)
    export.add_argument("--output", type=Path, default=Path("site"))
    confirm = commands.add_parser(
        "confirm-publication",
        help="Verify deployed file hashes, then record publication",
    )
    confirm.add_argument("--run", required=True)
    confirm.add_argument("--manifest", type=Path, default=Path("site/release.json"))
    confirm.add_argument("--site-url", required=True)
    verify = commands.add_parser(
        "verify-release", help="Check staged public artifacts without private settings"
    )
    verify.add_argument("--manifest", type=Path, default=Path("site/release.json"))
    return parser


# ========================================================================
# PRIMARY EXECUTION
# ========================================================================


def main(argv=None):
    parser = command_parser()
    args = parser.parse_args(argv)
    if args.command == "build":
        private_root = Path(".local").resolve()
        output = args.output_root.resolve()
        if output != private_root and private_root not in output.parents:
            parser.error(
                "Private review output must remain under ignored .local storage"
            )
        if args.resume and any(
            v is not None
            for v in (
                args.profile,
                args.pool_days,
                args.featured_limit,
                args.article_holds,
            )
        ):
            parser.error("Resume uses frozen settings; start a new run to change them")
    store = None
    try:
        if args.command == "verify-release":
            result = verify_release_directory(args.manifest.parent)
            print(json.dumps(result, indent=2))
            return 0
        load_dotenv(args.env_file, override=False)
        store = NewsStore.from_env()
        store.migrate()
        if args.command == "build":
            edition = run_workflow(
                store,
                JsonModel.from_env(),
                args.output_root,
                run_id=args.resume,
                profile=json.loads(args.profile.read_text()) if args.profile else None,
                article_holds=(
                    json.loads(args.article_holds.read_text())
                    if args.article_holds
                    else None
                ),
                pool_days=args.pool_days if args.pool_days is not None else 7,
                featured_limit=(
                    args.featured_limit if args.featured_limit is not None else 6
                ),
                include_review_previews=args.include_review_previews,
            )
            result = {
                "run_id": edition["run_id"],
                "counts": edition["counts"],
                "reader": str(args.output_root / edition["run_id"] / "index.html"),
                "review": str(args.output_root / edition["run_id"] / "review.html"),
            }
        elif args.command == "export":
            result = export_publication(store, args.run, args.output)
        elif args.command == "confirm-publication":
            result = confirm_publication(store, args.run, args.manifest, args.site_url)
        elif args.command == "stats":
            result = store.stats()
        else:
            result = {"schema": "news", "migration": "current"}
        print(json.dumps(result, indent=2))
        return 0
    except Exception as error:
        # Driver/transport details can contain private addresses, so keep the traceback ignored.
        log = Path(".local/news-errors.log")
        log.parent.mkdir(parents=True, exist_ok=True)
        with log.open("a") as stream:
            stream.write("\n" + datetime.now(timezone.utc).isoformat() + "\n")
            traceback.print_exc(file=stream)
        print(
            f"News command failed ({type(error).__name__}); private details: .local/news-errors.log",
            file=sys.stderr,
        )
        return 1
    finally:
        if store is not None:
            store.close()
