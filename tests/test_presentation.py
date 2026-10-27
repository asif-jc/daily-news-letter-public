"""A visual refresh verifies delivery without replacing first-publication provenance."""

import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from news.publication import confirm_presentation, export_publication
from tests.test_publication import Store


class PresentationTests(unittest.TestCase):
    def test_verified_presentation_and_rejected_metadata_or_delivery_mismatch(self):
        store = Store()
        recorded = []
        store.record_presentation = lambda run, receipt: recorded.append(receipt) or receipt
        run = store.edition['run_id']
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            export_publication(store, run, root)
            def fetch(url):
                return (root / url.split('/news/', 1)[1]).read_bytes()
            with patch('news.publication.fetch_public_file', side_effect=fetch):
                receipt = confirm_presentation(store, run, root/'release.json', 'https://example.github.io/news')
            self.assertEqual(receipt['public_url'], 'https://example.github.io/news/')
            self.assertEqual(len(recorded), 1)
            with patch('news.publication.fetch_public_file', return_value=b'wrong'):
                with self.assertRaises((ValueError, json.JSONDecodeError)):
                    confirm_presentation(store, run, root/'release.json', 'https://example.github.io/news/')
            manifest = json.loads((root/'release.json').read_text())
            manifest['generated_at'] = '2026-10-27T06:00:00+00:00'
            (root/'release.json').write_text(json.dumps(manifest))
            with self.assertRaisesRegex(ValueError, 'retained edition'):
                confirm_presentation(store, run, root/'release.json', 'https://example.github.io/news/')
            self.assertEqual(len(recorded), 1)
