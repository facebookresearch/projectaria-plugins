#!/usr/bin/env python3
# Copyright (c) Meta Platforms, Inc. and affiliates.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0

"""Check that the marketplace repo has all standard OSS files at root."""

from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent

REQUIRED_FILES = [
    "README.md",
    "LICENSE",
    "CONTRIBUTING.md",
    "CODE_OF_CONDUCT.md",
    "SECURITY.md",
    "SUPPORT.md",
    ".claude-plugin/marketplace.json",
    ".agents/plugins/marketplace.json",
]


def main() -> int:
    missing = [f for f in REQUIRED_FILES if not (REPO_ROOT / f).is_file()]
    if missing:
        print("❌ Missing required repo files:", file=sys.stderr)
        for f in missing:
            print(f"  - {f}", file=sys.stderr)
        return 1
    print(f"✅ All {len(REQUIRED_FILES)} required repo files present")
    return 0


if __name__ == "__main__":
    sys.exit(main())
