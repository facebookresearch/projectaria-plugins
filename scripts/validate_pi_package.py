#!/usr/bin/env python3
# Copyright (c) Meta Platforms, Inc. and affiliates.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0

"""Validate the Pi package manifest and its declared resources."""

from __future__ import annotations

import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
PACKAGE_JSON = REPO_ROOT / "package.json"
RESOURCE_TYPES = ("skills",)


def _resolve_resource(resource: object, kind: str, errors: list[str]) -> Path | None:
    if not isinstance(resource, str) or not resource.startswith("./"):
        errors.append(f"pi.{kind}: resource must be a relative './' path")
        return None

    path = (REPO_ROOT / resource).resolve()
    try:
        path.relative_to(REPO_ROOT)
    except ValueError:
        errors.append(f"pi.{kind}: resource {resource!r} escapes repo root")
        return None

    if not path.exists():
        errors.append(f"pi.{kind}: resource does not exist: {resource}")
        return None
    return path


def main() -> int:
    errors: list[str] = []
    try:
        package = json.loads(PACKAGE_JSON.read_text())
    except (OSError, json.JSONDecodeError) as error:
        print(f"ERROR: unable to read package.json ({error})", file=sys.stderr)
        return 1

    keywords = package.get("keywords", [])
    if "pi-package" not in keywords:
        errors.append("package.json keywords must include 'pi-package'")

    pi_manifest = package.get("pi")
    if not isinstance(pi_manifest, dict):
        errors.append("package.json must contain a 'pi' object")
        pi_manifest = {}

    resolved: dict[str, list[Path]] = {}
    for kind in RESOURCE_TYPES:
        resources = pi_manifest.get(kind)
        if not isinstance(resources, list) or not resources:
            errors.append(f"pi.{kind} must be a non-empty array")
            continue
        resolved[kind] = [
            path
            for resource in resources
            if (path := _resolve_resource(resource, kind, errors)) is not None
        ]

    skill_files = [
        skill_file
        for skill_root in resolved.get("skills", [])
        for skill_file in skill_root.rglob("SKILL.md")
    ]
    if not skill_files:
        errors.append("pi.skills resources do not contain any SKILL.md files")

    if errors:
        print(f"\n❌ {len(errors)} Pi package validation error(s):\n", file=sys.stderr)
        for error in errors:
            print(f"  - {error}", file=sys.stderr)
        return 1

    print(f"✅ Pi package manifest OK ({len(skill_files)} skill(s))")
    return 0


if __name__ == "__main__":
    sys.exit(main())
