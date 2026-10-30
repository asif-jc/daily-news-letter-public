"""Check public freshness from GitHub, independently of the private generation host."""

import argparse
import json
import os

import requests

from .automation import publication_age
from .publication import fetch_public_file, validate_manifest

ISSUE_TITLE = 'Daily News publication needs attention'
ISSUE_MARKER = '<!-- daily-news-freshness -->'


def check_publication(site_url):
    try:
        manifest = validate_manifest(json.loads(fetch_public_file(site_url.rstrip('/') + '/release.json')))
        age = publication_age(manifest)
        return {'healthy': True, 'age_hours': round(age, 2), 'run_id': manifest['run_id']}
    except Exception as error:
        # The public watchdog reports exception types, never transport text or private diagnostics.
        return {'healthy': False, 'error_type': type(error).__name__}


def update_issue(result, repository, token):
    session = requests.Session()
    session.headers.update({'Authorization': 'Bearer ' + token, 'Accept': 'application/vnd.github+json'})
    root = 'https://api.github.com/repos/' + repository + '/issues'
    response = session.get(root, params={'state': 'open', 'creator': 'github-actions[bot]', 'per_page': 100}, timeout=30)
    response.raise_for_status()
    issues = [i for i in response.json() if i['title'] == ISSUE_TITLE and ISSUE_MARKER in (i.get('body') or '')]
    run_url = 'https://github.com/' + repository + '/actions/runs/' + os.environ.get('GITHUB_RUN_ID', '')
    if not result['healthy'] and not issues:
        response = session.post(root, json={
            'title': ISSUE_TITLE,
            'body': ISSUE_MARKER + '\nThe public edition is unavailable, invalid, future dated, or older than 16 hours. '
                    'The last good reader has not been intentionally replaced. Inspect the private news job and deployment history.\n\n'
                    '[Watchdog run](' + run_url + ')',
            'assignees': [repository.split('/')[0]],
        }, timeout=30)
        response.raise_for_status()
    if result['healthy']:
        for issue in issues:
            response = session.patch(root + '/' + str(issue['number']), json={'state': 'closed', 'state_reason': 'completed'}, timeout=30)
            response.raise_for_status()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--site-url', required=True)
    args = parser.parse_args()
    result = check_publication(args.site_url)
    print(json.dumps(result))
    if os.getenv('GITHUB_TOKEN') and os.getenv('GITHUB_REPOSITORY'):
        try:
            update_issue(result, os.environ['GITHUB_REPOSITORY'], os.environ['GITHUB_TOKEN'])
        except requests.RequestException as error:
            print('Watchdog issue update failed: ' + type(error).__name__)
            return 1
    return 0 if result['healthy'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
