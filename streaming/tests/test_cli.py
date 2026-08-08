from __future__ import annotations

import io
import json
import tempfile
import unittest
from pathlib import Path

from streaming.mamaair_stream.cli import main
from streaming.tests.helpers import write_dataset

SCHEMA = Path(__file__).resolve().parents[1] / "schema/mamaair_stream_event.schema.json"


class CliTests(unittest.TestCase):
    def test_dry_run_writes_json_lines_without_aws_client(self):
        with tempfile.TemporaryDirectory() as directory:
            dataset_path = Path(directory) / "dataset.json"
            write_dataset(dataset_path)
            stdout = io.StringIO()
            stderr = io.StringIO()

            def forbidden_client(_region):
                raise AssertionError("dry run must not create an AWS client")

            result = main(
                [
                    "--dataset",
                    str(dataset_path),
                    "--event-schema",
                    str(SCHEMA),
                    "--dry-run",
                    "--max-events",
                    "3",
                    "--events-per-second",
                    "1000000",
                ],
                stdout=stdout,
                stderr=stderr,
                client_factory=forbidden_client,
            )
            lines = stdout.getvalue().splitlines()
            self.assertEqual(result, 0)
            self.assertEqual(len(lines), 3)
            self.assertEqual(json.loads(lines[0])["track_id"], "WQ1-001")
            self.assertIn("generated=3", stderr.getvalue())
            self.assertIn("succeeded=3", stderr.getvalue())

    def test_invalid_configuration_exits_nonzero(self):
        with self.assertRaises(SystemExit) as caught:
            main(["--dry-run", "--events-per-second", "0"])
        self.assertNotEqual(caught.exception.code, 0)

    def test_aws_mode_requires_stream_and_region(self):
        with self.assertRaises(SystemExit) as caught:
            main([])
        self.assertNotEqual(caught.exception.code, 0)

    def test_checkpoint_resume_continues_without_duplicates(self):
        with tempfile.TemporaryDirectory() as directory:
            dataset_path = Path(directory) / "dataset.json"
            checkpoint_path = Path(directory) / "checkpoint.json"
            write_dataset(dataset_path)

            first_stdout = io.StringIO()
            first_result = main(
                [
                    "--dataset",
                    str(dataset_path),
                    "--event-schema",
                    str(SCHEMA),
                    "--dry-run",
                    "--max-events",
                    "3",
                    "--events-per-second",
                    "1000000",
                    "--checkpoint-file",
                    str(checkpoint_path),
                ],
                stdout=first_stdout,
                stderr=io.StringIO(),
            )
            checkpoint = json.loads(checkpoint_path.read_text(encoding="utf-8"))
            self.assertEqual(checkpoint["next_source_offset"], 3)

            second_stdout = io.StringIO()
            second_result = main(
                [
                    "--dataset",
                    str(dataset_path),
                    "--event-schema",
                    str(SCHEMA),
                    "--dry-run",
                    "--max-events",
                    "1",
                    "--events-per-second",
                    "1000000",
                    "--checkpoint-file",
                    str(checkpoint_path),
                ],
                stdout=second_stdout,
                stderr=io.StringIO(),
            )

            first_events = [json.loads(line) for line in first_stdout.getvalue().splitlines()]
            second_event = json.loads(second_stdout.getvalue())
            self.assertEqual(first_result, 0)
            self.assertEqual(second_result, 0)
            self.assertEqual(
                [event["source_sequence"] for event in first_events]
                + [second_event["source_sequence"]],
                [0, 1, 2, 3],
            )
            self.assertEqual(
                len({event["event_id"] for event in first_events + [second_event]}),
                4,
            )


if __name__ == "__main__":
    unittest.main()
