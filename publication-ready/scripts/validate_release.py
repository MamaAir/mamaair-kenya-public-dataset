#!/usr/bin/env python3
"""Validate the local publication package and final-publication gate."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path
from typing import Any

REQUIRED_FILES = [
    "data/sample_records.json",
    "schema/mamaair_wq1.schema.observed.json",
    "scripts/validate_dataset.py",
    "scripts/validate_release.py",
    "scripts/render_registry_yaml.py",
    "scripts/validate_andrei_documents.py",
    "scripts/build_public_release.py",
    "scripts/generate_checksums.py",
    "scripts/validate_curated_release.py",
]

REQUIRED_INTERNAL_RELEASE_SUPPORT = [
    "release-support/schema/generation_logic.source.json",
    "release-support/schema/triage_crosswalk.source.json",
    "release-support/registry/mamaair-kenya-synthetic-maternal-health.yaml.template",
    "release-support/reports/dataset-validation.json",
]

REQUIRED_DOCUMENTS = [
    "docs/release/STREAMING.md",
    "docs/release/METHODOLOGY.md",
    "docs/release/DATA_DICTIONARY.md",
    "docs/release/LIMITATIONS_AND_ALLOWED_USE.md",
    "internal/docs/README.md",
    "internal/docs/operations/ENGINEERING_GUIDE.md",
    "internal/docs/operations/PUBLICATION_WORKFLOW.md",
    "internal/docs/operations/RELEASE_CHECKLIST.md",
    "internal/docs/operations/HANDOFF_TO_ANDREI.md",
    "internal/docs/operations/STREAMING_REPLAY.md",
    "internal/docs/audits/SOURCE_AUDIT.md",
    "internal/docs/audits/DATA_AUDIT.md",
    "internal/docs/audits/SCHEMA_DIFF.md",
    "internal/docs/audits/DECISIONS_REQUIRED.md",
    "internal/docs/audits/OWNER_REVIEW.md",
    "internal/docs/registry/PR_PROPOSAL.md",
    "internal/docs/data-exchange/DATA_GRANT_COPY.md",
    "internal/docs/data-exchange/DATA_GRANT_RUNBOOK.md",
    "internal/docs/source-materials/README.md",
]

APPROVED_RELEASE_TAGS = {
    "health",
    "life sciences",
    "machine learning",
    "climate",
    "environmental",
    "sustainability",
    "synthetic data",
}

OFFICIAL_ADX_CATEGORIES = {
    "Financial Services Data",
    "Retail, Location & Marketing Data",
    "Public Sector Data",
    "Healthcare & Life Sciences Data",
    "Resources Data",
    "Media & Entertainment Data",
    "Telecommunications Data",
    "Environmental Data",
    "Automotive Data",
    "Manufacturing Data",
    "Gaming Data",
}

PLACEHOLDER_RE = re.compile(r"\{\{[^}]+\}\}|REPLACE_WITH|\bTBD\b|\bTODO\b|\[Insert\b|\bxxx\b", re.I)
AWS_REGION_RE = re.compile(r"^(?:af|ap|ca|eu|il|me|mx|sa|us)(?:-gov)?-[a-z0-9-]+-\d$")
EXPECTED_DATASET_FACTS = {
    "trajectory_count": 75,
    "daily_record_count": 15_134,
    "weekly_summary_count": 2_162,
    "trajectory_value_hash": "fdb7fffec1c566b559c668d4b2b39c6d740ba017430c5078c8c974103329b98a",
}


class Gate:
    def __init__(self) -> None:
        self.errors: list[dict[str, Any]] = []
        self.blockers: list[dict[str, Any]] = []
        self.warnings: list[dict[str, Any]] = []

    def add(self, bucket: str, code: str, message: str, **details: Any) -> None:
        getattr(self, bucket).append({"code": code, "message": message, **details})


def read_text(root: Path, relative: str) -> str:
    return (root / relative).read_text(encoding="utf-8")


def parse_yaml_sequence(text: str, field: str) -> list[str]:
    lines = text.splitlines()
    values: list[str] = []
    active = False
    for line in lines:
        if re.match(rf"^{re.escape(field)}:\s*$", line):
            active = True
            continue
        if active:
            match = re.match(r"^\s+-\s+(.+?)\s*$", line)
            if match:
                values.append(match.group(1).strip().strip("'\""))
                continue
            if line and not line[0].isspace():
                break
    return values


def yaml_scalar(text: str, field: str) -> str | None:
    match = re.search(rf"^{re.escape(field)}:\s*(.+?)\s*$", text, re.M)
    return match.group(1).strip().strip("'\"") if match else None


def validate_registry(root: Path, gate: Gate) -> None:
    template_path = root / "registry/mamaair-kenya-synthetic-maternal-health.yaml.template"
    if not template_path.exists():
        return
    template = template_path.read_text(encoding="utf-8")
    tags = parse_yaml_sequence(template, "Tags")
    categories = parse_yaml_sequence(template, "ADXCategories")
    unsupported_tags = sorted(set(tags) - APPROVED_RELEASE_TAGS)
    unsupported_categories = sorted(set(categories) - OFFICIAL_ADX_CATEGORIES)
    if unsupported_tags:
        gate.add(
            "errors",
            "UNSUPPORTED_REGISTRY_TAGS",
            "Template includes tags outside the verified official vocabulary.",
            tags=unsupported_tags,
        )
    if unsupported_categories or len(categories) > 2:
        gate.add(
            "errors",
            "UNSUPPORTED_ADX_CATEGORIES",
            "Template includes invalid ADX categories or more than two categories.",
            categories=categories,
        )
    if any(tag.startswith("#") for tag in tags):
        gate.add("errors", "HASHTAG_REGISTRY_TAG", "Registry tags must not be hashtags.")

    region = yaml_scalar(template, "Region")
    if region and not PLACEHOLDER_RE.search(region) and not AWS_REGION_RE.fullmatch(region):
        gate.add(
            "errors",
            "INVALID_AWS_REGION",
            "Registry Region is not an AWS Region identifier.",
            observed=region,
        )
    if region and region.lower() == "kenya":
        gate.add(
            "errors", "KENYA_IS_NOT_AWS_REGION", "Kenya is a geographic scope, not an AWS Region."
        )

    placeholders = sorted(set(PLACEHOLDER_RE.findall(template)))
    if placeholders:
        gate.add(
            "blockers",
            "REGISTRY_RESOURCE_VALUES_UNRESOLVED",
            "The correctly labeled Registry template still needs a public documentation URL, bucket ARN, and AWS Region.",
            placeholders=placeholders,
        )

    for candidate in (root / "registry").glob("*.yaml"):
        if candidate.name.endswith(".template"):
            continue
        text = candidate.read_text(encoding="utf-8")
        if PLACEHOLDER_RE.search(text):
            gate.add(
                "errors",
                "FINAL_YAML_HAS_PLACEHOLDERS",
                "A supposedly final Registry YAML still contains placeholders.",
                file=str(candidate.relative_to(root)),
            )

    final_candidates = [
        candidate
        for candidate in (root / "registry").glob("*.yaml")
        if not candidate.name.endswith(".template")
    ]
    if not final_candidates:
        gate.add(
            "blockers",
            "FINAL_REGISTRY_YAML_UNAVAILABLE",
            "No final Registry YAML can be rendered until real deployment outputs exist.",
        )
    if not (root / "registry/REGISTRY_PR_URL.txt").is_file():
        gate.add(
            "blockers",
            "REGISTRY_GITHUB_PUBLICATION_UNRESOLVED",
            "No authorized Registry pull request URL is recorded; GitHub ownership/authentication remains a deployment prerequisite.",
        )


def parse_checksums(path: Path) -> dict[str, str]:
    entries: dict[str, str] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        match = re.fullmatch(r"([0-9a-f]{64})  (.+)", line)
        if match:
            entries[match.group(2)] = match.group(1)
    return entries


def validate_checksums(root: Path, gate: Gate) -> None:
    checksum_path = root / "CHECKSUMS.sha256"
    if not checksum_path.exists():
        return
    entries = parse_checksums(checksum_path)
    files = sorted(
        str(path.relative_to(root))
        for path in root.rglob("*")
        if path.is_file()
        and path != checksum_path
        and "__pycache__" not in path.parts
        and not path.name.startswith(".")
    )
    missing = sorted(set(files) - set(entries))
    extra = sorted(set(entries) - set(files))
    mismatches = []
    for relative in sorted(set(files) & set(entries)):
        digest = hashlib.sha256((root / relative).read_bytes()).hexdigest()
        if digest != entries[relative]:
            mismatches.append(relative)
    if missing or extra or mismatches:
        gate.add(
            "errors",
            "CHECKSUM_COVERAGE_OR_VALUE",
            "Checksum manifest is incomplete, stale, or contains extra entries.",
            missing=missing,
            extra=extra,
            mismatches=mismatches,
        )


def validate_triage_documentation(root: Path, documentation_root: Path, gate: Gate) -> None:
    try:
        crosswalk = json.loads(read_text(root, "schema/triage_crosswalk.source.json"))
        classes = crosswalk.get("classes", [])
        class_numbers = [item.get("class_number") for item in classes]
        fields = [field for item in classes for field in item.get("fields", [])]
        if class_numbers != [1, 2, 3, 4] or len(fields) != 20:
            gate.add(
                "errors",
                "TRIAGE_CROSSWALK_COVERAGE",
                "Maintained triage source must contain Classes 1-4 and 20 fields.",
            )
            return
        allowed = {"Exact", "Related proxy only", "Absent from release"}
        invalid_status = [
            field.get("source_field")
            for field in fields
            if field.get("mapping_status") not in allowed
        ]
        exact = [
            field.get("source_field") for field in fields if field.get("mapping_status") == "Exact"
        ]
        unsupported_equivalence = [
            field.get("source_field")
            for field in fields
            if field.get("mapping_status") != "Exact"
            and re.search(
                r"\b(?:is|are) clinically equivalent\b|\bclinically equivalent to\b",
                field.get("note", ""),
                re.I,
            )
        ]
        absent_without_statement = [
            field.get("source_field")
            for field in fields
            if field.get("mapping_status") == "Absent from release"
            and field.get("related_proxy_release_paths")
        ]
        if (
            invalid_status
            or exact != ["bp_alert"]
            or absent_without_statement
            or unsupported_equivalence
        ):
            gate.add(
                "errors",
                "TRIAGE_CROSSWALK_MAPPING",
                "Triage statuses, exact-match evidence, or absence declarations are invalid.",
                invalid_status=invalid_status,
                exact=exact,
                absent_with_proxies=absent_without_statement,
                unsupported_equivalence=unsupported_equivalence,
            )
        dictionary = read_text(documentation_root, "release/DATA_DICTIONARY.md")
        leaked_internal_terms = [
            value
            for value in [
                "Four-Class Physiological Triage Source-to-Release Crosswalk",
                "journey[].symptoms.excessive_hiccups",
                "docs/source-materials/",
                "generation_logic.source.json",
                "internal/",
            ]
            if value in dictionary
        ]
        if leaked_internal_terms:
            gate.add(
                "errors",
                "INTERNAL_SOURCE_MATERIAL_IN_PUBLIC_DICTIONARY",
                "The public dictionary exposes internal crosswalk or source-material details.",
                terms=leaked_internal_terms,
            )
    except (KeyError, OSError, json.JSONDecodeError) as exc:
        gate.add("errors", "TRIAGE_CROSSWALK_PARSE", f"Triage crosswalk cannot be validated: {exc}")


def validate_infrastructure(repository_root: Path, gate: Gate) -> None:
    outputs = (repository_root / "infrastructure/terraform/outputs.tf").read_text(encoding="utf-8")
    required_outputs = {
        "aws_region",
        "bucket_name",
        "bucket_arn",
        "stream_name",
        "stream_arn",
        "release_base_url",
        "sample_records_url",
        "schema_url",
        "documentation_url",
        "producer_policy_arn",
        "smoke_test_policy_arn",
    }
    declared = set(re.findall(r'^output\s+"([^"]+)"', outputs, re.M))
    missing_outputs = sorted(required_outputs - declared)
    if missing_outputs:
        gate.add(
            "errors",
            "TERRAFORM_OUTPUTS_MISSING",
            "Terraform does not expose every required deployment value.",
            outputs=missing_outputs,
        )
    main = (repository_root / "infrastructure/terraform/main.tf").read_text(encoding="utf-8")
    smoke_actions = {
        "kinesis:PutRecords",
        "kinesis:DescribeStreamSummary",
        "kinesis:ListShards",
        "kinesis:GetShardIterator",
        "kinesis:GetRecords",
    }
    smoke_match = re.search(
        r'data "aws_iam_policy_document" "smoke_test_operator" \{(.*?)\n\}',
        main,
        re.S,
    )
    observed_actions = (
        set(re.findall(r'"(kinesis:[A-Za-z]+)"', smoke_match.group(1))) if smoke_match else set()
    )
    if observed_actions != smoke_actions or "kinesis:*" in main:
        gate.add(
            "errors",
            "SMOKE_TEST_IAM_SCOPE",
            "Smoke-test IAM must contain only the five required stream actions.",
            expected=sorted(smoke_actions),
            observed=sorted(observed_actions),
        )
    producer_match = re.search(r'data "aws_iam_policy_document" "producer" \{(.*?)\n\}', main, re.S)
    producer_actions = (
        set(re.findall(r'"(kinesis:[A-Za-z]+)"', producer_match.group(1)))
        if producer_match
        else set()
    )
    if producer_actions != {"kinesis:PutRecords"}:
        gate.add(
            "errors",
            "PRODUCER_IAM_SCOPE",
            "Normal producer IAM must remain restricted to kinesis:PutRecords.",
            observed=sorted(producer_actions),
        )


def validate_current_documentation(repository_root: Path, gate: Gate) -> None:
    candidates = [repository_root / "README.md"]
    candidates.extend((repository_root / "docs").rglob("*.md"))
    stale = []
    for path in candidates:
        text = path.read_text(encoding="utf-8")
        if "publication-ready.zip" in text:
            stale.append(str(path.relative_to(repository_root)))
    if stale:
        gate.add(
            "errors",
            "STALE_ARCHIVE_DOCUMENTATION",
            "Current documentation must not claim or require publication-ready.zip.",
            files=sorted(stale),
        )


def validate_owner_review(repository_root: Path, gate: Gate) -> None:
    path = repository_root / "internal/docs/audits/OWNER_REVIEW.md"
    if not path.is_file():
        gate.add(
            "blockers",
            "OWNER_REVIEW_MISSING",
            "The internal owner decision record is missing.",
        )
        return
    text = path.read_text(encoding="utf-8")
    section = text.partition("## Owner confirmation needed")[2]
    decisions = re.findall(r"^\d+\.\s+.+$", section, re.M)
    if decisions:
        gate.add(
            "blockers",
            "OWNER_PUBLICATION_DECISIONS_UNRESOLVED",
            "Internal owner review contains unresolved public license/documentation decisions.",
            count=len(decisions),
        )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    args = parser.parse_args()
    root = args.root.resolve()
    repository_root = root.parent
    documentation_root = repository_root / "docs"
    internal_root = repository_root / "internal"
    gate = Gate()

    missing = [relative for relative in REQUIRED_FILES if not (root / relative).is_file()]
    if missing:
        gate.add(
            "errors",
            "MISSING_REQUIRED_FILES",
            "Publication package is missing required files.",
            files=missing,
        )
    missing_internal_support = [
        relative
        for relative in REQUIRED_INTERNAL_RELEASE_SUPPORT
        if not (internal_root / relative).is_file()
    ]
    if missing_internal_support:
        gate.add(
            "errors",
            "MISSING_INTERNAL_RELEASE_SUPPORT",
            "Internal validation and publication-support material is incomplete.",
            files=missing_internal_support,
        )
    missing_documents = [
        relative for relative in REQUIRED_DOCUMENTS if not (repository_root / relative).is_file()
    ]
    if missing_documents:
        gate.add(
            "errors",
            "MISSING_REQUIRED_DOCUMENTS",
            "The centralized documentation tree is incomplete.",
            files=missing_documents,
        )
    for relative in [
        "README.md",
        "LICENSE.md",
        "internal/andrei-source/Readme.md (1).odt",
        "internal/andrei-source/Licence.md (1).odt",
    ]:
        if not (repository_root / relative).is_file():
            gate.add(
                "errors",
                "MISSING_ANDREI_DOCUMENT",
                "An authoritative Andrei source or synchronized project document is missing.",
                file=relative,
            )

    report_path = internal_root / "release-support/reports/dataset-validation.json"
    if report_path.exists():
        try:
            report = json.loads(report_path.read_text(encoding="utf-8"))
            summary = report.get("summary", {})
            if summary.get("errors", 0):
                gate.add(
                    "errors",
                    "DATASET_VALIDATION_ERRORS",
                    "Dataset validation report contains release-blocking errors.",
                    count=summary.get("errors"),
                )
            facts = report.get("facts", {})
            mismatched_facts = {
                key: {"expected": expected, "observed": facts.get(key)}
                for key, expected in EXPECTED_DATASET_FACTS.items()
                if facts.get(key) != expected
            }
            if mismatched_facts:
                gate.add(
                    "errors",
                    "APPROVED_DATASET_FACTS_MISMATCH",
                    "Validation report does not describe the approved dataset counts/hash.",
                    mismatches=mismatched_facts,
                )
            if summary.get("owner_decisions", 0):
                gate.add(
                    "errors",
                    "STALE_OWNER_DECISION_FINDINGS",
                    "Dataset findings still contain obsolete owner-decision classifications.",
                    count=summary.get("owner_decisions"),
                )
        except (OSError, json.JSONDecodeError) as exc:
            gate.add(
                "errors",
                "DATASET_REPORT_PARSE",
                f"Dataset validation report cannot be parsed: {exc}",
            )

    try:
        from validate_andrei_documents import validate as validate_andrei

        for error in validate_andrei(repository_root):
            gate.add("errors", "ANDREI_DOCUMENT_DRIFT", error)
    except ImportError as exc:
        gate.add(
            "errors",
            "ANDREI_VALIDATOR_IMPORT",
            f"Andrei document validator could not be loaded: {exc}",
        )
    validate_registry(internal_root / "release-support", gate)
    validate_checksums(root, gate)
    validate_triage_documentation(internal_root / "release-support", documentation_root, gate)
    validate_infrastructure(repository_root, gate)
    validate_current_documentation(repository_root, gate)
    validate_owner_review(repository_root, gate)
    try:
        from validate_curated_release import validate as validate_curated

        curated_errors = validate_curated(
            repository_root / "build/public-release/releases/v1",
            repository_root,
            root,
        )
        for error in curated_errors:
            gate.add("errors", "CURATED_RELEASE_INVALID", error)
    except ImportError as exc:
        gate.add(
            "errors",
            "CURATED_VALIDATOR_IMPORT",
            f"Curated release validator could not be loaded: {exc}",
        )

    print("MamaAir release validation")
    print(f"  package errors: {len(gate.errors)}")
    print(f"  publication blockers: {len(gate.blockers)}")
    print(f"  warnings: {len(gate.warnings)}")
    for label, items in [
        ("ERROR", gate.errors),
        ("BLOCKER", gate.blockers),
        ("WARNING", gate.warnings),
    ]:
        for item in items:
            print(f"  [{label}] {item['code']}: {item['message']}")
    if gate.errors or gate.blockers:
        print("  final publication gate: FAIL")
        return 1
    print("  final publication gate: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
