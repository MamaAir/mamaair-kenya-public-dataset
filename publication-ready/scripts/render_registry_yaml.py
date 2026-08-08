#!/usr/bin/env python3
"""Render the Registry template only when all real public AWS values exist."""

from __future__ import annotations

import argparse
import re
from pathlib import Path
from urllib.parse import urlparse

PLACEHOLDERS = {
    "{{PUBLIC_DOCUMENTATION_URL}}": "documentation_url",
    "{{PUBLIC_BUCKET_ARN}}": "bucket_arn",
    "{{AWS_REGION}}": "region",
}
SUPPORTED_TOP_LEVEL_FIELDS = {
    "Deprecated",
    "DeprecatedNotice",
    "Name",
    "Description",
    "Documentation",
    "Contact",
    "ManagedBy",
    "Citation",
    "UpdateFrequency",
    "Collabs",
    "Tags",
    "ADXCategories",
    "License",
    "Resources",
    "DataAtWork",
}
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
REGION_RE = re.compile(r"^(?:af|ap|ca|eu|il|me|mx|sa|us)(?:-gov)?-[a-z0-9-]+-\d$")
BUCKET_ARN_RE = re.compile(r"^arn:(?:aws|aws-iso):s3:::[a-z0-9][a-z0-9.-]{1,61}[a-z0-9]$")


def sequence(text: str, field: str) -> list[str]:
    values: list[str] = []
    active = False
    for line in text.splitlines():
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


def validate_template(text: str) -> None:
    top_level = {
        match.group(1)
        for line in text.splitlines()
        if (match := re.match(r"^([A-Za-z][A-Za-z &]+):(?:\s|$)", line))
    }
    unsupported = sorted(top_level - SUPPORTED_TOP_LEVEL_FIELDS)
    if unsupported:
        raise ValueError(f"Unsupported Registry top-level fields: {unsupported}")
    tags = sequence(text, "Tags")
    bad_tags = sorted(set(tags) - APPROVED_RELEASE_TAGS)
    if bad_tags or any(tag.startswith("#") for tag in tags):
        raise ValueError(f"Unsupported or hashtag Registry tags: {bad_tags or tags}")
    categories = sequence(text, "ADXCategories")
    bad_categories = sorted(set(categories) - OFFICIAL_ADX_CATEGORIES)
    if bad_categories or len(categories) > 2:
        raise ValueError(f"Invalid ADXCategories: {categories}")


def validate_url(value: str) -> None:
    parsed = urlparse(value)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise ValueError("Documentation URL must be a public http(s) URL")


def main() -> int:
    default_template = (
        Path(__file__).resolve().parents[2]
        / "internal/release-support/registry/mamaair-kenya-synthetic-maternal-health.yaml.template"
    )
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--template", type=Path, default=default_template)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--documentation-url")
    parser.add_argument("--bucket-arn")
    parser.add_argument("--region")
    parser.add_argument("--check-template", action="store_true")
    args = parser.parse_args()

    text = args.template.read_text(encoding="utf-8")
    validate_template(text)
    remaining = [token for token in PLACEHOLDERS if token in text]
    if args.check_template:
        print(
            f"Template structure is valid; unresolved placeholders: {', '.join(remaining) or 'none'}"
        )
        return 0

    owner_review = Path(__file__).resolve().parents[2] / "internal/docs/audits/OWNER_REVIEW.md"
    if owner_review.is_file():
        review_text = owner_review.read_text(encoding="utf-8")
        unresolved = re.findall(
            r"^\d+\.\s+.+$",
            review_text.partition("## Owner confirmation needed")[2],
            re.M,
        )
        if unresolved:
            raise SystemExit(
                "Refusing to render final Registry YAML while internal owner publication decisions remain unresolved"
            )

    missing_args = [
        name
        for name, value in {
            "--output": args.output,
            "--documentation-url": args.documentation_url,
            "--bucket-arn": args.bucket_arn,
            "--region": args.region,
        }.items()
        if not value
    ]
    if missing_args:
        raise SystemExit(f"Refusing to render a final YAML; missing: {', '.join(missing_args)}")
    validate_url(args.documentation_url)
    if not BUCKET_ARN_RE.fullmatch(args.bucket_arn):
        raise SystemExit(
            "Refusing to render: bucket ARN must identify a real S3 bucket and contain no prefix"
        )
    if not REGION_RE.fullmatch(args.region) or args.region.lower() == "kenya":
        raise SystemExit(
            "Refusing to render: Region must be a valid AWS Region identifier, not a country"
        )

    replacements = {
        "{{PUBLIC_DOCUMENTATION_URL}}": args.documentation_url,
        "{{PUBLIC_BUCKET_ARN}}": args.bucket_arn,
        "{{AWS_REGION}}": args.region,
    }
    rendered = text
    for token, value in replacements.items():
        rendered = rendered.replace(token, value)
    unresolved = [token for token in PLACEHOLDERS if token in rendered]
    if unresolved:
        raise SystemExit(f"Refusing to write final YAML; unresolved placeholders: {unresolved}")
    validate_template(rendered)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(rendered, encoding="utf-8")
    print(f"Rendered final Registry YAML: {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
