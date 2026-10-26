"""Public export is separate from private processing and frozen-run resume."""

import contextlib
import io
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch
from news.cli import main


class CliTests(unittest.TestCase):
    def setUp(self):
        # CLI behavior is under test, not the developer's ignored runtime settings.
        loader = patch("news.cli.load_dotenv")
        self.load_env = loader.start()
        self.addCleanup(loader.stop)

    def test_export_does_not_initialize_the_model(self):
        store = Mock()
        with (
            patch("news.cli.NewsStore.from_env", return_value=store),
            patch("news.cli.JsonModel.from_env") as model,
            patch(
                "news.cli.export_publication",
                return_value={"run_id": "run", "stories": 1},
            ),
            contextlib.redirect_stdout(io.StringIO()),
        ):
            self.assertEqual(main(["export", "--run", "run", "--output", "site"]), 0)
        model.assert_not_called()
        store.close.assert_called_once()

    def test_build_cannot_write_private_review_outside_local_storage(self):
        with self.assertRaises(SystemExit), contextlib.redirect_stderr(io.StringIO()):
            main(["build", "--output-root", "site"])

    def test_resume_cannot_silently_change_frozen_profile(self):
        with self.assertRaises(SystemExit), contextlib.redirect_stderr(io.StringIO()):
            main(["build", "--resume", "run", "--featured-limit", "2"])

    def test_release_gate_requires_no_private_database_or_model(self):
        with (
            patch("news.cli.NewsStore.from_env") as database,
            patch("news.cli.JsonModel.from_env") as model,
            patch("news.cli.verify_release_directory", return_value={"run_id": "run"}),
            contextlib.redirect_stdout(io.StringIO()),
        ):
            self.assertEqual(main(["verify-release"]), 0)
        database.assert_not_called()
        model.assert_not_called()

    def test_help_has_one_canonical_execution_path(self):
        output = io.StringIO()
        with contextlib.redirect_stdout(output), self.assertRaises(SystemExit):
            main(["--help"])
        self.assertIn("confirm-publication", output.getvalue())
        self.assertNotIn("MVP", output.getvalue())
