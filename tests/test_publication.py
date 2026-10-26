"""A public release contains only intended reader fields and records verified delivery."""

import hashlib
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from news.publication import (
    export_publication,
    confirm_publication,
    verify_release_directory,
)


class Store:
    def __init__(self):
        self.receipts = []
        self.edition = {
            "schema_version": 3,
            "run_id": "11111111-1111-4111-8111-111111111111",
            "generated_at": "2026-10-26T06:00:00+00:00",
            "publication_status": "ready_for_review",
            "profile_id": "reader",
            "profile_version": 2,
            "stories": [
                {
                    "event_id": "event",
                    "title": "NZ policy decision",
                    "summary": "The government announced its decision.",
                    "why_matters": "",
                    "topics": ["Politics"],
                    "geography": ["NZ"],
                    "featured": True,
                    "importance": "notable",
                    "freshness": "new",
                    "sources": [
                        {
                            "source": "RNZ Politics",
                            "url": "https://www.rnz.co.nz/news/political/123/example",
                        }
                    ],
                    "support": [{"private_raw_text": "MUST_NOT_PUBLISH"}],
                }
            ],
            "private_audit": "MUST_NOT_PUBLISH",
        }

    def get_edition(self, run_id):
        return self.edition

    def get_run(self, run_id):
        return {"status": "ready_for_review", "config": {"archives": []}}

    def record_publication(self, run_id, receipt):
        self.receipts.append(receipt)
        return receipt


class PublicationTests(unittest.TestCase):
    def setUp(self):
        self.store = Store()
        self.run = self.store.edition["run_id"]
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name) / "site"

    def tearDown(self):
        self.temp.cleanup()

    def export(self):
        return export_publication(self.store, self.run, self.root)

    def test_deploy_gate_rejects_hash_correct_private_artifact(self):
        manifest = self.export()
        private = self.root / "review.html"
        private.write_text("private model audit")
        manifest["files"]["review.html"] = hashlib.sha256(
            private.read_bytes()
        ).hexdigest()
        (self.root / "release.json").write_text(json.dumps(manifest))
        with self.assertRaises(ValueError):
            verify_release_directory(self.root)

    def test_deploy_gate_rejects_directory_symlink_and_unknown_file(self):
        self.export()
        (self.root / "unexpected").symlink_to(
            Path(self.temp.name), target_is_directory=True
        )
        with self.assertRaises(ValueError):
            verify_release_directory(self.root)
        (self.root / "unexpected").unlink()
        (self.root / "private.json").write_text("{}")
        with self.assertRaises(ValueError):
            verify_release_directory(self.root)

    def test_export_has_only_reader_artifacts_and_does_not_record_publication(self):
        manifest = self.export()
        self.assertEqual(self.store.receipts, [])
        paths = {
            str(p.relative_to(self.root)) for p in self.root.rglob("*") if p.is_file()
        }
        self.assertEqual(
            paths, {"index.html", "assets/dunder_park.jpg", "release.json"}
        )
        self.assertNotIn("MUST_NOT_PUBLISH", (self.root / "index.html").read_text())
        self.assertEqual(manifest["run_id"], self.run)
        for path, digest in manifest["files"].items():
            self.assertEqual(
                hashlib.sha256((self.root / path).read_bytes()).hexdigest(), digest
            )

    def test_empty_or_unsafely_linked_edition_cannot_replace_reader(self):
        self.store.edition["stories"][0]["sources"][0][
            "url"
        ] = "http://127.0.0.1/private"
        with self.assertRaises(ValueError):
            self.export()
        self.store.edition["stories"] = []
        with self.assertRaises(ValueError):
            self.export()
        self.assertFalse(self.root.exists())

    def test_private_paths_in_reader_text_fail_export(self):
        self.store.edition["stories"][0][
            "summary"
        ] = "See /home/example/private/config for details."
        with self.assertRaises(ValueError):
            self.export()

    def test_unexpected_existing_file_and_symlink_fail_before_writing(self):
        self.root.mkdir()
        (self.root / "review.html").write_text("private")
        with self.assertRaises(ValueError):
            self.export()
        self.assertEqual((self.root / "review.html").read_text(), "private")
        (self.root / "review.html").unlink()
        (self.root / "index.html").symlink_to(Path(self.temp.name) / "outside")
        with self.assertRaises(ValueError):
            self.export()

    def test_reexport_owns_only_manifested_files(self):
        first = self.export()
        self.assertEqual(first, self.export())
        (self.root / "extra.txt").write_text("unreviewed")
        with self.assertRaises(ValueError):
            self.export()

    def test_delivery_hash_mismatch_or_network_failure_does_not_publish(self):
        self.export()
        with patch("news.publication.fetch_public_file", return_value=b"wrong"):
            with self.assertRaises(ValueError):
                confirm_publication(
                    self.store,
                    self.run,
                    self.root / "release.json",
                    "https://example.github.io/news/",
                )
        with patch(
            "news.publication.fetch_public_file",
            side_effect=RuntimeError("Unavailable"),
        ):
            with self.assertRaises(RuntimeError):
                confirm_publication(
                    self.store,
                    self.run,
                    self.root / "release.json",
                    "https://example.github.io/news/",
                )
        self.assertEqual(self.store.receipts, [])

    def test_success_checks_every_delivered_file_before_recording(self):
        manifest = self.export()

        def fetch(url):
            path = url.split("https://example.github.io/news/", 1)[1]
            return (self.root / path).read_bytes()

        with patch("news.publication.fetch_public_file", side_effect=fetch) as request:
            receipt = confirm_publication(
                self.store,
                self.run,
                self.root / "release.json",
                "https://example.github.io/news/",
            )
        self.assertEqual(request.call_count, len(manifest["files"]) + 1)
        self.assertEqual(len(self.store.receipts), 1)
        self.assertEqual(receipt["files_verified"], len(manifest["files"]))

    def test_edited_candidate_cannot_certify_different_content_for_the_saved_run(self):
        self.export()
        page = self.root / "index.html"
        page.write_text(
            page.read_text().replace(
                "The government announced its decision.", "An entirely different claim."
            )
        )
        path = self.root / "release.json"
        manifest = json.loads(path.read_text())
        manifest["files"]["index.html"] = hashlib.sha256(page.read_bytes()).hexdigest()
        path.write_text(json.dumps(manifest))

        def fetch(url):
            return (
                self.root / url.split("https://example.github.io/news/", 1)[1]
            ).read_bytes()

        with patch("news.publication.fetch_public_file", side_effect=fetch):
            with self.assertRaises(ValueError):
                confirm_publication(
                    self.store, self.run, path, "https://example.github.io/news/"
                )
        self.assertEqual(self.store.receipts, [])

    def test_manifest_cannot_publish_another_run_or_unlisted_path(self):
        self.export()
        path = self.root / "release.json"
        data = json.loads(path.read_text())
        data["run_id"] = "another"
        path.write_text(json.dumps(data))
        with self.assertRaises(ValueError):
            confirm_publication(
                self.store, self.run, path, "https://example.github.io/news/"
            )
        self.assertEqual(self.store.receipts, [])
