#!/usr/bin/env python3
"""Require explicit authorization and match `aws sts get-caller-identity`."""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
from dataclasses import dataclass

ACCOUNT_RE = re.compile(r"^[0-9]{12}$")
REGION_RE = re.compile(r"^(?:af|ap|ca|eu|il|me|mx|sa|us)(?:-gov)?-[a-z0-9-]+-[0-9]+$")
BUCKET_RE = re.compile(r"^[a-z0-9][a-z0-9-]{1,61}[a-z0-9]$")
STREAM_RE = re.compile(r"^[A-Za-z0-9_.-]{1,128}$")
VERSION_RE = re.compile(r"^v[1-9][0-9]*$")


@dataclass(frozen=True)
class PreflightResult:
    account_id: str
    arn: str
    region: str
    bucket_name: str
    stream_name: str
    public_prefix: str


def require_value(value: str | None, label: str) -> str:
    if not value:
        raise ValueError(f"{label} is required and must be explicitly supplied")
    return value


def run_preflight(
    *,
    expected_account_id: str,
    region: str,
    bucket_name: str,
    stream_name: str,
    dataset_version: str,
    deployment_authorized: str,
) -> PreflightResult:
    if deployment_authorized != "YES":
        raise ValueError("MAMAAIR_DEPLOYMENT_AUTHORIZED must equal YES")
    if not ACCOUNT_RE.fullmatch(expected_account_id):
        raise ValueError("EXPECTED_AWS_ACCOUNT_ID must contain exactly 12 digits")
    if not REGION_RE.fullmatch(region):
        raise ValueError("AWS_REGION must be a real AWS Region identifier")
    if not BUCKET_RE.fullmatch(bucket_name):
        raise ValueError("PUBLIC_BUCKET_NAME must be a valid S3 bucket name without dots")
    if not STREAM_RE.fullmatch(stream_name):
        raise ValueError("KINESIS_STREAM_NAME is not valid")
    if not VERSION_RE.fullmatch(dataset_version):
        raise ValueError("DATASET_VERSION must use the form v1, v2, ...")
    if not shutil.which("aws"):
        raise RuntimeError("AWS CLI is not installed; no deployment action is allowed")

    command = ["aws", "sts", "get-caller-identity", "--output", "json"]
    completed = subprocess.run(command, check=False, capture_output=True, text=True)
    if completed.returncode:
        raise RuntimeError(f"aws sts get-caller-identity failed: {completed.stderr.strip()}")
    try:
        identity = json.loads(completed.stdout)
    except json.JSONDecodeError as exc:
        raise RuntimeError("AWS CLI returned invalid identity JSON") from exc
    actual_account_id = str(identity.get("Account", ""))
    if actual_account_id != expected_account_id:
        raise RuntimeError(
            f"AWS account mismatch: authenticated={actual_account_id or 'unknown'} "
            f"expected={expected_account_id}; stopping before deployment"
        )

    result = PreflightResult(
        account_id=actual_account_id,
        arn=str(identity.get("Arn", "")),
        region=region,
        bucket_name=bucket_name,
        stream_name=stream_name,
        public_prefix=f"releases/{dataset_version}/",
    )
    print("MamaAir AWS deployment preflight PASS")
    print(f"  authenticated account: {result.account_id}")
    print(f"  authenticated ARN: {result.arn}")
    print(f"  Region: {result.region}")
    print(f"  bucket: {result.bucket_name}")
    print(f"  Kinesis stream: {result.stream_name}")
    print(f"  anonymous-read scope: s3://{result.bucket_name}/{result.public_prefix}*")
    print("  anonymous writes: never allowed")
    return result


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--expected-account-id", default=os.getenv("EXPECTED_AWS_ACCOUNT_ID"))
    parser.add_argument("--region", default=os.getenv("AWS_REGION"))
    parser.add_argument("--bucket-name", default=os.getenv("PUBLIC_BUCKET_NAME"))
    parser.add_argument("--stream-name", default=os.getenv("KINESIS_STREAM_NAME"))
    parser.add_argument("--dataset-version", default=os.getenv("DATASET_VERSION", "v1"))
    parser.add_argument(
        "--deployment-authorized", default=os.getenv("MAMAAIR_DEPLOYMENT_AUTHORIZED")
    )
    args = parser.parse_args(argv)
    try:
        run_preflight(
            expected_account_id=require_value(args.expected_account_id, "EXPECTED_AWS_ACCOUNT_ID"),
            region=require_value(args.region, "AWS_REGION"),
            bucket_name=require_value(args.bucket_name, "PUBLIC_BUCKET_NAME"),
            stream_name=require_value(args.stream_name, "KINESIS_STREAM_NAME"),
            dataset_version=args.dataset_version,
            deployment_authorized=require_value(
                args.deployment_authorized, "MAMAAIR_DEPLOYMENT_AUTHORIZED"
            ),
        )
        return 0
    except (RuntimeError, ValueError) as exc:
        print(f"MamaAir AWS deployment preflight FAIL: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
