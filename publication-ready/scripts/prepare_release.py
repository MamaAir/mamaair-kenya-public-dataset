#!/usr/bin/env python3
"""Build deterministic release data, observed schema, and data dictionary.

The source files are read-only inputs. The release copy normalizes only confirmed
public metadata; trajectory and record values are not modified.
"""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
from collections import defaultdict
from collections.abc import Iterable
from pathlib import Path
from typing import Any

PUBLIC_CONTACT = "dusmikeev@mamaair.africa"
PUBLIC_MANAGER = "MamaAir.Africa"
PUBLIC_LICENSE = "MamaAir Public Data Sample License (Permissive Evaluation & Research Terms)"
EXPECTED_TRAJECTORY_HASH = "fdb7fffec1c566b559c668d4b2b39c6d740ba017430c5078c8c974103329b98a"
REGISTRY_TAGS = [
    "health",
    "life sciences",
    "machine learning",
    "climate",
    "environmental",
    "sustainability",
    "synthetic data",
]

SCHEMA_GAP_NOTES = {
    "trajectories[*].static_profile.household.co_risk_level": "Absent from the supplied custom generation schema.",
    "trajectories[*].static_profile.household.settlement": "Absent from the supplied custom generation schema.",
    "trajectories[*].static_profile.household.structure_type": "Absent from the supplied custom generation schema.",
    "trajectories[*].static_profile.household.water_access_score": "Absent from the supplied custom generation schema.",
    "trajectories[*].daily_records[*].behavioral.nudge_complied": "Absent from the supplied custom generation schema.",
    "trajectories[*].daily_records[*].behavioral.nudge_sent": "Absent from the supplied custom generation schema.",
    "trajectories[*].daily_records[*].quality_flags.completeness_index": "Absent from the supplied custom generation schema.",
    "trajectories[*].daily_records[*].quality_flags.missingness_flags": "Absent from the supplied custom generation schema.",
    "trajectories[*].daily_records[*].quality_flags.synthetic_confidence": "Absent from the supplied custom generation schema.",
    "trajectories[*].daily_records[*].trimester_label": "Absent from the supplied custom generation schema.",
    "trajectories[*].daily_records[*].workload_activity.is_workday": "Absent from the supplied custom generation schema.",
    "trajectories[*].pregnancy_summary.trajectory_overview.trajectory_arc": "Supplied schema places this field at pregnancy_summary.trajectory_arc instead of under trajectory_overview.",
    "trajectories[*].daily_records[*].anc_tracking.skip_reason": "JSON null is observed, while the supplied enum lists the literal string 'null'.",
    "trajectories[*].daily_records[*].nutrition_hydration.meals_per_day": "Two values are 4; the supplied intended range is 1-3.",
    "trajectories[*].daily_records[*].nutrition_hydration.fluid_intake_ml": "Twenty-one values are below the supplied intended minimum of 400 mL.",
    "trajectories[*].daily_records[*].mpesa_micro_economy.avg_transaction_kes": "511 values are 0; the supplied intended minimum is 10 KES.",
    "trajectories[*].daily_records[*].clinical_markers.bp_systolic_mmhg": "Thirty-eight values are outside the supplied intended 90-170 mmHg range.",
}


def json_type(value: Any) -> str:
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
    raise TypeError(f"Unsupported JSON value: {type(value)!r}")


def normalized_types(values: Iterable[Any]) -> list[str]:
    types = {json_type(value) for value in values}
    if "number" in types and "integer" in types:
        types.remove("integer")
    order = ["null", "boolean", "integer", "number", "string", "array", "object"]
    return [item for item in order if item in types]


def infer_schema(values: list[Any]) -> dict[str, Any]:
    """Infer a structural Draft 2020-12 schema from every observed value."""
    types = normalized_types(values)
    schema: dict[str, Any] = {"type": types[0] if len(types) == 1 else types}
    non_null = [value for value in values if value is not None]
    non_null_types = normalized_types(non_null) if non_null else []

    if non_null and non_null_types == ["object"]:
        keys = sorted({key for value in non_null for key in value})
        schema["properties"] = {
            key: infer_schema([value[key] for value in non_null if key in value]) for key in keys
        }
        required = [key for key in keys if all(key in value for value in non_null)]
        if required:
            schema["required"] = required
        schema["additionalProperties"] = False
    elif non_null and non_null_types == ["array"]:
        items = [item for value in non_null for item in value]
        schema["items"] = infer_schema(items) if items else {}
        lengths = [len(value) for value in non_null]
        schema["x-observed-min-items"] = min(lengths)
        schema["x-observed-max-items"] = max(lengths)
    else:
        numeric = [
            value
            for value in non_null
            if isinstance(value, (int, float)) and not isinstance(value, bool)
        ]
        if numeric and len(numeric) == len(non_null):
            schema["x-observed-minimum"] = min(numeric)
            schema["x-observed-maximum"] = max(numeric)
        hashable = [value for value in values if isinstance(value, (str, bool)) or value is None]
        if len(hashable) == len(values):
            unique = sorted(set(hashable), key=lambda value: (value is not None, repr(value)))
            if len(unique) <= 50:
                schema["enum"] = unique
    return schema


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


def source_descriptor_map(source_schema: dict[str, Any]) -> dict[str, dict[str, Any]]:
    mappings = [
        ("trajectories[*].static_profile", source_schema["static_profile_schema"]["fields"]),
        ("trajectories[*].daily_records[*]", source_schema["daily_record_schema"]["fields"]),
        ("trajectories[*].weekly_summaries[*]", source_schema["weekly_summary_schema"]["fields"]),
        ("trajectories[*].pregnancy_summary", source_schema["pregnancy_summary_schema"]["fields"]),
    ]
    result: dict[str, dict[str, Any]] = {}
    for base, fields in mappings:
        for path, descriptor in schema_descriptors(fields).items():
            result[f"{base}.{path}"] = descriptor
    # Preserve the supplied misplaced descriptor as evidence while mapping its
    # content to the observed field for dictionary purposes.
    misplaced = result.get("trajectories[*].pregnancy_summary.trajectory_arc")
    if misplaced:
        result["trajectories[*].pregnancy_summary.trajectory_overview.trajectory_arc"] = misplaced
    return result


def record_observations(value: Any, observations: dict[str, list[Any]], path: str = "") -> None:
    if path:
        observations[path].append(value)
    if isinstance(value, dict):
        for key, child in value.items():
            child_path = f"{path}.{key}" if path else key
            record_observations(child, observations, child_path)
    elif isinstance(value, list):
        for child in value:
            if isinstance(child, dict):
                record_observations(child, observations, f"{path}[*]")


def descriptor_description(descriptor: dict[str, Any] | None, path: str) -> tuple[str, str, str]:
    if path == "trajectories[*].track_id":
        return (
            "Unique synthetic sequential record identifier; described as decoupled from real patient databases.",
            "Sourced from the supplied data dictionary.",
            "",
        )
    if descriptor is None:
        if path.endswith("[*]") or path in {"dataset_metadata", "trajectories"}:
            return ("Structural container observed in the JSON.", "Inferred from structure", "")
        return (
            "No field-level description was found in the supplied custom schema.",
            "Not sourced",
            "",
        )
    for key, label in [
        ("description", ""),
        ("note", "Source note: "),
        ("interpretation", "Source interpretation: "),
        ("logic", "Source logic: "),
        ("formula", "Source formula: "),
        ("generation", "Source generation rule: "),
    ]:
        if key in descriptor:
            text = f"{label}{descriptor[key]}"
            break
    else:
        text = "Field is defined in the supplied custom generation schema."
    unit = str(descriptor.get("unit", ""))
    return (text, "Sourced: generation_logic.source.json", unit)


def summarize_values(values: list[Any]) -> tuple[str, str, str, str, str]:
    types = normalized_types(values)
    type_text = " | ".join(types)
    nullable = "Yes" if any(value is None for value in values) else "No"
    non_null = [value for value in values if value is not None]
    minimum = maximum = ""
    enum = ""
    if non_null and all(
        isinstance(value, (int, float)) and not isinstance(value, bool) for value in non_null
    ):
        minimum = str(min(non_null))
        maximum = str(max(non_null))
    elif non_null and all(isinstance(value, list) for value in non_null):
        items = [item for value in non_null for item in value]
        numeric_items = [
            item for item in items if isinstance(item, (int, float)) and not isinstance(item, bool)
        ]
        if items and len(numeric_items) == len(items):
            minimum = str(min(numeric_items))
            maximum = str(max(numeric_items))
        simple_items = [item for item in items if isinstance(item, (str, bool)) or item is None]
        if items and len(simple_items) == len(items) and len(set(simple_items)) <= 20:
            enum = ", ".join(
                json.dumps(item, ensure_ascii=False) for item in sorted(set(simple_items), key=repr)
            )
    else:
        simple = [value for value in values if isinstance(value, (str, bool)) or value is None]
        if len(simple) == len(values):
            unique = sorted(set(simple), key=repr)
            enum = (
                ", ".join(json.dumps(item, ensure_ascii=False) for item in unique)
                if len(unique) <= 20
                else f"{len(unique)} unique observed values"
            )
    return type_text, nullable, minimum, maximum, enum


def markdown_cell(value: Any, limit: int = 240) -> str:
    text = " ".join(str(value).split())
    if len(text) > limit:
        text = text[: limit - 1] + "..."
    return text.replace("|", "\\|") or "-"


def validate_triage_crosswalk(triage_crosswalk: dict[str, Any], observed_paths: set[str]) -> None:
    classes = triage_crosswalk.get("classes")
    if not isinstance(classes, list) or [item.get("class_number") for item in classes] != [
        1,
        2,
        3,
        4,
    ]:
        raise ValueError("Triage crosswalk must contain Classes 1-4 in order")
    fields = [field for item in classes for field in item.get("fields", [])]
    if len(fields) != 20 or len({field.get("source_field") for field in fields}) != 20:
        raise ValueError("Triage crosswalk must contain 20 unique source fields")
    allowed_statuses = {"Exact", "Related proxy only", "Absent from release"}
    exact = [field for field in fields if field.get("mapping_status") == "Exact"]
    if [field.get("source_field") for field in exact] != ["bp_alert"]:
        raise ValueError("bp_alert must be the only Exact triage mapping")
    for field in fields:
        status = field.get("mapping_status")
        observed = field.get("observed_release_path")
        proxies = field.get("related_proxy_release_paths")
        if status not in allowed_statuses:
            raise ValueError(f"Invalid triage mapping status: {status}")
        if not isinstance(proxies, list):
            raise ValueError("related_proxy_release_paths must be an array")
        if status == "Exact" and observed not in observed_paths:
            raise ValueError(f"Exact triage path is absent from the release: {observed}")
        if status != "Exact" and observed is not None:
            raise ValueError("Only Exact mappings may set observed_release_path")
        if status == "Related proxy only" and not proxies:
            raise ValueError("Related proxy mappings must identify at least one release path")
        if status == "Absent from release" and proxies:
            raise ValueError("Absent mappings cannot identify related proxy paths")
        missing_proxies = sorted(set(proxies) - observed_paths)
        if missing_proxies:
            raise ValueError(f"Triage proxy paths are absent from the release: {missing_proxies}")


def triage_crosswalk_markdown(triage_crosswalk: dict[str, Any]) -> list[str]:
    lines = [
        "## Four-Class Physiological Triage Source-to-Release Crosswalk",
        "",
        "This is a documentation crosswalk from the supplied source taxonomy to the observed public release. It is not medical validation and does not assert that a related release signal is clinically equivalent to a source symptom.",
        "",
    ]
    lines.extend(f"- {note}" for note in triage_crosswalk["source_notes"])
    lines.extend(
        [
            "",
            "| Class | Source field | Source-document path | Observed exact release path | Possible related/proxy release paths | Mapping status | Evidence-based note |",
            "|---|---|---|---|---|---|---|",
        ]
    )
    for item in triage_crosswalk["classes"]:
        class_label = f"Class {item['class_number']} — {item['class_name']}"
        for field in item["fields"]:
            proxies = "<br>".join(f"`{path}`" for path in field["related_proxy_release_paths"])
            row = [
                class_label,
                f"`{field['source_field']}`",
                f"`{field['source_document_path']}`",
                (f"`{field['observed_release_path']}`" if field["observed_release_path"] else "-"),
                proxies or "-",
                field["mapping_status"],
                field["note"],
            ]
            lines.append("| " + " | ".join(markdown_cell(value, limit=800) for value in row) + " |")
    lines.extend(["", "## Observed Release Field Inventory", ""])
    return lines


def build_dictionary(data: dict[str, Any]) -> str:
    observations: dict[str, list[Any]] = defaultdict(list)
    record_observations(data, observations)
    lines = [
        "# MamaAir WQ1 Data Dictionary",
        "",
        "Generated deterministically from the released JSON object. Numeric minima, maxima, nullability, and value sets describe only the observed synthetic records; they are not clinical validity bounds or generation rules.",
        "",
        "## Observed Release Field Inventory",
        "",
    ]
    lines.extend(
        [
            "| Path | Type | Nullable | Observed min | Observed max | Observed enum/value set |",
            "|---|---|---:|---:|---:|---|",
        ]
    )
    for path in sorted(observations):
        values = observations[path]
        type_text, nullable, minimum, maximum, enum = summarize_values(values)
        row = [
            f"`{path}`",
            type_text,
            nullable,
            minimum,
            maximum,
            enum,
        ]
        lines.append("| " + " | ".join(markdown_cell(item) for item in row) + " |")
    lines.extend(
        [
            "",
            "## Notes",
            "",
            "- Array item paths use `[*]`.",
            "- JSON `integer` and `number` are consolidated to `number` when both representations occur.",
            "- Empty arrays have no observed item enum or range.",
            "- Intended-range and null differences are summarized in the public `limitations_and_allowed_use.md`; they are not enforced by the observed schema when the data conflicts.",
        ]
    )
    return "\n".join(lines) + "\n"


def normalize_release_metadata(source: dict[str, Any]) -> dict[str, Any]:
    data = copy.deepcopy(source)
    metadata = data.get("dataset_metadata")
    if not isinstance(metadata, dict):
        raise ValueError("dataset_metadata must be an object")
    if metadata.get("dataset_id") != "mamaair-ssa-climate-maternal-wq1":
        raise ValueError("Unexpected dataset_id; refusing to normalize")
    metadata["contact"] = PUBLIC_CONTACT
    metadata["managed_by"] = PUBLIC_MANAGER
    metadata["license"] = PUBLIC_LICENSE
    metadata["format"] = "JSON"
    metadata["aws_registry_tags"] = REGISTRY_TAGS
    return data


def trajectory_value_hash(data: dict[str, Any]) -> str:
    canonical = json.dumps(data["trajectories"], ensure_ascii=True, separators=(",", ":")).encode(
        "utf-8"
    )
    return hashlib.sha256(canonical).hexdigest()


def main() -> int:
    package_root = Path(__file__).resolve().parents[1]
    repository_root = package_root.parent
    parser = argparse.ArgumentParser()
    parser.add_argument("--source-data", type=Path, required=True)
    parser.add_argument("--source-schema", type=Path, required=True)
    parser.add_argument(
        "--triage-crosswalk",
        type=Path,
        default=repository_root / "internal/release-support/schema/triage_crosswalk.source.json",
    )
    parser.add_argument("--output-root", type=Path, required=True)
    parser.add_argument(
        "--dictionary-output",
        type=Path,
        default=repository_root / "docs/release/DATA_DICTIONARY.md",
    )
    args = parser.parse_args()

    with args.source_data.open("r", encoding="utf-8") as handle:
        source_data = json.load(handle)
    with args.source_schema.open("r", encoding="utf-8") as handle:
        json.load(handle)
    with args.triage_crosswalk.open("r", encoding="utf-8") as handle:
        triage_crosswalk = json.load(handle)

    release_data = normalize_release_metadata(source_data)
    source_trajectory_hash = trajectory_value_hash(source_data)
    release_trajectory_hash = trajectory_value_hash(release_data)
    if source_trajectory_hash != EXPECTED_TRAJECTORY_HASH:
        raise ValueError(f"Unexpected source trajectory hash: {source_trajectory_hash}")
    if release_trajectory_hash != source_trajectory_hash:
        raise ValueError("Metadata normalization changed trajectory values")
    data_dir = args.output_root / "data"
    schema_dir = args.output_root / "schema"
    data_dir.mkdir(parents=True, exist_ok=True)
    schema_dir.mkdir(parents=True, exist_ok=True)

    with (data_dir / "sample_records.json").open("w", encoding="utf-8", newline="") as handle:
        json.dump(release_data, handle, ensure_ascii=True, indent=2)

    observed = infer_schema([release_data])
    observed = {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "title": "MamaAir WQ1 observed release schema",
        "description": "Structural schema inferred from the 75-trajectory JSON release candidate. x-observed-* values are annotations, not medical or generator constraints.",
        "$comment": "Observed numeric annotations are descriptive and are not clinical or generator constraints. See limitations_and_allowed_use.md.",
        **observed,
    }
    with (schema_dir / "mamaair_wq1.schema.observed.json").open(
        "w", encoding="utf-8", newline=""
    ) as handle:
        json.dump(observed, handle, ensure_ascii=False, indent=2)
        handle.write("\n")

    observations: dict[str, list[Any]] = defaultdict(list)
    record_observations(release_data, observations)
    validate_triage_crosswalk(triage_crosswalk, set(observations))
    dictionary = build_dictionary(release_data)
    args.dictionary_output.parent.mkdir(parents=True, exist_ok=True)
    args.dictionary_output.write_text(dictionary, encoding="utf-8")

    original_data_hash_input = json.dumps(source_data, ensure_ascii=True, indent=2).encode("utf-8")
    source_bytes = args.source_data.read_bytes()
    if original_data_hash_input != source_bytes:
        raise ValueError(
            "Source JSON formatting differs from the deterministic serializer; source was not modified"
        )

    print("Prepared data/sample_records.json with metadata-only normalization.")
    print("Read the maintained source schema and internal triage crosswalk without copying them.")
    print(f"Generated schema/mamaair_wq1.schema.observed.json and {args.dictionary_output}.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
