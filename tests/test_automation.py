"""Exercise automatic publication with real Git repositories and retained attempt state."""

import json
import subprocess
import tempfile
import unittest
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch

from news.automation import prepare_checkout, publish_export, publication_age, publication_checkout, refresh


def git(root, *args):
    return subprocess.check_output(['git', '-C', str(root), *args], text=True).strip()


class AutomaticPublicationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.remote = self.root / 'remote.git'
        subprocess.run(['git', 'init', '--bare', '-q', str(self.remote)], check=True)
        self.repo = self.root / 'publisher'
        subprocess.run(['git', 'clone', '-q', str(self.remote), str(self.repo)], check=True)
        git(self.repo, 'checkout', '-b', 'main')
        self.env = patch.dict('os.environ', {
            'GIT_AUTHOR_NAME': 'News test', 'GIT_AUTHOR_EMAIL': 'test@example.com',
            'GIT_COMMITTER_NAME': 'News test', 'GIT_COMMITTER_EMAIL': 'test@example.com',
        })
        self.env.start()
        self.addCleanup(self.env.stop)
        (self.repo / 'README.md').write_text('Code stays reviewed.\n')
        git(self.repo, 'add', 'README.md')
        git(self.repo, 'commit', '-qm', 'Initial code')
        git(self.repo, 'push', '-q', 'origin', 'HEAD:main')
        self.run = str(uuid.uuid4())
        self.state_path = self.root / 'attempt.json'
        self.state = {'run_id': self.run}

    def export(self, generated=None):
        site = self.repo / 'site'
        site.mkdir(exist_ok=True)
        (site / 'index.html').write_text('A verified edition.')
        (site / 'release.json').write_text(json.dumps({
            'run_id': self.run,
            'generated_at': (generated or datetime.now(timezone.utc)).isoformat(),
        }))
        return site

    def test_publish_is_site_only_and_retries_same_commit(self):
        self.export()
        with patch('news.automation.verify_release_directory', side_effect=lambda path, *_: json.loads((path / 'release.json').read_text())), patch('news.automation.scan_export'):
            sha = publish_export(self.repo, self.state_path, self.state)
            self.assertEqual(sha, git(self.remote, 'rev-parse', 'refs/heads/main'))
            self.assertEqual(set(git(self.repo, 'diff-tree', '--no-commit-id', '--name-only', '-r', sha).splitlines()), {'site/index.html', 'site/release.json'})
            self.assertEqual(publish_export(self.repo, self.state_path, self.state), sha)
        self.assertEqual(json.loads(self.state_path.read_text())['commit'], sha)

    def test_code_edits_block_publication(self):
        self.export()
        (self.repo / 'README.md').write_text('Unexpected code edit')
        before = git(self.remote, 'rev-parse', 'refs/heads/main')
        with patch('news.automation.verify_release_directory', side_effect=lambda path, *_: json.loads((path / 'release.json').read_text())), patch('news.automation.scan_export'):
            with self.assertRaises(ValueError):
                publish_export(self.repo, self.state_path, self.state)
        self.assertEqual(git(self.remote, 'rev-parse', 'refs/heads/main'), before)

    def test_failed_push_keeps_commit_for_retry_without_rebuilding(self):
        self.export()
        original = subprocess.run
        def fail_push(args, **kwargs):
            if 'push' in args:
                raise subprocess.CalledProcessError(1, args)
            return original(args, **kwargs)
        with patch('news.automation.verify_release_directory', side_effect=lambda path, *_: json.loads((path / 'release.json').read_text())), patch('news.automation.scan_export'):
            with patch('news.automation.subprocess.run', side_effect=fail_push):
                with self.assertRaises(subprocess.CalledProcessError):
                    publish_export(self.repo, self.state_path, self.state)
            saved = json.loads(self.state_path.read_text())
            self.assertEqual(saved['commit'], git(self.repo, 'rev-parse', 'HEAD'))
            self.assertEqual(publish_export(self.repo, self.state_path, saved), saved['commit'])

    def test_unrelated_local_commit_cannot_be_pushed(self):
        (self.repo / 'README.md').write_text('Unreviewed code')
        git(self.repo, 'add', 'README.md')
        git(self.repo, 'commit', '-qm', 'Unreviewed')
        with self.assertRaises(ValueError):
            prepare_checkout(self.repo, {})

    def test_new_attempt_is_not_blocked_by_failed_previous_commit(self):
        first = publication_checkout(self.repo, str(uuid.uuid4()))
        (first / 'README.md').write_text('A pending commit')
        git(first, 'add', 'README.md')
        git(first, 'commit', '-qm', 'Pending publication')
        second = publication_checkout(self.repo, str(uuid.uuid4()))
        prepare_checkout(second, {})
        self.assertEqual(git(second, 'rev-parse', 'HEAD'), git(self.remote, 'rev-parse', 'main'))
        self.assertNotEqual(git(first, 'rev-parse', 'HEAD'), git(second, 'rev-parse', 'HEAD'))

    def test_reviewed_code_merge_during_generation_preserves_site_export(self):
        self.export()
        reviewer = self.root / 'reviewer'
        subprocess.run(['git', 'clone', '-q', '--branch', 'main', str(self.remote), str(reviewer)], check=True)
        (reviewer / 'README.md').write_text('Reviewed update')
        git(reviewer, 'add', 'README.md')
        git(reviewer, 'commit', '-qm', 'Reviewed code')
        git(reviewer, 'push', '-q', 'origin', 'main')
        prepare_checkout(self.repo, self.state)
        self.assertEqual((self.repo / 'README.md').read_text(), 'Reviewed update')
        self.assertEqual(json.loads((self.repo / 'site/release.json').read_text())['run_id'], self.run)

    def test_older_attempt_cannot_replace_newer_public_edition(self):
        self.export()
        git(self.repo, 'add', 'site/index.html', 'site/release.json')
        git(self.repo, 'commit', '-qm', 'Newer public edition')
        git(self.repo, 'push', '-q', 'origin', 'main')
        before = git(self.remote, 'rev-parse', 'refs/heads/main')
        self.export(datetime.now(timezone.utc) - timedelta(hours=1))
        with patch('news.automation.verify_release_directory', side_effect=lambda path, *_: json.loads((path / 'release.json').read_text())), patch('news.automation.scan_export'):
            with self.assertRaisesRegex(ValueError, 'newer public edition'):
                publish_export(self.repo, self.state_path, self.state)
        self.assertEqual(git(self.remote, 'rev-parse', 'refs/heads/main'), before)

    def test_accepted_push_with_lost_response_can_be_confirmed_on_retry(self):
        self.export()
        original = subprocess.run
        def lose_response(args, **kwargs):
            result = original(args, **kwargs)
            if 'push' in args:
                raise subprocess.CalledProcessError(1, args)
            return result
        with patch('news.automation.verify_release_directory', side_effect=lambda path, *_: json.loads((path / 'release.json').read_text())), patch('news.automation.scan_export'):
            with patch('news.automation.subprocess.run', side_effect=lose_response):
                with self.assertRaises(subprocess.CalledProcessError):
                    publish_export(self.repo, self.state_path, self.state)
            state = json.loads(self.state_path.read_text())
            self.assertEqual(state['commit'], git(self.remote, 'rev-parse', 'refs/heads/main'))
            self.assertEqual(publish_export(self.repo, self.state_path, state), state['commit'])

    def test_future_or_stale_edition_fails_freshness(self):
        now = datetime.now(timezone.utc)
        for delta in (timedelta(hours=-17), timedelta(hours=1)):
            with self.assertRaises(ValueError):
                publication_age({'generated_at': (now + delta).isoformat()}, now=now)
        self.assertAlmostEqual(publication_age({'generated_at': (now - timedelta(hours=2)).isoformat()}, now=now), 2)

class RefreshRecoveryTests(unittest.TestCase):
    def setUp(self):
        import os
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.previous = Path.cwd()
        os.chdir(self.temp.name)
        self.addCleanup(os.chdir, self.previous)
        self.attempt = str(uuid.uuid4())
        self.run = str(uuid.uuid4())
        self.env = patch.dict(os.environ, {
            'NEWS_PUBLISH_CHECKOUT': str(Path('publisher').resolve()),
            'NEWS_PUBLIC_URL': 'https://example.github.io/news/',
        })
        self.env.start()
        self.addCleanup(self.env.stop)
        from unittest.mock import MagicMock
        self.store = MagicMock()
        self.path = Path('.local/automation') / (self.attempt + '.json')

    def test_build_failure_retains_identity_and_next_attempt_resumes_it(self):
        def fail(*args, **kwargs):
            kwargs['on_run_created'](self.run)
            raise RuntimeError('Collection interrupted')
        with patch('news.automation.publication_checkout', return_value=Path('publisher')), patch('news.automation.prepare_checkout'), patch('news.automation.run_workflow', side_effect=fail):
            with self.assertRaises(RuntimeError):
                refresh(self.attempt, store=self.store, model=object(), notify=lambda _: None)
        self.assertEqual(json.loads(self.path.read_text())['run_id'], self.run)
        with patch('news.automation.publication_checkout', return_value=Path('publisher')), patch('news.automation.prepare_checkout'), patch('news.automation.run_workflow', return_value={'run_id': self.run}) as build, patch('news.automation.export_publication'), patch('news.automation.publish_export'), patch('news.automation.confirm_publication', return_value={'files_verified': 4}):
            result = refresh(self.attempt, store=self.store, model=object(), notify=lambda _: None)
        self.assertEqual(build.call_args.kwargs['run_id'], self.run)
        self.assertEqual(result['confirmed']['files_verified'], 4)
        self.store.lock_run.assert_called_with('automatic-publication')

    def test_delivery_failure_retries_without_building_or_exporting_again(self):
        from news.automation import save_attempt
        save_attempt(self.path, {'attempt_id': self.attempt, 'run_id': self.run, 'commit': 'a' * 40})
        with patch('news.automation.publication_checkout', return_value=Path('publisher')), patch('news.automation.prepare_checkout'), patch('news.automation.run_workflow') as build, patch('news.automation.export_publication') as export, patch('news.automation.publish_export'), patch('news.automation.confirm_publication', side_effect=ValueError('Not yet delivered')), patch.dict('os.environ', {'NEWS_DEPLOY_TIMEOUT_SECONDS':'0'}):
            with self.assertRaises(TimeoutError):
                refresh(self.attempt, store=self.store, model=object(), notify=lambda _: None)
        build.assert_not_called()
        export.assert_not_called()
        self.assertNotIn('confirmed', json.loads(self.path.read_text()))

    def test_competing_launch_does_no_work(self):
        self.store.lock_run.return_value.__enter__.side_effect = RuntimeError('Already running')
        with patch('news.automation.publication_checkout', return_value=Path('publisher')), patch('news.automation.prepare_checkout') as prepare:
            with self.assertRaises(RuntimeError):
                refresh(self.attempt, store=self.store, model=object(), notify=lambda _: None)
        prepare.assert_not_called()
        self.assertFalse(self.path.exists())
