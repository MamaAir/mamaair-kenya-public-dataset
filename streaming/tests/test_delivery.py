from __future__ import annotations

import unittest

from streaming.mamaair_stream.delivery import (
    DeliveryError,
    DeliveryRecord,
    KinesisBatchSender,
    ordered_batches,
)


def record(key: str, payload: bytes = b"{}\n") -> DeliveryRecord:
    return DeliveryRecord(payload, key, 0, 0)


class FakeKinesis:
    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = []

    def put_records(self, **kwargs):
        self.calls.append(kwargs)
        return self.responses.pop(0)


class BatchingTests(unittest.TestCase):
    def test_batch_size_is_enforced(self):
        batches = list(ordered_batches([record("a"), record("b"), record("c")], max_records=2))
        self.assertEqual(
            [[item.partition_key for item in batch] for batch in batches], [["a", "b"], ["c"]]
        )

    def test_repeated_partition_starts_a_new_batch(self):
        batches = list(ordered_batches([record("a"), record("b"), record("a")], max_records=100))
        self.assertEqual(
            [[item.partition_key for item in batch] for batch in batches], [["a", "b"], ["a"]]
        )

    def test_sender_rejects_non_order_safe_batch(self):
        sender = KinesisBatchSender(FakeKinesis([]), "stream")
        with self.assertRaises(DeliveryError):
            sender.send([record("a"), record("a")])


class RetryTests(unittest.TestCase):
    def test_partial_failure_retries_only_failed_record(self):
        client = FakeKinesis(
            [
                {
                    "Records": [
                        {"SequenceNumber": "1", "ShardId": "s"},
                        {"ErrorCode": "ProvisionedThroughputExceededException"},
                    ]
                },
                {"Records": [{"SequenceNumber": "2", "ShardId": "s"}]},
            ]
        )
        sleeps = []
        sender = KinesisBatchSender(
            client,
            "stream",
            max_attempts=3,
            backoff_base_seconds=0.5,
            sleep=sleeps.append,
        )
        stats = sender.send([record("a"), record("b")])
        self.assertEqual(
            (stats.attempted, stats.succeeded, stats.retried, stats.failed), (2, 2, 1, 0)
        )
        self.assertEqual(len(client.calls), 2)
        self.assertEqual([entry["PartitionKey"] for entry in client.calls[1]["Records"]], ["b"])
        self.assertEqual(sleeps, [0.5])

    def test_exhausted_partial_failure_is_counted(self):
        failure = {"Records": [{"ErrorCode": "InternalFailure"}]}
        client = FakeKinesis([failure, failure])
        sender = KinesisBatchSender(
            client,
            "stream",
            max_attempts=2,
            backoff_base_seconds=0,
        )
        stats = sender.send([record("a")])
        self.assertEqual(
            (stats.succeeded, stats.retried, stats.failed, stats.api_calls), (0, 1, 1, 2)
        )


if __name__ == "__main__":
    unittest.main()
