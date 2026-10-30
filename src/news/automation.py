"""Publish a retained edition automatically, with restartable delivery and a site-only Git boundary.
Dagster owns scheduling; this module owns one complete, exclusive publication attempt.
"""

import json
import os
import subprocess
import time
from datetime import datetime, timezone
from pathlib import Path
from uuid import UUID

import requests

from .ingest import write_json
from .llm import JsonModel
from .publication import (
    artifact_path, confirm_publication, export_publication, verify_release_directory,
)
from .store import NewsStore
from .workflow import run_workflow


# ========================================================================
# PUBLICATION GUARDS
# ========================================================================


def publication_age(manifest, now=None, maximum_hours=16):
    generated = datetime.fromisoformat(manifest['generated_at'].replace('Z', '+00:00'))
    if generated.tzinfo is None:
        raise ValueError('Publication timestamp must include its timezone')
    age = ((now or datetime.now(timezone.utc)) - generated).total_seconds() / 3600
    if age < -5 / 60 or age > maximum_hours:
        raise ValueError('Public edition is stale or future dated')
    return age


def save_attempt(path, state):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    temporary = path.with_suffix('.tmp')
    temporary.write_text(json.dumps(state, indent=2) + '\n')
    temporary.chmod(0o600)
    temporary.replace(path)


def git(repository, *args):
    # Never echo Git transport errors: remote configuration can contain private paths or credentials.
    result = subprocess.run(
        ['git', '-C', str(repository), *args], check=True,
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=120,
    )
    return result.stdout.strip()


def changed_paths(repository):
    raw = subprocess.run(
        ['git', '-C', str(repository), 'status', '--porcelain=v1', '-z', '--untracked-files=all'],
        check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=30,
    ).stdout
    entries = [entry.decode() for entry in raw.split(b'\0') if entry]
    if any(entry[0] in 'RC' or entry[1] in 'RC' for entry in entries):
        raise ValueError('Renames are not supported in an automatic export')
    paths = [entry[3:] for entry in entries]
    if any(not p.startswith('site/') or not (p == 'site/release.json' or artifact_path(p[5:])) for p in paths):
        raise ValueError('Automatic publisher refuses changes outside the managed reader')
    return paths


def publication_checkout(base, attempt_id):
    base = Path(base).resolve()
    checkout = base / '.local/publications' / str(UUID(attempt_id))
    if not checkout.exists():
        git(base, 'fetch', 'origin', 'main')
        checkout.parent.mkdir(parents=True, exist_ok=True)
        # An abandoned push owns only this detached worktree, never the next scheduled run.
        git(base, 'worktree', 'add', '--detach', str(checkout), 'origin/main')
    return checkout


def prepare_checkout(repository, state):
    if git(repository, 'branch', '--show-current') not in ('main', ''):
        raise ValueError('Publisher checkout must follow main or a detached publication attempt')
    git(repository, 'fetch', 'origin', 'main')
    head, remote = git(repository, 'rev-parse', 'HEAD'), git(repository, 'rev-parse', 'origin/main')
    paths = changed_paths(repository)
    if state.get('commit'):
        if head != state['commit'] or paths:
            raise ValueError('Pending publication checkout was changed')
        return
    # Only remote-reviewed code may be the parent of an automatic site commit.
    if head != remote:
        ahead = git(repository, 'rev-list', '--count', 'origin/main..HEAD')
        if ahead != '0':
            raise ValueError('Publisher has unreviewed local commits')
        git(repository, 'merge', '--ff-only', 'origin/main')


def scan_export(repository, log_root, committed=False):
    log_root = Path(log_root)
    log_root.mkdir(parents=True, exist_ok=True)
    arguments = (
        ['git', str(repository), '--log-opts=origin/main..HEAD'] if committed
        else ['dir', str(Path(repository) / 'site')]
    )
    result = subprocess.run(
        ['gitleaks', *arguments, '--redact=100', '--no-banner',
         '--report-format=json', '--report-path=' + str(log_root / ('commits.json' if committed else 'files.json'))],
        stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=120,
    )
    (log_root / ('commits.log' if committed else 'files.log')).write_bytes(result.stdout)
    if result.returncode:
        raise ValueError('Automatic publication privacy scan failed; inspect private diagnostics')


def publish_export(repository, state_path, state):
    repository, state_path = Path(repository), Path(state_path)
    prepare_checkout(repository, state)
    site = repository / 'site'
    manifest = verify_release_directory(site, state['run_id'])
    publication_age(manifest)
    # An old retry must never replace a newer edition that another attempt already delivered.
    try:
        remote_manifest = json.loads(git(repository, 'show', 'origin/main:site/release.json'))
    except subprocess.CalledProcessError:
        remote_manifest = None
    if remote_manifest:
        candidate_time = datetime.fromisoformat(manifest['generated_at'])
        remote_time = datetime.fromisoformat(remote_manifest['generated_at'])
        if remote_time > candidate_time:
            raise ValueError('Refusing to replace a newer public edition')
    paths = changed_paths(repository)
    scan_export(repository, state_path.parent / 'scans')
    if not state.get('commit'):
        if paths:
            git(repository, 'add', '--', *paths)
            git(repository, 'commit', '-m', 'Publish news edition ' + state['run_id'])
        state['commit'] = git(repository, 'rev-parse', 'HEAD')
        save_attempt(state_path, state)
    scan_export(repository, state_path.parent / 'scans', committed=True)
    git(repository, 'push', 'origin', state['commit'] + ':refs/heads/main')
    state['pushed'] = True
    save_attempt(state_path, state)
    return state['commit']


# ========================================================================
# RESTARTABLE REFRESH
# ========================================================================


def refresh(attempt_id, *, store=None, model=None, notify=print):
    attempt_id = str(UUID(attempt_id))
    base = Path(os.environ['NEWS_PUBLISH_CHECKOUT']).resolve()
    state_root = Path('.local/automation')
    state_path = state_root / (attempt_id + '.json')
    state = json.loads(state_path.read_text()) if state_path.exists() else {'attempt_id': attempt_id}
    owned_store = store is None
    store = store or NewsStore.from_env()
    try:
        # This session lock covers build through confirmation, including competing scheduler runs.
        with store.lock_run('automatic-publication'):
            if state.get('confirmed'):
                return state
            repository = publication_checkout(base, attempt_id)
            prepare_checkout(repository, state)
            if not state.get('commit'):
                def remember_run(run_id):
                    state['run_id'] = run_id
                    save_attempt(state_path, state)
                notify('Building the retained news edition')
                edition = run_workflow(
                    store, model or JsonModel.from_env(), Path('.local/news-editions'),
                    run_id=state.get('run_id'), on_run_created=remember_run,
                )
                state['run_id'] = edition['run_id']
                save_attempt(state_path, state)
                export_publication(store, state['run_id'], repository / 'site')
            notify('Validating and pushing the public reader export')
            publish_export(repository, state_path, state)
            notify('Waiting for GitHub Pages and verifying every delivered reader file')
            deadline = time.monotonic() + int(os.getenv('NEWS_DEPLOY_TIMEOUT_SECONDS', '1200'))
            while True:
                try:
                    receipt = confirm_publication(
                        store, state['run_id'], repository / 'site/release.json',
                        os.environ['NEWS_PUBLIC_URL'],
                    )
                    break
                except (requests.RequestException, ValueError):
                    if time.monotonic() >= deadline:
                        raise TimeoutError('Public delivery did not match the edition before the deadline') from None
                    time.sleep(30)
            state['confirmed'] = receipt
            save_attempt(state_path, state)
            notify('Publication confirmed: ' + state['run_id'])
            return state
    finally:
        if owned_store:
            store.close()
