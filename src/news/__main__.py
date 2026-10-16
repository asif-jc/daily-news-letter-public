import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

from dotenv import load_dotenv

from .llm import JsonModel
from .pipeline import build_edition, collect_articles


def main():
    parser = argparse.ArgumentParser(description='Build a local, news-only edition for review; never publishes.')
    parser.add_argument('--env-file', default='.env')
    parser.add_argument('--input', type=Path, help='Replay saved collected articles instead of fetching RSS')
    parser.add_argument('--history', type=Path, help='Previously reviewed edition for repeat/update comparison')
    parser.add_argument('--top-limit', type=int, default=5)
    parser.add_argument('--quick-limit', type=int, default=10)
    args = parser.parse_args()
    if not 0 <= args.top_limit <= 10 or not 0 <= args.quick_limit <= 20 or not args.top_limit + args.quick_limit:
        parser.error('Use 0–10 top and 0–20 quick stories, with at least one available slot')
    load_dotenv(args.env_file, override=False)
    run_dir = Path('.local/news-runs') / datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')
    run_dir.mkdir(parents=True, exist_ok=False)
    try:
        model = JsonModel.from_env(audit_dir=run_dir / 'model')
        rows, health = (json.loads(args.input.read_text()), []) if args.input else collect_articles()
        history = json.loads(args.history.read_text()) if args.history else None
        edition = build_edition(rows, model, run_dir, history=history, source_health=health,
                                top_limit=args.top_limit, quick_limit=args.quick_limit)
        print(json.dumps({'status': edition['status'], 'counts': edition['counts'],
                          'run_directory': str(run_dir)}, indent=2))
        return 0
    except Exception as exc:
        print(f'News review run failed ({type(exc).__name__}); inspect local run artifacts.', file=sys.stderr)
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
