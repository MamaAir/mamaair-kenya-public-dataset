#!/usr/bin/env python3
"""Generate a deterministic SHA-256 manifest for publication artifacts."""

from __future__ import annotations

import argparse
import hashlib
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    args = parser.parse_args()
    root = args.root.resolve()
    manifest = root / "CHECKSUMS.sha256"
    files = sorted(
        path
        for path in root.rglob("*")
        if path.is_file()
        and path != manifest
        and "__pycache__" not in path.parts
        and not path.name.startswith(".")
    )
    lines = []
    for path in files:
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        lines.append(f"{digest}  {path.relative_to(root)}")
    manifest.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"Wrote {len(lines)} checksum entries to {manifest}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
