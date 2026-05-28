#!/usr/bin/env python3
# Copyright (c) Meta Platforms, Inc. and affiliates.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0

"""Validate the marketplace manifest and every plugin manifest it references.

Checks:
1. `.claude-plugin/marketplace.json` is valid JSON and matches schema.
2. Every `plugins[].source` directory exists and contains
   `.claude-plugin/plugin.json`.
3. Every plugin manifest is valid JSON and matches schema.
4. Plugin names are unique across the marketplace.
5. Plugin manifest `name` matches the marketplace entry `name`.
6. Each plugin has README.md.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import jsonschema

REPO_ROOT = Path(__file__).resolve().parent.parent
MARKETPLACE_JSON = REPO_ROOT / ".claude-plugin" / "marketplace.json"
SCHEMAS_DIR = REPO_ROOT / ".claude-plugin" / "schemas"


def _fail(msg: str, errors: list[str]) -> None:
    errors.append(msg)


def _load_json(path: Path, errors: list[str]) -> dict | None:
    try:
        return json.loads(path.read_text())
    except FileNotFoundError:
        _fail(f"Missing file: {path.relative_to(REPO_ROOT)}", errors)
    except json.JSONDecodeError as e:
        _fail(f"Invalid JSON in {path.relative_to(REPO_ROOT)}: {e}", errors)
    return None


def _validate_against_schema(
    instance: dict, schema_path: Path, label: str, errors: list[str]
) -> None:
    schema = json.loads(schema_path.read_text())
    validator = jsonschema.Draft7Validator(schema)
    for err in sorted(validator.iter_errors(instance), key=lambda e: e.path):
        loc = "/".join(str(p) for p in err.absolute_path) or "<root>"
        _fail(f"[{label}] {loc}: {err.message}", errors)


def _resolve_plugin_dir(label: str, source: str, errors: list[str]) -> Path | None:
    if not source.startswith("./"):
        _fail(f"{label}: source must start with './'", errors)
        return None

    plugin_dir = (REPO_ROOT / source).resolve()
    try:
        plugin_dir.relative_to(REPO_ROOT)
    except ValueError:
        _fail(f"{label}: source {source!r} escapes repo root", errors)
        return None

    if not plugin_dir.is_dir():
        _fail(f"{label}: source directory does not exist: {source}", errors)
        return None

    return plugin_dir


def _validate_plugin_entry(
    entry: dict,
    plugin_names_seen: dict[str, str],
    errors: list[str],
) -> None:
    entry_name = entry.get("name")
    source = entry.get("source", "")
    label = f"plugins[{entry_name!r}]"

    if entry_name in plugin_names_seen:
        _fail(
            f"{label}: duplicate plugin name (also at {plugin_names_seen[entry_name]})",
            errors,
        )
    plugin_names_seen[entry_name] = source

    plugin_dir = _resolve_plugin_dir(label, source, errors)
    if plugin_dir is None:
        return

    plugin_json_path = plugin_dir / ".claude-plugin" / "plugin.json"
    plugin_json = _load_json(plugin_json_path, errors)
    if plugin_json is None:
        return

    _validate_against_schema(
        plugin_json,
        SCHEMAS_DIR / "plugin.schema.json",
        f"{source}/.claude-plugin/plugin.json",
        errors,
    )

    if plugin_json.get("name") != entry_name:
        _fail(
            f"{label}: marketplace name {entry_name!r} does not match "
            f"plugin.json name {plugin_json.get('name')!r}",
            errors,
        )

    readme = plugin_dir / "README.md"
    if not readme.is_file():
        _fail(f"{label}: missing {readme.relative_to(REPO_ROOT)}", errors)

    skills_dir = plugin_dir / "skills"
    if not skills_dir.is_dir():
        _fail(
            f"{label}: missing skills/ directory at "
            f"{skills_dir.relative_to(REPO_ROOT)}",
            errors,
        )


def main() -> int:
    errors: list[str] = []

    marketplace = _load_json(MARKETPLACE_JSON, errors)
    if marketplace is None:
        for e in errors:
            print(f"ERROR: {e}", file=sys.stderr)
        return 1

    _validate_against_schema(
        marketplace,
        SCHEMAS_DIR / "marketplace.schema.json",
        "marketplace.json",
        errors,
    )

    plugin_names_seen: dict[str, str] = {}
    for entry in marketplace.get("plugins", []):
        _validate_plugin_entry(entry, plugin_names_seen, errors)

    if errors:
        print(f"\n❌ {len(errors)} marketplace validation error(s):\n", file=sys.stderr)
        for e in errors:
            print(f"  - {e}", file=sys.stderr)
        return 1

    print(f"✅ marketplace.json OK ({len(plugin_names_seen)} plugin(s) validated)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
