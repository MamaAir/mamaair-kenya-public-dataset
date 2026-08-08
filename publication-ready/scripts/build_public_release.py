#!/usr/bin/env python3
"""Build the deterministic, allowlisted public object prefix."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import shutil
import tempfile
from pathlib import Path

EXPECTED_TRAJECTORY_HASH = "fdb7fffec1c566b559c668d4b2b39c6d740ba017430c5078c8c974103329b98a"
VERSION_RE = re.compile(r"^v[1-9][0-9]*$")


def public_files(repository_root: Path, package_root: Path) -> dict[str, Path]:
    release_docs = repository_root / "docs/release"
    return {
        "README.md": repository_root / "README.md",
        "LICENSE.md": repository_root / "LICENSE.md",
        "METHODOLOGY_NOTE.md": release_docs / "METHODOLOGY.md",
        "data_dictionary.md": release_docs / "DATA_DICTIONARY.md",
        "limitations_and_allowed_use.md": release_docs / "LIMITATIONS_AND_ALLOWED_USE.md",
        "STREAMING.md": release_docs / "STREAMING.md",
        "sample_records.json": package_root / "data/sample_records.json",
        "schema.json": package_root / "schema/mamaair_wq1.schema.observed.json",
        "schema/mamaair_stream_event.schema.json": repository_root
        / "streaming/schema/mamaair_stream_event.schema.json",
    }


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def trajectory_hash(path: Path) -> str:
    with path.open("r", encoding="utf-8") as handle:
        trajectories = json.load(handle)["trajectories"]
    canonical = json.dumps(trajectories, ensure_ascii=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(canonical).hexdigest()


def verify_release(release_root: Path, expected_files: set[str]) -> None:
    actual = {
        str(path.relative_to(release_root)) for path in release_root.rglob("*") if path.is_file()
    }
    expected_with_manifest = expected_files | {"CHECKSUMS.sha256"}
    if actual != expected_with_manifest:
        raise ValueError(
            f"Public release allowlist mismatch; missing={sorted(expected_with_manifest - actual)}, "
            f"extra={sorted(actual - expected_with_manifest)}"
        )
    entries = {}
    for line in (release_root / "CHECKSUMS.sha256").read_text(encoding="utf-8").splitlines():
        value, relative = line.split("  ", 1)
        entries[relative] = value
    if set(entries) != expected_files:
        raise ValueError("Public checksum manifest coverage is incorrect")
    mismatches = [
        relative for relative, value in entries.items() if digest(release_root / relative) != value
    ]
    if mismatches:
        raise ValueError(f"Public checksum mismatch: {mismatches}")
    observed_hash = trajectory_hash(release_root / "sample_records.json")
    if observed_hash != EXPECTED_TRAJECTORY_HASH:
        raise ValueError(f"Trajectory hash changed: {observed_hash}")


def build(repository_root: Path, package_root: Path, output_root: Path, version: str) -> Path:
    if not VERSION_RE.fullmatch(version):
        raise ValueError("Version must use the form v1, v2, ...")
    mapping = public_files(repository_root, package_root)
    missing = [str(path) for path in mapping.values() if not path.is_file()]
    if missing:
        raise FileNotFoundError(f"Missing public source files: {missing}")

    resolved_output = output_root.resolve()
    if resolved_output in {Path("/"), Path.home().resolve(), repository_root.resolve()}:
        raise ValueError("Refusing a broad or unsafe public-release output root")
    releases_root = resolved_output / "releases"
    releases_root.mkdir(parents=True, exist_ok=True)
    target = releases_root / version
    if package_root.resolve() == target or package_root.resolve() in target.parents:
        raise ValueError("Output must not contain the source publication package")

    temporary = Path(tempfile.mkdtemp(prefix=f".{version}-", dir=releases_root))
    try:
        for relative, source in sorted(mapping.items()):
            destination = temporary / relative
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(source, destination)
        lines = [f"{digest(temporary / relative)}  {relative}" for relative in sorted(mapping)]
        (temporary / "CHECKSUMS.sha256").write_text("\n".join(lines) + "\n", encoding="utf-8")
        verify_release(temporary, set(mapping))
        if target.exists():
            shutil.rmtree(target)
        temporary.replace(target)
    except Exception:
        if temporary.exists():
            shutil.rmtree(temporary)
        raise
    return target


def main() -> int:
    package_root = Path(__file__).resolve().parents[1]
    repository_root = package_root.parent
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--package-root", type=Path, default=package_root)
    parser.add_argument(
        "--output-root", type=Path, default=repository_root / "build/public-release"
    )
    parser.add_argument("--version", default="v1")
    args = parser.parse_args()
    target = build(
        repository_root.resolve(),
        args.package_root.resolve(),
        args.output_root.resolve(),
        args.version,
    )
    print(f"Built curated public prefix: {target}")
    print("No archive is created or required; deployment uploads this directory directly.")
    print(f"Trajectory hash: {EXPECTED_TRAJECTORY_HASH}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
