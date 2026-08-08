#!/usr/bin/env python3
"""Publish and read back a small ordered synthetic replay sequence."""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path

from deployment.aws_preflight import require_value, run_preflight
from streaming.mamaair_stream.delivery import DeliveryRecord, KinesisBatchSender, serialize_event
from streaming.mamaair_stream.events import event_validator, iter_replay_events, load_dataset

ROOT = Path(__file__).resolve().parents[1]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--dataset", type=Path, default=ROOT / "publication-ready/data/sample_records.json"
    )
    parser.add_argument(
        "--event-schema",
        type=Path,
        default=ROOT / "streaming/schema/mamaair_stream_event.schema.json",
    )
    parser.add_argument("--count", type=int, default=3)
    parser.add_argument("--timeout-seconds", type=int, default=60)
    parser.add_argument("--dataset-version", default=os.getenv("DATASET_VERSION", "v1"))
    parser.add_argument("--expected-account-id", default=os.getenv("EXPECTED_AWS_ACCOUNT_ID"))
    parser.add_argument("--region", default=os.getenv("AWS_REGION"))
    parser.add_argument("--bucket-name", default=os.getenv("PUBLIC_BUCKET_NAME"))
    parser.add_argument("--stream-name", default=os.getenv("KINESIS_STREAM_NAME"))
    parser.add_argument(
        "--deployment-authorized", default=os.getenv("MAMAAIR_DEPLOYMENT_AUTHORIZED")
    )
    parser.add_argument("--execute", action="store_true")
    args = parser.parse_args(argv)
    if args.count <= 1 or args.timeout_seconds <= 0:
        parser.error("--count must exceed 1 and --timeout-seconds must be positive")
    if not args.execute:
        print(
            "Dry run only. Add --execute after authorization to publish and read back smoke records."
        )
        return 0

    try:
        expected_account_id = require_value(args.expected_account_id, "EXPECTED_AWS_ACCOUNT_ID")
        region = require_value(args.region, "AWS_REGION")
        bucket_name = require_value(args.bucket_name, "PUBLIC_BUCKET_NAME")
        stream_name = require_value(args.stream_name, "KINESIS_STREAM_NAME")
        authorization = require_value(args.deployment_authorized, "MAMAAIR_DEPLOYMENT_AUTHORIZED")
        run_preflight(
            expected_account_id=expected_account_id,
            region=region,
            bucket_name=bucket_name,
            stream_name=stream_name,
            dataset_version=args.dataset_version,
            deployment_authorized=authorization,
        )
        import boto3

        client = boto3.client("kinesis", region_name=region)
        summary = client.describe_stream_summary(StreamName=stream_name)["StreamDescriptionSummary"]
        if summary["StreamStatus"] != "ACTIVE":
            raise RuntimeError(f"Kinesis stream is {summary['StreamStatus']}, not ACTIVE")

        iterators = []
        paginator = client.get_paginator("list_shards")
        for page in paginator.paginate(StreamName=stream_name):
            for shard in page["Shards"]:
                response = client.get_shard_iterator(
                    StreamName=stream_name,
                    ShardId=shard["ShardId"],
                    ShardIteratorType="LATEST",
                )
                iterators.append(response["ShardIterator"])

        dataset = load_dataset(args.dataset)
        first_track = min(item["track_id"] for item in dataset["trajectories"])
        validator = event_validator(args.event_schema)
        selected = []
        for item in iter_replay_events(dataset):
            if item.partition_key == first_track:
                validator.validate(item.event)
                selected.append(item)
                if len(selected) == args.count:
                    break
        if len(selected) != args.count:
            raise RuntimeError("Dataset did not contain enough records for the smoke sequence")

        sender = KinesisBatchSender(client, stream_name)
        for item in selected:
            record = DeliveryRecord(
                serialize_event(item.event),
                item.partition_key,
                item.next_source_offset,
                item.next_replay_iteration,
            )
            stats = sender.send([record])
            if stats.failed or stats.succeeded != 1:
                raise RuntimeError("Smoke-test record delivery failed")

        expected_ids = [item.event["event_id"] for item in selected]
        observed = {}
        observed_order = []
        deadline = time.monotonic() + args.timeout_seconds
        while time.monotonic() < deadline and len(observed) < len(expected_ids):
            next_iterators = []
            for iterator in iterators:
                response = client.get_records(ShardIterator=iterator, Limit=1000)
                next_iterators.append(response["NextShardIterator"])
                for record in response["Records"]:
                    event = json.loads(record["Data"])
                    event_id = event.get("event_id")
                    if event_id in expected_ids and event_id not in observed:
                        observed[event_id] = event
                        observed_order.append(event_id)
            iterators = next_iterators
            if len(observed) < len(expected_ids):
                time.sleep(1)
        if len(observed) != len(expected_ids):
            missing = [value for value in expected_ids if value not in observed]
            raise RuntimeError(f"Timed out reading smoke records: {missing}")
        if observed_order != expected_ids:
            raise RuntimeError(f"Smoke records arrived out of trajectory order: {observed_order}")
        observed_sequence = [observed[value]["source_sequence"] for value in observed_order]
        expected_sequence = [item.event["source_sequence"] for item in selected]
        if observed_sequence != expected_sequence:
            raise RuntimeError("Smoke records were not read back in expected trajectory order")
        print(
            f"Kinesis smoke test PASS: stream ACTIVE; {len(selected)} records published and read back"
        )
        print(f"  track_id: {first_track}")
        print(f"  source sequence: {expected_sequence}")
        print("  resources were retained")
        return 0
    except (OSError, RuntimeError, ValueError) as exc:
        print(f"Kinesis smoke test FAIL: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
