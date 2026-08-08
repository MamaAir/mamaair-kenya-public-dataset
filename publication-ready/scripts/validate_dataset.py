#!/usr/bin/env python3
"""Validate the MamaAir JSON release candidate without rewriting it."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from collections import Counter, defaultdict
from collections.abc import Iterable
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

EXPECTED_DATASET_ID = "mamaair-ssa-climate-maternal-wq1"
EXPECTED_TRAJECTORY_COUNT = 75
EXPECTED_DAILY_RECORD_COUNT = 15_134
EXPECTED_WEEKLY_SUMMARY_COUNT = 2_162
EXPECTED_TRAJECTORY_HASH = "fdb7fffec1c566b559c668d4b2b39c6d740ba017430c5078c8c974103329b98a"
EXPECTED_CONTACT = "dusmikeev@mamaair.africa"
EXPECTED_MANAGER = "MamaAir.Africa"
EXPECTED_LICENSE = "MamaAir Public Data Sample License (Permissive Evaluation & Research Terms)"
EXPECTED_FORMAT = "JSON"
EXPECTED_REGISTRY_TAGS = [
    "health",
    "life sciences",
    "machine learning",
    "climate",
    "environmental",
    "sustainability",
    "synthetic data",
]
EXPECTED_START_WEEKS = {1, 8, 12, 16, 20, 24}
EXPECTED_TRAJECTORY_KEYS = {
    "track_id",
    "static_profile",
    "pregnancy_summary",
    "weekly_summaries",
    "daily_records",
}
FORBIDDEN_RECORD_KEYS = {
    "h3",
    "h3_index",
    "latitude",
    "longitude",
    "lat",
    "lon",
    "gps",
    "coordinates",
    "coordinate",
    "timestamp",
    "datetime",
    "patient_id",
    "facility_id",
    "facility_name",
    "email",
    "phone",
    "address",
}
KNOWN_COARSE_LOCATION_KEYS = {"settlement", "settlement_name", "commute_km", "commute_mode"}
PLACEHOLDER_RE = re.compile(r"\{\{[^}]+\}\}|REPLACE_WITH|\bTBD\b|\bTODO\b|\[Insert\b|\bxxx\b", re.I)


class Results:
    def __init__(self) -> None:
        self.findings: list[dict[str, Any]] = []

    def add(self, severity: str, code: str, message: str, **details: Any) -> None:
        finding = {"severity": severity, "code": code, "message": message}
        finding.update(details)
        self.findings.append(finding)

    def count(self, severity: str) -> int:
        return sum(item["severity"] == severity for item in self.findings)


def json_kind(value: Any) -> str:
    if value is None:
        return "null"
    if isinstance(value, bool):
        return "boolean"
    if isinstance(value, int):
        return "integer"
    if isinstance(value, float):
        return "number"
    if isinstance(value, str):
        return "string"
    if isinstance(value, list):
        return "array"
    if isinstance(value, dict):
        return "object"
    return type(value).__name__


def get_path(value: Any, path: str) -> tuple[bool, Any]:
    for part in path.split(".") if path else []:
        if not isinstance(value, dict) or part not in value:
            return False, None
        value = value[part]
    return True, value


def data_leaf_paths(value: Any, prefix: str = "") -> set[str]:
    result: set[str] = set()
    if isinstance(value, dict):
        for key, child in value.items():
            path = f"{prefix}.{key}" if prefix else key
            result.update(data_leaf_paths(child, path))
    else:
        result.add(prefix)
    return result


def schema_descriptors(node: Any, prefix: str = "") -> dict[str, dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {}
    if isinstance(node, dict):
        if "type" in node:
            result[prefix] = node
        else:
            for key, value in node.items():
                path = f"{prefix}.{key}" if prefix else key
                result.update(schema_descriptors(value, path))
    return result


def simple_range(text: Any) -> tuple[float, float] | None:
    match = re.fullmatch(r"\s*(-?\d+(?:\.\d+)?)\s*[–-]\s*(-?\d+(?:\.\d+)?)\s*", str(text or ""))
    return (float(match.group(1)), float(match.group(2))) if match else None


def type_matches(value: Any, source_type: str) -> bool:
    if source_type == "integer":
        return isinstance(value, int) and not isinstance(value, bool)
    if source_type == "float":
        return isinstance(value, (int, float)) and not isinstance(value, bool)
    if source_type == "boolean":
        return isinstance(value, bool)
    if source_type in {"string", "enum"}:
        return isinstance(value, str)
    if "array" in str(source_type).lower():
        return isinstance(value, list)
    return True


def compact_observed(values: list[Any]) -> dict[str, Any]:
    non_null = [value for value in values if value is not None]
    result: dict[str, Any] = {
        "types": sorted({json_kind(value) for value in values}),
        "null_count": sum(value is None for value in values),
    }
    numeric = [
        value
        for value in non_null
        if isinstance(value, (int, float)) and not isinstance(value, bool)
    ]
    if numeric and len(numeric) == len(non_null):
        result["minimum"] = min(numeric)
        result["maximum"] = max(numeric)
        unique = sorted(set(numeric))
        if len(unique) <= 20:
            result["values"] = unique
    else:
        simple = [value for value in values if isinstance(value, (str, bool)) or value is None]
        if len(simple) == len(values):
            unique = sorted(set(simple), key=repr)
            result["values"] = unique if len(unique) <= 30 else f"{len(unique)} unique values"
    return result


def contexts_for_rows(
    rows: list[tuple[dict[str, Any], str, int | None]], path: str
) -> dict[str, Any]:
    hits: list[tuple[str, int | None, Any]] = []
    for row, track_id, week in rows:
        present, value = get_path(row, path)
        if present:
            hits.append((track_id, week, value))
    values = [hit[2] for hit in hits]
    return {
        "count": len(hits),
        "observed": compact_observed(values) if values else {},
        "affected_track_ids": sorted({hit[0] for hit in hits}),
        "gestational_weeks": sorted({hit[1] for hit in hits if hit[1] is not None}),
    }


def walk_objects(
    value: Any, path: str = "", context: str = ""
) -> Iterable[tuple[str, tuple[str, ...], str]]:
    if isinstance(value, dict):
        yield path or "$", tuple(sorted(value)), context
        for key, child in value.items():
            child_path = f"{path}.{key}" if path else key
            yield from walk_objects(child, child_path, context)
    elif isinstance(value, list):
        for child in value:
            yield from walk_objects(child, f"{path}[*]", context)


def walk_keys(value: Any, path: str = "") -> Iterable[tuple[str, str, Any]]:
    if isinstance(value, dict):
        for key, child in value.items():
            child_path = f"{path}.{key}" if path else key
            yield child_path, key, child
            yield from walk_keys(child, child_path)
    elif isinstance(value, list):
        for child in value:
            yield from walk_keys(child, f"{path}[*]")


def all_strings(value: Any, path: str = "") -> Iterable[tuple[str, str]]:
    if isinstance(value, str):
        yield path, value
    elif isinstance(value, dict):
        for key, child in value.items():
            child_path = f"{path}.{key}" if path else key
            yield from all_strings(child, child_path)
    elif isinstance(value, list):
        for child in value:
            yield from all_strings(child, f"{path}[*]")


def observed_schema_errors(
    value: Any,
    schema: dict[str, Any],
    path: str = "$",
    errors: list[str] | None = None,
    limit: int = 100,
) -> list[str]:
    """Validate the generated schema subset without an external dependency."""
    if errors is None:
        errors = []
    if len(errors) >= limit:
        return errors
    expected = schema.get("type")
    allowed = [expected] if isinstance(expected, str) else list(expected or [])
    actual = json_kind(value)
    type_ok = actual in allowed or (actual == "integer" and "number" in allowed)
    if allowed and not type_ok:
        errors.append(f"{path}: expected {allowed}, observed {actual}")
        return errors
    if "enum" in schema and value not in schema["enum"]:
        errors.append(f"{path}: value is outside observed enum")
        return errors
    if isinstance(value, dict):
        properties = schema.get("properties", {})
        required = set(schema.get("required", []))
        missing = sorted(required - set(value))
        if missing:
            errors.append(f"{path}: missing required keys {missing}")
        if schema.get("additionalProperties") is False:
            extra = sorted(set(value) - set(properties))
            if extra:
                errors.append(f"{path}: extra keys {extra}")
        for key, child in value.items():
            if key in properties:
                observed_schema_errors(child, properties[key], f"{path}.{key}", errors, limit)
    elif isinstance(value, list) and isinstance(schema.get("items"), dict):
        for index, child in enumerate(value):
            observed_schema_errors(child, schema["items"], f"{path}[{index}]", errors, limit)
    return errors


def validate_source_schema(
    data: dict[str, Any], source_schema: dict[str, Any], results: Results
) -> dict[str, Any]:
    trajectories = data["trajectories"]
    roots: dict[str, tuple[list[tuple[dict[str, Any], str, int | None]], dict[str, Any]]] = {
        "static_profile": (
            [(item["static_profile"], item["track_id"], None) for item in trajectories],
            source_schema["static_profile_schema"]["fields"],
        ),
        "daily_records": (
            [
                (record, item["track_id"], record.get("gestation_week"))
                for item in trajectories
                for record in item["daily_records"]
            ],
            source_schema["daily_record_schema"]["fields"],
        ),
        "weekly_summaries": (
            [
                (record, item["track_id"], record.get("gestation_week"))
                for item in trajectories
                for record in item["weekly_summaries"]
            ],
            source_schema["weekly_summary_schema"]["fields"],
        ),
        "pregnancy_summary": (
            [(item["pregnancy_summary"], item["track_id"], None) for item in trajectories],
            source_schema["pregnancy_summary_schema"]["fields"],
        ),
    }
    report: dict[str, Any] = {}
    for root_name, (rows, fields) in roots.items():
        observed_paths = set().union(*(data_leaf_paths(row) for row, _, _ in rows))
        descriptors = schema_descriptors(fields)
        source_paths = set(descriptors)
        missing_from_source = []
        for path in sorted(observed_paths - source_paths):
            details = contexts_for_rows(rows, path)
            missing_from_source.append({"path": path, **details})
        missing_from_data = []
        for path in sorted(source_paths - observed_paths):
            affected = [track_id for _, track_id, _ in rows]
            missing_from_data.append(
                {
                    "path": path,
                    "count": len(rows),
                    "affected_track_ids": sorted(set(affected)),
                    "gestational_weeks": sorted({week for _, _, week in rows if week is not None}),
                }
            )

        if missing_from_source:
            results.add(
                "warning",
                f"SOURCE_SCHEMA_{root_name.upper()}_GAPS",
                f"{len(missing_from_source)} observed leaf fields are absent from the supplied {root_name} schema.",
                field_paths=[item["path"] for item in missing_from_source],
            )
        if missing_from_data:
            results.add(
                "warning",
                f"SOURCE_SCHEMA_{root_name.upper()}_MISPLACED_OR_ABSENT",
                f"{len(missing_from_data)} supplied schema leaf fields are not present at the documented path.",
                field_paths=[item["path"] for item in missing_from_data],
            )

        type_enum_range = []
        for path, descriptor in sorted(descriptors.items()):
            occurrences: list[tuple[str, int | None, Any]] = []
            for row, track_id, week in rows:
                present, value = get_path(row, path)
                if present:
                    occurrences.append((track_id, week, value))
            if not occurrences:
                continue
            source_type = str(descriptor.get("type", ""))
            type_hits = [item for item in occurrences if not type_matches(item[2], source_type)]
            allowed = descriptor.get("values")
            enum_hits = [
                item for item in occurrences if isinstance(allowed, list) and item[2] not in allowed
            ]
            parsed_range = simple_range(descriptor.get("range"))
            range_hits = []
            if parsed_range:
                low, high = parsed_range
                range_hits = [
                    item
                    for item in occurrences
                    if isinstance(item[2], (int, float))
                    and not isinstance(item[2], bool)
                    and not low <= item[2] <= high
                ]
            if type_hits or enum_hits or range_hits:
                combined = []
                for item in occurrences:
                    value = item[2]
                    wrong_type = not type_matches(value, source_type)
                    wrong_enum = isinstance(allowed, list) and value not in allowed
                    wrong_range = bool(
                        parsed_range
                        and isinstance(value, (int, float))
                        and not isinstance(value, bool)
                        and not parsed_range[0] <= value <= parsed_range[1]
                    )
                    if wrong_type or wrong_enum or wrong_range:
                        combined.append(item)
                detail = {
                    "path": path,
                    "source_type": source_type,
                    "source_values": allowed,
                    "source_range": descriptor.get("range"),
                    "type_difference_count": len(type_hits),
                    "enum_difference_count": len(enum_hits),
                    "range_difference_count": len(range_hits),
                    "count": len(combined),
                    "observed": compact_observed([item[2] for item in combined]),
                    "affected_track_ids": sorted({item[0] for item in combined}),
                    "gestational_weeks": sorted(
                        {item[1] for item in combined if item[1] is not None}
                    ),
                }
                type_enum_range.append(detail)
                classification = (
                    "preserved documented limitation; owner confirmed that release values "
                    "must remain unchanged"
                )
                results.add(
                    "warning",
                    "SOURCE_SCHEMA_VALUE_DIFFERENCE",
                    f"{root_name}.{path} differs from the supplied type, enum, or intended range.",
                    classification=classification,
                    **detail,
                )

        report[root_name] = {
            "observed_leaf_field_count": len(observed_paths),
            "source_schema_leaf_field_count": len(source_paths),
            "observed_fields_missing_from_source_schema": missing_from_source,
            "source_schema_fields_missing_at_observed_path": missing_from_data,
            "type_enum_range_differences": type_enum_range,
        }
    return report


def validate_dataset(data: Any, source_schema: dict[str, Any], results: Results) -> dict[str, Any]:
    facts: dict[str, Any] = {}
    if not isinstance(data, dict):
        results.add("error", "TOP_LEVEL_NOT_OBJECT", "Top-level JSON value must be an object.")
        return facts
    if set(data) != {"dataset_metadata", "trajectories"}:
        results.add(
            "error",
            "TOP_LEVEL_KEYS",
            "Top-level keys must be exactly dataset_metadata and trajectories.",
            observed_keys=sorted(data),
        )
    metadata = data.get("dataset_metadata")
    trajectories = data.get("trajectories")
    if not isinstance(metadata, dict) or not isinstance(trajectories, list):
        results.add(
            "error",
            "TOP_LEVEL_STRUCTURE",
            "dataset_metadata must be an object and trajectories an array.",
        )
        return facts

    expected_metadata = {
        "dataset_id": EXPECTED_DATASET_ID,
        "contact": EXPECTED_CONTACT,
        "managed_by": EXPECTED_MANAGER,
        "license": EXPECTED_LICENSE,
        "format": EXPECTED_FORMAT,
    }
    for key, expected in expected_metadata.items():
        if metadata.get(key) != expected:
            results.add(
                "error",
                "METADATA_INCONSISTENT",
                f"dataset_metadata.{key} does not match the confirmed release value.",
                path=f"dataset_metadata.{key}",
                expected=expected,
                observed=metadata.get(key),
            )
    if metadata.get("aws_registry_tags") != EXPECTED_REGISTRY_TAGS:
        results.add(
            "error",
            "METADATA_REGISTRY_TAGS",
            "Embedded Registry tags differ from the verified release vocabulary.",
            expected=EXPECTED_REGISTRY_TAGS,
            observed=metadata.get("aws_registry_tags"),
        )
    if metadata.get("total_trajectories") != len(trajectories):
        results.add(
            "error",
            "METADATA_TRAJECTORY_COUNT",
            "Metadata trajectory count differs from the actual array length.",
            metadata_count=metadata.get("total_trajectories"),
            actual_count=len(trajectories),
        )
    if len(trajectories) != EXPECTED_TRAJECTORY_COUNT:
        results.add(
            "error",
            "RELEASE_TRAJECTORY_COUNT",
            "Trajectory count differs from the owner-approved release.",
            expected=EXPECTED_TRAJECTORY_COUNT,
            observed=len(trajectories),
        )

    ids = [item.get("track_id") if isinstance(item, dict) else None for item in trajectories]
    blank_ids = [value for value in ids if not isinstance(value, str) or not value.strip()]
    duplicates = sorted(value for value, count in Counter(ids).items() if value and count > 1)
    if blank_ids:
        results.add(
            "error",
            "TRACK_ID_BLANK",
            "One or more track_id values are empty.",
            count=len(blank_ids),
        )
    if duplicates:
        results.add(
            "error", "TRACK_ID_DUPLICATE", "track_id values must be unique.", values=duplicates
        )

    daily_total = 0
    weekly_total = 0
    start_counter: Counter[int] = Counter()
    length_counter: Counter[int] = Counter()
    day_counter: Counter[int] = Counter()
    structural_issues = 0
    for index, trajectory in enumerate(trajectories):
        if not isinstance(trajectory, dict):
            results.add(
                "error", "TRAJECTORY_NOT_OBJECT", "Trajectory must be an object.", index=index
            )
            structural_issues += 1
            continue
        track_id = trajectory.get("track_id", f"index:{index}")
        if set(trajectory) != EXPECTED_TRAJECTORY_KEYS:
            results.add(
                "error",
                "TRAJECTORY_SECTIONS",
                "Trajectory sections differ from the required set.",
                track_id=track_id,
                missing=sorted(EXPECTED_TRAJECTORY_KEYS - set(trajectory)),
                extra=sorted(set(trajectory) - EXPECTED_TRAJECTORY_KEYS),
            )
            structural_issues += 1
            continue
        daily = trajectory["daily_records"]
        weekly = trajectory["weekly_summaries"]
        summary = trajectory["pregnancy_summary"]
        if (
            not isinstance(daily, list)
            or not isinstance(weekly, list)
            or not isinstance(summary, dict)
        ):
            results.add(
                "error",
                "TRAJECTORY_SECTION_TYPES",
                "Daily, weekly, or pregnancy summary has the wrong type.",
                track_id=track_id,
            )
            structural_issues += 1
            continue
        overview = summary.get("trajectory_overview")
        if not isinstance(overview, dict):
            results.add(
                "error",
                "TRAJECTORY_OVERVIEW",
                "Missing pregnancy_summary.trajectory_overview.",
                track_id=track_id,
            )
            structural_issues += 1
            continue
        start = overview.get("starting_gestation_week")
        if start not in EXPECTED_START_WEEKS:
            results.add(
                "error",
                "START_WEEK",
                "Unexpected starting gestational week.",
                track_id=track_id,
                observed=start,
            )
            structural_issues += 1
            continue
        expected_weeks = list(range(start, 41))
        weekly_weeks = [item.get("gestation_week") for item in weekly if isinstance(item, dict)]
        daily_weeks = [item.get("gestation_week") for item in daily if isinstance(item, dict)]
        checks = {
            "weekly gestational coverage": weekly_weeks == expected_weeks,
            "daily gestational coverage": sorted(set(daily_weeks)) == expected_weeks,
            "daily count equals tracked weeks x 7": len(daily) == len(weekly) * 7,
            "weekly summary count equals tracked weeks": len(weekly) == len(expected_weeks),
            "daily and weekly week sets agree": set(daily_weeks) == set(weekly_weeks),
            "cumulative pregnancy days are sequential": [
                item.get("cumulative_pregnancy_day") for item in daily
            ]
            == list(range(1, len(daily) + 1)),
            "day_of_week cycles from 1 to 7": [item.get("day_of_week") for item in daily]
            == [offset % 7 + 1 for offset in range(len(daily))],
            "weekly week_number is sequential tracking ordinal": [
                item.get("week_number") for item in weekly
            ]
            == list(range(1, len(weekly) + 1)),
            "overview weeks_tracked matches": overview.get("weeks_tracked") == len(weekly),
        }
        failed = [label for label, passed in checks.items() if not passed]
        if failed:
            results.add(
                "error",
                "TEMPORAL_COVERAGE",
                "Trajectory temporal checks failed.",
                track_id=track_id,
                checks=failed,
            )
            structural_issues += len(failed)
        daily_total += len(daily)
        weekly_total += len(weekly)
        start_counter[start] += 1
        length_counter[len(weekly)] += 1
        day_counter[len(daily)] += 1

    object_keysets: dict[str, set[tuple[str, ...]]] = defaultdict(set)
    for trajectory in trajectories:
        if isinstance(trajectory, dict):
            for path, keys, _ in walk_objects(
                trajectory, "trajectories[*]", str(trajectory.get("track_id"))
            ):
                object_keysets[path].add(keys)
    inconsistent = {
        path: [list(keys) for keys in sorted(keysets)]
        for path, keysets in object_keysets.items()
        if len(keysets) > 1
    }
    if inconsistent:
        results.add(
            "error",
            "INCONSISTENT_RECORD_STRUCTURES",
            "Object key sets vary across records.",
            paths=inconsistent,
        )

    forbidden = []
    coarse = []
    for trajectory in trajectories:
        if not isinstance(trajectory, dict):
            continue
        for path, key, value in walk_keys(trajectory, "trajectories[*]"):
            lowered = key.lower()
            if lowered in FORBIDDEN_RECORD_KEYS:
                forbidden.append(path)
            if lowered in KNOWN_COARSE_LOCATION_KEYS:
                coarse.append(path)
    if forbidden:
        results.add(
            "error",
            "UNEXPECTED_SENSITIVE_OR_LOCATION_KEYS",
            "Forbidden H3, coordinate, timestamp, identifier, or facility keys are present.",
            field_paths=sorted(set(forbidden)),
        )
    results.add(
        "warning",
        "COARSE_LOCATION_FIELDS_PRESENT",
        "Only named coarse settlement and commute fields were found; these are not exact GPS traces.",
        field_paths=sorted(set(coarse)),
    )
    if any(
        key == "race"
        for trajectory in trajectories
        if isinstance(trajectory, dict)
        for _, key, _ in walk_keys(trajectory)
    ):
        results.add(
            "warning",
            "SYNTHETIC_DEMOGRAPHIC_ATTRIBUTE",
            "The synthetic static profile includes a race field; representativeness and downstream bias require evaluation.",
            path="trajectories[*].static_profile.race",
        )

    if daily_total != EXPECTED_DAILY_RECORD_COUNT:
        results.add(
            "error",
            "RELEASE_DAILY_RECORD_COUNT",
            "Daily-record count differs from the owner-approved release.",
            expected=EXPECTED_DAILY_RECORD_COUNT,
            observed=daily_total,
        )
    if weekly_total != EXPECTED_WEEKLY_SUMMARY_COUNT:
        results.add(
            "error",
            "RELEASE_WEEKLY_SUMMARY_COUNT",
            "Weekly-summary count differs from the owner-approved release.",
            expected=EXPECTED_WEEKLY_SUMMARY_COUNT,
            observed=weekly_total,
        )
    trajectory_bytes = json.dumps(trajectories, ensure_ascii=True, separators=(",", ":")).encode(
        "utf-8"
    )
    observed_trajectory_hash = hashlib.sha256(trajectory_bytes).hexdigest()
    if observed_trajectory_hash != EXPECTED_TRAJECTORY_HASH:
        results.add(
            "error",
            "TRAJECTORY_VALUE_HASH",
            "Canonical trajectory-value hash differs from the approved release.",
            expected=EXPECTED_TRAJECTORY_HASH,
            observed=observed_trajectory_hash,
        )

    placeholders = [path for path, value in all_strings(data) if PLACEHOLDER_RE.search(value)]
    if placeholders:
        results.add(
            "error",
            "DATA_PLACEHOLDERS",
            "Placeholder text remains in the release dataset.",
            field_paths=sorted(set(placeholders)),
        )

    source_metadata = source_schema.get("schema_metadata", {})
    if source_metadata.get("contact") != EXPECTED_CONTACT:
        results.add(
            "warning",
            "PRESERVED_SOURCE_SCHEMA_CONTACT",
            "The byte-preserved custom schema contains the superseded contact; cleaned public metadata uses the confirmed contact.",
            path="schema_metadata.contact",
            observed=source_metadata.get("contact"),
            expected=EXPECTED_CONTACT,
        )

    facts.update(
        {
            "dataset_id": metadata.get("dataset_id"),
            "top_level_type": "object",
            "top_level_keys": sorted(data),
            "trajectory_count": len(trajectories),
            "daily_record_count": daily_total,
            "weekly_summary_count": weekly_total,
            "trajectory_value_hash": observed_trajectory_hash,
            "unique_track_id_count": len(set(ids)),
            "starting_week_distribution": {
                str(key): value for key, value in sorted(start_counter.items())
            },
            "tracked_week_length_distribution": {
                str(key): value for key, value in sorted(length_counter.items())
            },
            "daily_record_length_distribution": {
                str(key): value for key, value in sorted(day_counter.items())
            },
            "structural_or_temporal_issue_count": structural_issues,
            "h3_keys_found": 0,
            "raw_coordinate_keys_found": 0,
            "timestamp_keys_found": 0,
        }
    )
    return facts


def write_report(path: Path, report: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        json.dump(report, handle, ensure_ascii=False, indent=2)
        handle.write("\n")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("dataset", type=Path)
    parser.add_argument("--source-schema", type=Path, required=True)
    parser.add_argument("--observed-schema", type=Path)
    parser.add_argument("--report", type=Path, required=True)
    args = parser.parse_args()
    results = Results()

    try:
        with args.dataset.open("r", encoding="utf-8") as handle:
            data = json.load(handle)
    except (OSError, json.JSONDecodeError) as exc:
        results.add("error", "JSON_PARSE", f"Dataset could not be parsed: {exc}")
        report = {
            "validated_at_utc": datetime.now(UTC).isoformat(),
            "dataset": str(args.dataset),
            "summary": {"errors": 1, "warnings": 0, "owner_decisions": 0},
            "findings": results.findings,
        }
        write_report(args.report, report)
        print(f"ERROR: {exc}")
        return 1
    try:
        with args.source_schema.open("r", encoding="utf-8") as handle:
            source_schema = json.load(handle)
    except (OSError, json.JSONDecodeError) as exc:
        results.add("error", "SOURCE_SCHEMA_PARSE", f"Source schema could not be parsed: {exc}")
        source_schema = {}

    facts = validate_dataset(data, source_schema, results) if source_schema else {}
    schema_diff = (
        validate_source_schema(data, source_schema, results) if facts and source_schema else {}
    )

    if args.observed_schema:
        try:
            with args.observed_schema.open("r", encoding="utf-8") as handle:
                observed_schema = json.load(handle)
            if observed_schema.get("$schema") != "https://json-schema.org/draft/2020-12/schema":
                results.add(
                    "error",
                    "OBSERVED_SCHEMA_DRAFT",
                    "Observed schema is not declared as Draft 2020-12.",
                )
            conformance_errors = observed_schema_errors(data, observed_schema)
            if conformance_errors:
                results.add(
                    "error",
                    "OBSERVED_SCHEMA_CONFORMANCE",
                    "Release data does not conform to the generated observed schema.",
                    examples=conformance_errors,
                )
            elif facts:
                facts["observed_schema_conformance"] = "pass"
        except (OSError, json.JSONDecodeError) as exc:
            results.add(
                "error", "OBSERVED_SCHEMA_PARSE", f"Observed schema could not be parsed: {exc}"
            )

    summary = {
        "errors": results.count("error"),
        "warnings": results.count("warning"),
        "owner_decisions": results.count("owner_decision"),
    }
    report = {
        "validated_at_utc": datetime.now(UTC).isoformat(),
        "dataset": str(args.dataset),
        "source_schema": str(args.source_schema),
        "observed_schema": str(args.observed_schema) if args.observed_schema else None,
        "summary": summary,
        "facts": facts,
        "schema_diff": schema_diff,
        "findings": results.findings,
    }
    write_report(args.report, report)

    print("MamaAir dataset validation")
    print(f"  trajectories: {facts.get('trajectory_count', 'n/a')}")
    print(f"  daily records: {facts.get('daily_record_count', 'n/a')}")
    print(f"  weekly summaries: {facts.get('weekly_summary_count', 'n/a')}")
    print(f"  errors: {summary['errors']}")
    print(f"  warnings: {summary['warnings']}")
    print(f"  owner decisions: {summary['owner_decisions']}")
    for finding in results.findings:
        print(f"  [{finding['severity'].upper()}] {finding['code']}: {finding['message']}")
    print(f"  JSON report: {args.report}")
    return 1 if summary["errors"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
