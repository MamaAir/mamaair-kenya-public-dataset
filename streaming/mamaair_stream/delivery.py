"""Kinesis serialization, order-safe batching, and bounded retries."""

from __future__ import annotations

import json
import time
from collections.abc import Callable, Iterable, Iterator
from dataclasses import dataclass
from typing import Any

MAX_BATCH_RECORDS = 500
MAX_RECORD_BYTES = 10 * 1024 * 1024
MAX_BATCH_BYTES = 10 * 1024 * 1024
MAX_PARTITION_KEY_BYTES = 256


class DeliveryError(RuntimeError):
    """Raised for an invalid batch or unusable Kinesis response."""


@dataclass(frozen=True)
class DeliveryRecord:
    data: bytes
    partition_key: str
    next_source_offset: int
    next_replay_iteration: int


@dataclass
class DeliveryStats:
    attempted: int = 0
    succeeded: int = 0
    retried: int = 0
    failed: int = 0
    api_calls: int = 0

    def add(self, other: DeliveryStats) -> None:
        self.attempted += other.attempted
        self.succeeded += other.succeeded
        self.retried += other.retried
        self.failed += other.failed
        self.api_calls += other.api_calls


def serialize_event(event: dict[str, Any]) -> bytes:
    return (json.dumps(event, ensure_ascii=True, separators=(",", ":")) + "\n").encode("utf-8")


def validate_record(record: DeliveryRecord) -> int:
    key_size = len(record.partition_key.encode("utf-8"))
    if not 1 <= key_size <= MAX_PARTITION_KEY_BYTES:
        raise DeliveryError("Partition key must contain 1-256 UTF-8 bytes")
    record_size = len(record.data) + key_size
    if record_size > MAX_RECORD_BYTES:
        raise DeliveryError(f"Kinesis record exceeds {MAX_RECORD_BYTES} bytes")
    return record_size


def ordered_batches(
    records: Iterable[DeliveryRecord],
    *,
    max_records: int = 100,
    max_bytes: int = MAX_BATCH_BYTES,
) -> Iterator[list[DeliveryRecord]]:
    """Batch without repeating a partition key in the same PutRecords call.

    Combined with synchronous retry completion before the next batch, this
    avoids submitting a later event for a trajectory before its earlier event.
    """

    if not 1 <= max_records <= MAX_BATCH_RECORDS:
        raise ValueError(f"max_records must be between 1 and {MAX_BATCH_RECORDS}")
    if not 1 <= max_bytes <= MAX_BATCH_BYTES:
        raise ValueError(f"max_bytes must be between 1 and {MAX_BATCH_BYTES}")

    batch: list[DeliveryRecord] = []
    batch_bytes = 0
    partition_keys: set[str] = set()
    for record in records:
        size = validate_record(record)
        if size > max_bytes:
            raise DeliveryError("A record exceeds the configured batch byte limit")
        if batch and (
            len(batch) >= max_records
            or batch_bytes + size > max_bytes
            or record.partition_key in partition_keys
        ):
            yield batch
            batch = []
            batch_bytes = 0
            partition_keys = set()
        batch.append(record)
        batch_bytes += size
        partition_keys.add(record.partition_key)
    if batch:
        yield batch


class KinesisBatchSender:
    def __init__(
        self,
        client: Any,
        stream_name: str,
        *,
        max_attempts: int = 5,
        backoff_base_seconds: float = 0.25,
        backoff_cap_seconds: float = 8.0,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        if not stream_name:
            raise ValueError("stream_name is required")
        if max_attempts <= 0:
            raise ValueError("max_attempts must be positive")
        if backoff_base_seconds < 0 or backoff_cap_seconds < 0:
            raise ValueError("Backoff values must be non-negative")
        self.client = client
        self.stream_name = stream_name
        self.max_attempts = max_attempts
        self.backoff_base_seconds = backoff_base_seconds
        self.backoff_cap_seconds = backoff_cap_seconds
        self.sleep = sleep

    def send(self, batch: list[DeliveryRecord]) -> DeliveryStats:
        if not batch:
            return DeliveryStats()
        if len({record.partition_key for record in batch}) != len(batch):
            raise DeliveryError("Order-safe batches may contain only one record per partition key")
        pending = list(batch)
        stats = DeliveryStats(attempted=len(batch))
        attempt = 1
        while pending:
            stats.api_calls += 1
            request = [
                {"Data": record.data, "PartitionKey": record.partition_key} for record in pending
            ]
            try:
                response = self.client.put_records(StreamName=self.stream_name, Records=request)
                entries = response.get("Records")
                if not isinstance(entries, list) or len(entries) != len(pending):
                    raise DeliveryError("Kinesis returned an invalid PutRecords response")
                failed = []
                for record, entry in zip(pending, entries):
                    if entry.get("ErrorCode"):
                        failed.append(record)
                    else:
                        stats.succeeded += 1
            except DeliveryError:
                raise
            except Exception:
                failed = pending

            if not failed:
                break
            if attempt >= self.max_attempts:
                stats.failed += len(failed)
                break
            stats.retried += len(failed)
            delay = min(
                self.backoff_cap_seconds,
                self.backoff_base_seconds * (2 ** (attempt - 1)),
            )
            if delay:
                self.sleep(delay)
            pending = failed
            attempt += 1
        return stats
