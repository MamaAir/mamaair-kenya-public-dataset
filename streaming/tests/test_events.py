from __future__ import annotations

import unittest
from datetime import UTC, datetime
from pathlib import Path

from streaming.mamaair_stream.events import event_validator, iter_replay_events
from streaming.tests.helpers import dataset

FIXED_TIME = datetime(2026, 8, 5, 12, 30, 45, 123000, tzinfo=UTC)
SCHEMA = Path(__file__).resolve().parents[1] / "schema/mamaair_stream_event.schema.json"


class EventGenerationTests(unittest.TestCase):
    def events(self):
        return list(iter_replay_events(dataset(), clock=lambda: FIXED_TIME))

    def test_generation_is_deterministic(self):
        first = self.events()
        second = self.events()
        self.assertEqual([item.event for item in first], [item.event for item in second])
        self.assertEqual(first[0].event["replay_emitted_at"], "2026-08-05T12:30:45.123Z")

    def test_original_daily_values_are_preserved_exactly(self):
        source = dataset()
        generated = self.events()
        expected = {
            (trajectory["track_id"], index): record
            for trajectory in source["trajectories"]
            for index, record in enumerate(trajectory["daily_records"])
        }
        for item in generated:
            event = item.event
            key = (event["track_id"], event["trajectory_context"]["trajectory_record_sequence"])
            self.assertEqual(event["payload"], expected[key])
            self.assertIsNot(event["payload"], expected[key])

    def test_order_is_sorted_trajectory_round_robin(self):
        observed = [
            (item.event["track_id"], item.event["trajectory_context"]["trajectory_record_sequence"])
            for item in self.events()
        ]
        self.assertEqual(
            observed,
            [("WQ1-001", 0), ("WQ1-002", 0), ("WQ1-001", 1), ("WQ1-002", 1)],
        )

    def test_partition_key_is_track_id(self):
        for item in self.events():
            self.assertEqual(item.partition_key, item.event["track_id"])

    def test_generated_events_conform_to_schema(self):
        validator = event_validator(SCHEMA)
        for item in self.events():
            validator.validate(item.event)

    def test_looping_changes_iteration_and_event_id(self):
        items = list(
            iter_replay_events(dataset(), loop=True, max_events=5, clock=lambda: FIXED_TIME)
        )
        self.assertEqual(items[-1].event["replay_iteration"], 1)
        self.assertNotEqual(items[0].event["event_id"], items[-1].event["event_id"])


if __name__ == "__main__":
    unittest.main()
