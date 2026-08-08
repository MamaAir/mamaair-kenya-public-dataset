"""Command-line orchestration for the MamaAir Kinesis replay producer."""

from __future__ import annotations

import argparse
import json
import sys
import time
from collections.abc import Iterable
from pathlib import Path
from typing import Any, TextIO

from .delivery import (
    DeliveryError,
    DeliveryRecord,
    DeliveryStats,
    KinesisBatchSender,
    ordered_batches,
    serialize_event,
)
from .events import event_validator, iter_replay_events, load_dataset, source_records

REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_DATASET = REPOSITORY_ROOT / "publication-ready/data/sample_records.json"
DEFAULT_SCHEMA = Path(__file__).resolve().parents[1] / "schema/mamaair_stream_event.schema.json"


class RateLimiter:
    def __init__(
        self, events_per_second: float, *, monotonic=time.monotonic, sleep=time.sleep
    ) -> None:
        if events_per_second <= 0:
            raise ValueError("events_per_second must be positive")
        self.events_per_second = events_per_second
        self.monotonic = monotonic
        self.sleep = sleep
        self.started = monotonic()
        self.count = 0

    def wait(self, count: int) -> None:
        self.count += count
        delay = self.started + self.count / self.events_per_second - self.monotonic()
        if delay > 0:
            self.sleep(delay)


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser(
        description="Replay MamaAir synthetic daily records to Kinesis or stdout."
    )
    result.add_argument("--dataset", type=Path, default=DEFAULT_DATASET)
    result.add_argument("--event-schema", type=Path, default=DEFAULT_SCHEMA)
    result.add_argument("--stream-name")
    result.add_argument("--region")
    result.add_argument("--events-per-second", type=float, default=10.0)
    result.add_argument("--batch-size", type=int, default=100)
    result.add_argument("--max-events", type=int)
    result.add_argument("--loop", action="store_true")
    result.add_argument(
        "--dry-run", action="store_true", help="Write JSON Lines to stdout; do not load boto3"
    )
    result.add_argument("--start-offset", type=int)
    result.add_argument("--checkpoint-file", type=Path)
    result.add_argument("--max-attempts", type=int, default=5)
    result.add_argument("--backoff-base-seconds", type=float, default=0.25)
    return result


def read_checkpoint(path: Path, dataset_id: str) -> tuple[int, int]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"Cannot read checkpoint {path}: {exc}") from exc
    if value.get("dataset_id") != dataset_id:
        raise ValueError("Checkpoint dataset_id does not match the selected dataset")
    offset = value.get("next_source_offset")
    iteration = value.get("next_replay_iteration")
    if not isinstance(offset, int) or not isinstance(iteration, int):
        raise ValueError("Checkpoint offsets must be integers")
    return offset, iteration


def write_checkpoint(path: Path, dataset_id: str, record: DeliveryRecord) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.tmp")
    value = {
        "dataset_id": dataset_id,
        "next_source_offset": record.next_source_offset,
        "next_replay_iteration": record.next_replay_iteration,
    }
    temporary.write_text(json.dumps(value, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    temporary.replace(path)


def _delivery_records(items: Iterable[Any], validator: Any) -> Iterable[DeliveryRecord]:
    for item in items:
        try:
            validator.validate(item.event)
        except Exception as exc:
            raise ValueError(
                f"Generated event {item.event.get('event_id', '<unknown>')} failed schema validation: {exc}"
            ) from exc
        yield DeliveryRecord(
            data=serialize_event(item.event),
            partition_key=item.partition_key,
            next_source_offset=item.next_source_offset,
            next_replay_iteration=item.next_replay_iteration,
        )


def _create_kinesis_client(region: str):
    try:
        import boto3
    except ImportError as exc:
        raise RuntimeError(
            "boto3 is required for AWS delivery; install streaming/requirements.txt"
        ) from exc
    return boto3.client("kinesis", region_name=region)


def _summary(stats: DeliveryStats, generated: int, stderr: TextIO) -> None:
    print(
        "Replay counters: "
        f"generated={generated} attempted={stats.attempted} succeeded={stats.succeeded} "
        f"retried={stats.retried} failed={stats.failed} api_calls={stats.api_calls}",
        file=stderr,
    )


def main(
    argv: list[str] | None = None,
    *,
    stdout: TextIO = sys.stdout,
    stderr: TextIO = sys.stderr,
    client_factory=_create_kinesis_client,
) -> int:
    args_parser = parser()
    args = args_parser.parse_args(argv)
    if args.events_per_second <= 0:
        args_parser.error("--events-per-second must be positive")
    if not 1 <= args.batch_size <= 500:
        args_parser.error("--batch-size must be between 1 and 500")
    if args.max_events is not None and args.max_events <= 0:
        args_parser.error("--max-events must be positive")
    if args.start_offset is not None and args.start_offset < 0:
        args_parser.error("--start-offset must be non-negative")
    if args.max_attempts <= 0:
        args_parser.error("--max-attempts must be positive")
    if args.backoff_base_seconds < 0:
        args_parser.error("--backoff-base-seconds must be non-negative")
    if not args.dry_run and (not args.stream_name or not args.region):
        args_parser.error("--stream-name and --region are required unless --dry-run is used")

    totals = DeliveryStats()
    generated = 0
    try:
        dataset = load_dataset(args.dataset)
        total = len(source_records(dataset))
        dataset_id = dataset["dataset_metadata"]["dataset_id"]
        start_offset = args.start_offset or 0
        start_iteration = 0
        if args.checkpoint_file and args.checkpoint_file.exists():
            if args.start_offset is not None:
                raise ValueError("Do not combine --start-offset with an existing checkpoint")
            start_offset, start_iteration = read_checkpoint(args.checkpoint_file, dataset_id)
        if not 0 <= start_offset <= total:
            raise ValueError(f"start offset must be between 0 and {total}")

        validator = event_validator(args.event_schema)
        replay_items = iter_replay_events(
            dataset,
            start_offset=start_offset,
            start_iteration=start_iteration,
            loop=args.loop,
            max_events=args.max_events,
        )
        records = _delivery_records(replay_items, validator)
        limiter = RateLimiter(args.events_per_second)
        sender = None
        if not args.dry_run:
            try:
                client = client_factory(args.region)
            except Exception as exc:
                raise RuntimeError(f"Cannot create Kinesis client: {exc}") from exc
            sender = KinesisBatchSender(
                client,
                args.stream_name,
                max_attempts=args.max_attempts,
                backoff_base_seconds=args.backoff_base_seconds,
            )

        for batch in ordered_batches(records, max_records=args.batch_size):
            generated += len(batch)
            if args.dry_run:
                for record in batch:
                    stdout.write(record.data.decode("utf-8"))
                batch_stats = DeliveryStats(attempted=len(batch), succeeded=len(batch), api_calls=0)
            else:
                batch_stats = sender.send(batch)
            totals.add(batch_stats)
            if batch_stats.failed:
                _summary(totals, generated, stderr)
                return 1
            if args.checkpoint_file:
                write_checkpoint(args.checkpoint_file, dataset_id, batch[-1])
            limiter.wait(len(batch))
        _summary(totals, generated, stderr)
        return 0
    except KeyboardInterrupt:
        _summary(totals, generated, stderr)
        print("Replay interrupted; no later batch was submitted.", file=stderr)
        return 130
    except (DeliveryError, RuntimeError, ValueError, OSError) as exc:
        print(f"Replay failed: {exc}", file=stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
