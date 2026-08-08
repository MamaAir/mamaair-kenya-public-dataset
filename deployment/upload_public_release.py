#!/usr/bin/env python3
"""Upload only a verified curated release with explicit object content types."""

from __future__ import annotations

import argparse
import hashlib
import os
import sys
from pathlib import Path

try:
    from deployment.aws_preflight import require_value, run_preflight
except ModuleNotFoundError:  # Direct execution from deployment/.
    from aws_preflight import require_value, run_preflight


CONTENT_TYPES = {
    ".json": "application/json",
    ".md": "text/markdown; charset=utf-8",
    ".sha256": "text/plain; charset=utf-8",
}

APPROVED_PUBLIC_OBJECTS = {
    "CHECKSUMS.sha256",
    "LICENSE.md",
    "METHODOLOGY_NOTE.md",
    "README.md",
    "STREAMING.md",
    "data_dictionary.md",
    "limitations_and_allowed_use.md",
    "sample_records.json",
    "schema.json",
    "schema/mamaair_stream_event.schema.json",
}


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def verified_objects(release_root: Path) -> list[Path]:
    manifest = release_root / "CHECKSUMS.sha256"
    if not manifest.is_file():
        raise ValueError("Curated release has no CHECKSUMS.sha256")
    entries = {}
    for line in manifest.read_text(encoding="utf-8").splitlines():
        digest, relative = line.split("  ", 1)
        entries[relative] = digest
    actual_without_manifest = {
        str(path.relative_to(release_root))
        for path in release_root.rglob("*")
        if path.is_file() and path != manifest
    }
    actual = actual_without_manifest | {"CHECKSUMS.sha256"}
    if actual != APPROVED_PUBLIC_OBJECTS:
        raise ValueError(
            "Curated release differs from the explicit uploader allowlist; "
            f"missing={sorted(APPROVED_PUBLIC_OBJECTS - actual)}, "
            f"extra={sorted(actual - APPROVED_PUBLIC_OBJECTS)}"
        )
    if actual_without_manifest != set(entries):
        raise ValueError("Curated release contains missing, extra, or unmanifested objects")
    mismatches = [
        relative
        for relative, digest in entries.items()
        if sha256(release_root / relative) != digest
    ]
    if mismatches:
        raise ValueError(f"Curated release checksum mismatch: {mismatches}")
    return [release_root / relative for relative in sorted(entries)] + [manifest]


def unresolved_owner_decisions(path: Path) -> list[str]:
    if not path.is_file():
        return ["owner review record is missing"]
    section = False
    decisions: list[str] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip() == "## Owner confirmation needed":
            section = True
            continue
        if section and line.startswith("## "):
            break
        if section and line.lstrip().startswith(tuple(f"{number}." for number in range(1, 100))):
            decisions.append(line.strip())
    return decisions


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--build-root", type=Path, default=Path("build/public-release"))
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

    try:
        release_root = args.build_root.resolve() / "releases" / args.dataset_version
        objects = verified_objects(release_root)
        prefix = f"releases/{args.dataset_version}/"
        print(f"Verified {len(objects)} curated objects from {release_root}")
        for path in objects:
            content_type = CONTENT_TYPES.get(path.suffix)
            if not content_type:
                raise ValueError(f"No approved content type for {path.name}")
            print(f"  {prefix}{path.relative_to(release_root)} [{content_type}]")
        owner_review = Path(__file__).resolve().parents[1] / "internal/docs/audits/OWNER_REVIEW.md"
        owner_blockers = unresolved_owner_decisions(owner_review)
        if not args.execute:
            print(
                "Dry run only; no AWS API was called. Add --execute only after reviewing this list."
            )
            if owner_blockers:
                print(
                    f"Deployment blocked: {len(owner_blockers)} unresolved owner decision(s) "
                    "remain in the internal OWNER_REVIEW.md."
                )
            return 0

        if owner_blockers:
            raise ValueError(
                f"{len(owner_blockers)} unresolved owner decision(s) remain in internal OWNER_REVIEW.md"
            )

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

        try:
            import boto3
        except ImportError as exc:
            raise RuntimeError("boto3 is required for upload") from exc
        client = boto3.client("s3", region_name=region)
        for path in objects:
            key = prefix + str(path.relative_to(release_root))
            client.put_object(
                Bucket=bucket_name,
                Key=key,
                Body=path.read_bytes(),
                ContentType=CONTENT_TYPES[path.suffix],
                CacheControl="public, max-age=31536000, immutable",
            )
            print(f"Uploaded s3://{bucket_name}/{key}")
        return 0
    except (OSError, RuntimeError, ValueError) as exc:
        print(f"Upload refused: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
