#!/usr/bin/env python3
"""Verify authenticated/public reads and prove anonymous writes are denied."""

from __future__ import annotations

import argparse
import hashlib
import os
import sys
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

from deployment.aws_preflight import require_value, run_preflight
from deployment.upload_public_release import verified_objects

ROOT = Path(__file__).resolve().parents[1]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--build-root", type=Path, default=ROOT / "build/public-release")
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
    if not args.execute:
        print("Dry run only. Add --execute after upload to verify deployed access controls.")
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

        release_root = args.build_root.resolve() / "releases" / args.dataset_version
        objects = verified_objects(release_root)
        client = boto3.client("s3", region_name=region)
        base = f"https://{bucket_name}.s3.{region}.amazonaws.com"
        prefix = f"releases/{args.dataset_version}/"
        for local_path in objects:
            relative = str(local_path.relative_to(release_root))
            key = prefix + relative
            client.head_object(Bucket=bucket_name, Key=key)
            url = f"{base}/{urllib.parse.quote(key)}"
            with urllib.request.urlopen(url, timeout=30) as response:
                body = response.read()
                if response.status != 200:
                    raise RuntimeError(f"Anonymous GET returned {response.status}: {url}")
            if (
                hashlib.sha256(body).hexdigest()
                != hashlib.sha256(local_path.read_bytes()).hexdigest()
            ):
                raise RuntimeError(f"Anonymous GET checksum mismatch: {url}")
            print(f"Verified authenticated HEAD and anonymous GET: {url}")

        probe_key = prefix + "verification/anonymous-write-must-fail.txt"
        probe_url = f"{base}/{urllib.parse.quote(probe_key)}"
        request = urllib.request.Request(
            probe_url,
            data=b"anonymous writes must be denied\n",
            method="PUT",
            headers={"Content-Type": "text/plain"},
        )
        unexpected_write = False
        try:
            with urllib.request.urlopen(request, timeout=30) as response:
                unexpected_write = 200 <= response.status < 300
        except urllib.error.HTTPError as exc:
            if exc.code not in {401, 403}:
                raise RuntimeError(f"Anonymous write returned unexpected HTTP {exc.code}") from exc
            print(f"Verified anonymous PUT denied with HTTP {exc.code}: {probe_url}")
        if unexpected_write:
            client.delete_object(Bucket=bucket_name, Key=probe_key)
            raise RuntimeError(
                "CRITICAL: anonymous write unexpectedly succeeded; exact probe object was deleted"
            )
        return 0
    except (OSError, RuntimeError, ValueError) as exc:
        print(f"Public release verification FAIL: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
