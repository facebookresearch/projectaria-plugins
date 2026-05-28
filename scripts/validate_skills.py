#!/usr/bin/env python3
# Copyright (c) Meta Platforms, Inc. and affiliates.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0

"""Validate every SKILL.md file in the repo.

Checks for each SKILL.md under <plugin>/skills/<skill_name>/SKILL.md:
1. File parses as YAML frontmatter + markdown body.
2. Frontmatter has required `name` and `description` keys.
3. `name` matches the parent directory name (kebab-case).
4. `name` is unique within a plugin.
5. `description` is non-empty and >= 20 characters.
6. Body contains at least one heading (`#`).
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

import frontmatter
import yaml

REPO_ROOT = Path(__file__).resolve().parent.parent
# Anchored kebab-case: starts with a letter, hyphens must be between
# alphanumeric segments (disallows `a-`, `a--a`, trailing hyphens, etc.).
KEBAB_RE = re.compile(r"^[a-z][a-z0-9]*(-[a-z0-9]+)*$")
MIN_DESCRIPTION_LEN = 20


def _validate_name(
    name: object,
    rel: Path,
    dir_name: str,
    plugin: str,
    seen_per_plugin: dict[str, set[str]],
    errors: list[str],
) -> None:
    if not name:
        errors.append(f"{rel}: missing required frontmatter key `name`")
        return
    if not isinstance(name, str):
        errors.append(f"{rel}: `name` must be a string")
        return
    if not KEBAB_RE.match(name):
        errors.append(
            f"{rel}: `name` {name!r} must be kebab-case ([a-z][a-z0-9]*(-[a-z0-9]+)*)"
        )
    if name != dir_name:
        errors.append(f"{rel}: `name` {name!r} does not match parent dir {dir_name!r}")
    seen = seen_per_plugin.setdefault(plugin, set())
    if name in seen:
        errors.append(f"{rel}: duplicate skill name {name!r} within {plugin}")
    seen.add(name)


def _validate_description(description: object, rel: Path, errors: list[str]) -> None:
    if not description:
        errors.append(f"{rel}: missing required frontmatter key `description`")
        return
    if not isinstance(description, str):
        errors.append(f"{rel}: `description` must be a string")
        return
    if len(description.strip()) < MIN_DESCRIPTION_LEN:
        errors.append(
            f"{rel}: `description` is too short (must be >= "
            f"{MIN_DESCRIPTION_LEN} chars)"
        )


def _validate_skill(
    path: Path,
    seen_per_plugin: dict[str, set[str]],
    errors: list[str],
) -> None:
    rel = path.relative_to(REPO_ROOT)
    plugin = path.parts[-4]
    dir_name = path.parent.name

    try:
        post = frontmatter.load(path)
    except (OSError, UnicodeDecodeError, yaml.YAMLError) as e:
        errors.append(f"{rel}: failed to parse frontmatter ({e})")
        return

    fm = post.metadata
    body = post.content

    _validate_name(fm.get("name"), rel, dir_name, plugin, seen_per_plugin, errors)
    _validate_description(fm.get("description"), rel, errors)

    if not re.search(r"^#\s+\S", body, re.MULTILINE):
        errors.append(f"{rel}: body must contain at least one markdown heading")


def main() -> int:
    errors: list[str] = []
    skill_files = sorted(REPO_ROOT.glob("*/skills/*/SKILL.md"))

    if not skill_files:
        print("ERROR: no SKILL.md files found", file=sys.stderr)
        return 1

    seen_per_plugin: dict[str, set[str]] = {}
    for path in skill_files:
        _validate_skill(path, seen_per_plugin, errors)

    if errors:
        print(f"\n❌ {len(errors)} skill validation error(s):\n", file=sys.stderr)
        for e in errors:
            print(f"  - {e}", file=sys.stderr)
        return 1

    print(f"✅ All {len(skill_files)} SKILL.md file(s) valid")
    return 0


if __name__ == "__main__":
    sys.exit(main())
