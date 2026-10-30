"""Watchdog decisions are independent of private runtime connectivity."""

import unittest
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

from news.monitoring import check_publication


class MonitoringTests(unittest.TestCase):
    def manifest(self, age=0):
        return {'run_id': 'test-run', 'generated_at': (datetime.now(timezone.utc) - timedelta(hours=age)).isoformat()}

    def test_current_publication_is_healthy(self):
        with patch('news.monitoring.fetch_public_file', return_value=b'{}'), patch('news.monitoring.validate_manifest', return_value=self.manifest(2)):
            self.assertTrue(check_publication('https://example.github.io/news/')['healthy'])

    def test_stale_or_unavailable_site_is_unhealthy(self):
        with patch('news.monitoring.fetch_public_file', return_value=b'{}'), patch('news.monitoring.validate_manifest', return_value=self.manifest(17)):
            self.assertFalse(check_publication('https://example.github.io/news/')['healthy'])
        with patch('news.monitoring.fetch_public_file', side_effect=TimeoutError('private diagnostics')):
            result = check_publication('https://example.github.io/news/')
            self.assertFalse(result['healthy'])
            self.assertNotIn('private diagnostics', str(result))
