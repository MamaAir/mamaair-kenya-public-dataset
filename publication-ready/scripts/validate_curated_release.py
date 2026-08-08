#!/usr/bin/env python3
"""Validate the directly deployable curated release directory."""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

from build_public_release import public_files, verify_release
from validate_andrei_documents import validate_pair

REQUIRED_PUBLIC_OBJECTS = {
    "README.md",
    "LICENSE.md",
    "METHODOLOGY_NOTE.md",
    "data_dictionary.md",
    "limitations_and_allowed_use.md",
    "sample_records.json",
    "schema.json",
    "STREAMING.md",
    "schema/mamaair_stream_event.schema.json",
}

FORBIDDEN_PUBLIC_OBJECTS = {
    "OWNER_REVIEW.md",
    "schema/generation_logic.source.json",
    "schema/triage_crosswalk.source.json",
}


def unsupported_clinical_equivalence_lines(text: str) -> list[str]:
    hits = []
    for line in text.splitlines():
        positive = re.search(
            r"\b(?:is|are) clinically equivalent\b|\bclinically equivalent to\b",
            line,
            re.I,
        )
        disclaimer = re.search(r"\b(?:not|does not|non-equivalent)\b", line, re.I)
        if positive and not disclaimer:
            hits.append(line.strip())
    return hits


def leaf_paths(value: object, prefix: str = "") -> set[str]:
    paths: set[str] = set()
    if isinstance(value, dict):
        for key, child in value.items():
            path = f"{prefix}.{key}" if prefix else key
            paths.update(leaf_paths(child, path))
    elif isinstance(value, list):
        paths.add(prefix)
        for child in value:
            if isinstance(child, dict):
                paths.update(leaf_paths(child, f"{prefix}[*]"))
    else:
        paths.add(prefix)
    return paths


def validate(root: Path, repository_root: Path, package_root: Path) -> list[str]:
    errors: list[str] = []
    mapping = public_files(repository_root, package_root)
    expected = set(mapping) | {"CHECKSUMS.sha256"}
    actual = {str(path.relative_to(root)) for path in root.rglob("*") if path.is_file()}
    if actual != expected:
        errors.append(
            f"curated allowlist mismatch: missing={sorted(expected - actual)} "
            f"extra={sorted(actual - expected)}"
        )
    if not REQUIRED_PUBLIC_OBJECTS <= actual:
        errors.append(
            f"required public objects missing: {sorted(REQUIRED_PUBLIC_OBJECTS - actual)}"
        )
    try:
        verify_release(root, set(mapping))
    except (OSError, ValueError) as exc:
        errors.append(str(exc))

    if actual & FORBIDDEN_PUBLIC_OBJECTS:
        errors.append(f"internal objects present in curated release: {sorted(actual & FORBIDDEN_PUBLIC_OBJECTS)}")

    try:
        schema = json.loads((root / "schema.json").read_text(encoding="utf-8"))
        if schema.get("$schema") != "https://json-schema.org/draft/2020-12/schema":
            errors.append("schema.json is not the observed Draft 2020-12 schema")
        json.loads((root / "sample_records.json").read_text(encoding="utf-8"))
    except (KeyError, OSError, ValueError, json.JSONDecodeError) as exc:
        errors.append(f"curated data/schema validation failed: {exc}")

    dictionary = root / "data_dictionary.md"
    if dictionary.is_file():
        text = dictionary.read_text(encoding="utf-8")
        for required in ["Observed Release Field Inventory"]:
            if required not in text:
                errors.append(f"data_dictionary.md is missing: {required}")
        for forbidden in [
            "triage crosswalk",
            "generation_logic.source.json",
            "docs/source-materials/",
            "internal/",
        ]:
            if forbidden.lower() in text.lower():
                errors.append(f"data_dictionary.md exposes internal source material: {forbidden}")
        equivalence_claims = unsupported_clinical_equivalence_lines(text)
        if equivalence_claims:
            errors.append(
                "data_dictionary.md contains unsupported clinical-equivalence claims: "
                f"{equivalence_claims}"
            )

    for public_name, source_name in [
        ("README.md", "Readme.md (1).odt"),
        ("LICENSE.md", "Licence.md (1).odt"),
    ]:
        try:
            errors.extend(
                validate_pair(
                    root / public_name,
                    repository_root / "internal/andrei-source" / source_name,
                )
            )
        except (OSError, ValueError) as exc:
            errors.append(f"Andrei document validation failed for {public_name}: {exc}")

    sys.path.insert(0, str(repository_root))
    try:
        from deployment.upload_public_release import CONTENT_TYPES, verified_objects

        upload_objects = verified_objects(root)
        upload_keys = {str(path.relative_to(root)) for path in upload_objects}
        if upload_keys != expected:
            errors.append("uploader object layout differs from the curated allowlist")
        missing_content_types = sorted(
            relative for relative in upload_keys if Path(relative).suffix not in CONTENT_TYPES
        )
        if missing_content_types:
            errors.append(f"uploader content types missing: {missing_content_types}")
    except (ImportError, OSError, ValueError) as exc:
        errors.append(f"uploader integration validation failed: {exc}")
    return errors


def main() -> int:
    repository_root = Path(__file__).resolve().parents[2]
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--root",
        type=Path,
        default=repository_root / "build/public-release/releases/v1",
    )
    args = parser.parse_args()
    errors = validate(
        args.root.resolve(),
        repository_root,
        repository_root / "publication-ready",
    )
    print("MamaAir curated release validation")
    print(f"  errors: {len(errors)}")
    for error in errors:
        print(f"  [ERROR] {error}")
    if errors:
        return 1
    count = sum(path.is_file() for path in args.root.rglob("*"))
    print(f"  objects: {count}")
    print("  required stable names, allowlist, checksums, public schemas, and uploader: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
