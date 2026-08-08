"""Deterministic transformation of MamaAir daily records into replay events."""

from __future__ import annotations

import copy
import hashlib
import json
from collections.abc import Callable, Iterator
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

EVENT_SCHEMA_VERSION = "1.0.0"
EXPECTED_DATASET_ID = "mamaair-ssa-climate-maternal-wq1"


@dataclass(frozen=True)
class SourceRecord:
    """A daily record plus its deterministic position and trajectory context."""

    source_sequence: int
    trajectory_sequence: int
    trajectory_record_sequence: int
    track_id: str
    daily_record: dict[str, Any]
    static_profile: dict[str, Any]
    trajectory_overview: dict[str, Any]


@dataclass(frozen=True)
class ReplayItem:
    """Generated event and the checkpoint that follows it."""

    event: dict[str, Any]
    partition_key: str
    next_source_offset: int
    next_replay_iteration: int


def utc_now() -> datetime:
    return datetime.now(UTC)


def load_dataset(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        data = json.load(handle)
    if not isinstance(data, dict) or not isinstance(data.get("dataset_metadata"), dict):
        raise ValueError("Dataset must contain a dataset_metadata object")
    if data["dataset_metadata"].get("dataset_id") != EXPECTED_DATASET_ID:
        raise ValueError("Unexpected dataset_id")
    if not isinstance(data.get("trajectories"), list) or not data["trajectories"]:
        raise ValueError("Dataset must contain at least one trajectory")
    return data


def source_records(dataset: dict[str, Any]) -> list[SourceRecord]:
    """Return a deterministic, order-safe replay sequence.

    Trajectories are sorted by track_id. Records are then interleaved one daily
    position at a time. This preserves order within every trajectory while
    allowing a PutRecords batch to contain at most one record per partition key.
    """

    raw_trajectories = dataset["trajectories"]
    if any(not isinstance(item, dict) for item in raw_trajectories):
        raise ValueError("Every trajectory must be an object")
    if any(not isinstance(item.get("daily_records"), list) for item in raw_trajectories):
        raise ValueError("Every trajectory must contain a daily_records array")
    trajectories = sorted(raw_trajectories, key=lambda item: str(item.get("track_id", "")))
    track_ids = [item.get("track_id") for item in trajectories]
    if any(not isinstance(value, str) or not value for value in track_ids):
        raise ValueError("Every trajectory must have a non-empty track_id")
    if len(set(track_ids)) != len(track_ids):
        raise ValueError("track_id values must be unique")

    maximum_length = max(len(item.get("daily_records", [])) for item in trajectories)
    result: list[SourceRecord] = []
    for record_sequence in range(maximum_length):
        for trajectory_sequence, trajectory in enumerate(trajectories):
            daily_records = trajectory.get("daily_records")
            if not isinstance(daily_records, list):
                raise ValueError(f"{trajectory['track_id']} daily_records must be an array")
            if record_sequence >= len(daily_records):
                continue
            daily_record = daily_records[record_sequence]
            overview = trajectory.get("pregnancy_summary", {}).get("trajectory_overview")
            if not isinstance(daily_record, dict) or not isinstance(overview, dict):
                raise ValueError(f"{trajectory['track_id']} contains invalid record context")
            static_profile = trajectory.get("static_profile")
            if not isinstance(static_profile, dict):
                raise ValueError(f"{trajectory['track_id']} static_profile must be an object")
            result.append(
                SourceRecord(
                    source_sequence=len(result),
                    trajectory_sequence=trajectory_sequence,
                    trajectory_record_sequence=record_sequence,
                    track_id=trajectory["track_id"],
                    daily_record=daily_record,
                    static_profile=static_profile,
                    trajectory_overview=overview,
                )
            )
    return result


def deterministic_event_id(dataset_id: str, source_sequence: int, replay_iteration: int) -> str:
    identity = f"{dataset_id}\0{source_sequence}\0{replay_iteration}".encode()
    return hashlib.sha256(identity).hexdigest()


def _utc_timestamp(clock: Callable[[], datetime]) -> str:
    value = clock()
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("Replay clock must return a timezone-aware datetime")
    return value.astimezone(UTC).isoformat(timespec="milliseconds").replace("+00:00", "Z")


def build_event(
    dataset_id: str,
    source: SourceRecord,
    replay_iteration: int,
    clock: Callable[[], datetime] = utc_now,
) -> dict[str, Any]:
    payload = copy.deepcopy(source.daily_record)
    required = ["gestation_week", "day_of_week", "cumulative_pregnancy_day"]
    missing = [field for field in required if field not in payload]
    if missing:
        raise ValueError(f"Daily record is missing required envelope fields: {missing}")
    return {
        "schema_version": EVENT_SCHEMA_VERSION,
        "event_id": deterministic_event_id(dataset_id, source.source_sequence, replay_iteration),
        "dataset_id": dataset_id,
        "track_id": source.track_id,
        "gestation_week": payload["gestation_week"],
        "day_of_week": payload["day_of_week"],
        "cumulative_pregnancy_day": payload["cumulative_pregnancy_day"],
        "source_sequence": source.source_sequence,
        "replay_iteration": replay_iteration,
        "replay_emitted_at": _utc_timestamp(clock),
        "replay_metadata": {
            "kind": "synthetic_dataset_replay",
            "is_replay": True,
            "is_clinical_timestamp": False,
        },
        "trajectory_context": {
            "trajectory_sequence": source.trajectory_sequence,
            "trajectory_record_sequence": source.trajectory_record_sequence,
            "starting_gestation_week": source.trajectory_overview.get("starting_gestation_week"),
            "weeks_tracked": source.trajectory_overview.get("weeks_tracked"),
            "static_profile": copy.deepcopy(source.static_profile),
            "trajectory_overview": copy.deepcopy(source.trajectory_overview),
        },
        "payload": payload,
    }


def iter_replay_events(
    dataset: dict[str, Any],
    *,
    start_offset: int = 0,
    start_iteration: int = 0,
    loop: bool = False,
    max_events: int | None = None,
    clock: Callable[[], datetime] = utc_now,
) -> Iterator[ReplayItem]:
    records = source_records(dataset)
    total = len(records)
    if not 0 <= start_offset <= total:
        raise ValueError(f"start_offset must be between 0 and {total}")
    if start_iteration < 0:
        raise ValueError("start_iteration must be non-negative")
    if max_events is not None and max_events <= 0:
        raise ValueError("max_events must be positive")
    if start_offset == total:
        if not loop:
            return
        start_offset = 0
        start_iteration += 1

    metadata = dataset["dataset_metadata"]
    dataset_id = metadata["dataset_id"]
    emitted = 0
    iteration = start_iteration
    offset = start_offset
    while True:
        for source in records[offset:]:
            next_offset = source.source_sequence + 1
            next_iteration = iteration
            if next_offset == total:
                next_offset = 0 if loop else total
                next_iteration = iteration + 1 if loop else iteration
            yield ReplayItem(
                event=build_event(dataset_id, source, iteration, clock),
                partition_key=source.track_id,
                next_source_offset=next_offset,
                next_replay_iteration=next_iteration,
            )
            emitted += 1
            if max_events is not None and emitted >= max_events:
                return
        if not loop:
            return
        iteration += 1
        offset = 0


def event_validator(schema_path: Path):
    try:
        from jsonschema import Draft202012Validator, FormatChecker
    except ImportError as exc:
        raise RuntimeError("jsonschema is required; install streaming/requirements.txt") from exc
    with schema_path.open("r", encoding="utf-8") as handle:
        schema = json.load(handle)
    try:
        Draft202012Validator.check_schema(schema)
        return Draft202012Validator(schema, format_checker=FormatChecker())
    except Exception as exc:
        raise RuntimeError(f"Invalid stream-event schema: {exc}") from exc
