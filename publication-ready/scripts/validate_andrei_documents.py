#!/usr/bin/env python3
"""Verify project README and license against Andrei's authoritative ODT files."""

from __future__ import annotations

import argparse
import hashlib
import html
import re
import xml.etree.ElementTree as ET
from pathlib import Path
from zipfile import BadZipFile, ZipFile

TEXT_NS = "urn:oasis:names:tc:opendocument:xmlns:text:1.0"
OFFICE_NS = "urn:oasis:names:tc:opendocument:xmlns:office:1.0"
TEXT = f"{{{TEXT_NS}}}"
OFFICE = f"{{{OFFICE_NS}}}"

AUTHORITATIVE_DOCUMENTS = {
    "README.md": (
        "internal/andrei-source/Readme.md (1).odt",
        "7bec5247bfb1c20d82bff7165f84766c4fbd2dcd4f02a281f8a18712a2e57253",
    ),
    "LICENSE.md": (
        "internal/andrei-source/Licence.md (1).odt",
        "541d6979c1076a131a141fe01b0c0dd366565b2fb98ded72469cadc19c63ab3f",
    ),
}


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _element_text(element: ET.Element) -> str:
    parts: list[str] = []

    def walk(node: ET.Element) -> None:
        if node.text:
            parts.append(node.text)
        for child in node:
            if child.tag == f"{TEXT}s":
                parts.append(" " * int(child.attrib.get(f"{TEXT}c", "1")))
            elif child.tag == f"{TEXT}tab":
                parts.append("\t")
            elif child.tag == f"{TEXT}line-break":
                parts.append("\n")
            else:
                walk(child)
            if child.tail:
                parts.append(child.tail)

    walk(element)
    return "".join(parts).replace("\N{NO-BREAK SPACE}", " ").rstrip()


def odt_blocks(path: Path) -> list[str]:
    with ZipFile(path) as archive:
        root = ET.fromstring(archive.read("content.xml"))
    body = root.find(f".//{OFFICE}text")
    if body is None:
        raise ValueError(f"ODT has no office:text body: {path}")
    blocks = [
        _element_text(element)
        for element in body
        if element.tag in {f"{TEXT}p", f"{TEXT}h"}
    ]
    return [block for block in blocks if block.strip()]


def markdown_blocks(path: Path) -> list[str]:
    text = html.unescape(path.read_text(encoding="utf-8")).replace("\r\n", "\n")
    blocks = []
    for block in re.split(r"\n[ \t]*\n", text.strip()):
        block = re.sub(r"^#{1,6}[ \t]+", "", block)
        blocks.append(block.rstrip())
    return blocks


def validate_pair(markdown_path: Path, odt_path: Path) -> list[str]:
    expected = odt_blocks(odt_path)
    observed = markdown_blocks(markdown_path)
    if observed == expected:
        return []
    errors = []
    if len(observed) != len(expected):
        errors.append(
            f"{markdown_path.name} block count differs from {odt_path.name}: "
            f"expected={len(expected)} observed={len(observed)}"
        )
    for index, (expected_block, observed_block) in enumerate(
        zip(expected, observed, strict=False), start=1
    ):
        if observed_block != expected_block:
            errors.append(
                f"{markdown_path.name} block {index} differs from {odt_path.name}: "
                f"expected={expected_block!r} observed={observed_block!r}"
            )
    return errors


def validate(repository_root: Path) -> list[str]:
    errors: list[str] = []
    for markdown_relative, (odt_relative, expected_hash) in AUTHORITATIVE_DOCUMENTS.items():
        markdown_path = repository_root / markdown_relative
        odt_path = repository_root / odt_relative
        if not markdown_path.is_file() or not odt_path.is_file():
            errors.append(f"Missing authoritative document pair: {markdown_relative}, {odt_relative}")
            continue
        observed_hash = sha256(odt_path)
        if observed_hash != expected_hash:
            errors.append(
                f"Andrei source hash changed for {odt_relative}: "
                f"expected={expected_hash} observed={observed_hash}"
            )
            continue
        try:
            errors.extend(validate_pair(markdown_path, odt_path))
        except (BadZipFile, ET.ParseError, OSError, ValueError) as exc:
            errors.append(f"Cannot validate {markdown_relative} against {odt_relative}: {exc}")
    return errors


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--repository-root", type=Path, default=Path(__file__).resolve().parents[2]
    )
    args = parser.parse_args()
    errors = validate(args.repository_root.resolve())
    print("Andrei README/license validation")
    print(f"  errors: {len(errors)}")
    for error in errors:
        print(f"  [ERROR] {error}")
    if errors:
        return 1
    print("  README.md and LICENSE.md match the authoritative ODT text exactly: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
