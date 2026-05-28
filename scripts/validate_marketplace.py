#!/usr/bin/env python3
# Copyright (c) Meta Platforms, Inc. and affiliates.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0

"""Validate marketplace manifests and every plugin manifest they reference.

Checks:
1. `.claude-plugin/marketplace.json` is valid JSON and matches schema.
2. `.agents/plugins/marketplace.json` is valid JSON.
3. Every `plugins[].source` directory exists and contains
   `.claude-plugin/plugin.json`.
4. Every Codex plugin source directory contains `.codex-plugin/plugin.json`.
5. Every plugin manifest is valid JSON and matches schema or local rules.
6. Plugin names are unique across each marketplace.
7. Plugin manifest `name` matches the marketplace entry `name`.
8. Each plugin has README.md.
9. `gemini-extension.json` is valid JSON with required fields and its
   `contextFileName` points to an existing file.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import jsonschema

REPO_ROOT = Path(__file__).resolve().parent.parent
CLAUDE_MARKETPLACE_JSON = REPO_ROOT / ".claude-plugin" / "marketplace.json"
CLAUDE_SCHEMAS_DIR = REPO_ROOT / ".claude-plugin" / "schemas"
CODEX_MARKETPLACE_JSON = REPO_ROOT / ".agents" / "plugins" / "marketplace.json"
GEMINI_EXTENSION_JSON = REPO_ROOT / "gemini-extension.json"
CODEX_INSTALLATION_POLICIES = {
    "NOT_AVAILABLE",
    "AVAILABLE",
    "INSTALLED_BY_DEFAULT",
}
CODEX_AUTHENTICATION_POLICIES = {
    "ON_INSTALL",
    "ON_USE",
}


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


def _resolve_plugin_dir(label: str, source_path: str, errors: list[str]) -> Path | None:
    if not source_path.startswith("./"):
        _fail(f"{label}: source path must start with './'", errors)
        return None

    plugin_dir = (REPO_ROOT / source_path).resolve()
    try:
        plugin_dir.relative_to(REPO_ROOT)
    except ValueError:
        _fail(f"{label}: source path {source_path!r} escapes repo root", errors)
        return None

    if not plugin_dir.is_dir():
        _fail(f"{label}: source directory does not exist: {source_path}", errors)
        return None

    return plugin_dir


def _validate_claude_plugin_entry(
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
        CLAUDE_SCHEMAS_DIR / "plugin.schema.json",
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


def _expect_string(obj: dict, key: str, label: str, errors: list[str]) -> str | None:
    value = obj.get(key)
    if not isinstance(value, str) or not value:
        _fail(f"{label}: missing or invalid string field {key!r}", errors)
        return None
    return value


def _validate_codex_plugin_manifest(
    plugin_json: dict, manifest_label: str, entry_name: str, errors: list[str]
) -> None:
    plugin_name = _expect_string(plugin_json, "name", manifest_label, errors)
    _expect_string(plugin_json, "description", manifest_label, errors)
    _expect_string(plugin_json, "version", manifest_label, errors)

    if plugin_name != entry_name:
        _fail(
            f"{manifest_label}: marketplace name {entry_name!r} does not match "
            f"plugin.json name {plugin_name!r}",
            errors,
        )

    skills = plugin_json.get("skills")
    if skills is not None and (
        not isinstance(skills, str) or not skills.startswith("./")
    ):
        _fail(f"{manifest_label}: skills must be a relative './' path", errors)

    interface = plugin_json.get("interface")
    if interface is not None and not isinstance(interface, dict):
        _fail(f"{manifest_label}: interface must be an object", errors)


def _validate_codex_plugin_entry(
    entry: dict,
    plugin_names_seen: dict[str, str],
    errors: list[str],
) -> None:
    entry_name = _expect_string(entry, "name", "codex plugins[]", errors)
    source = entry.get("source")
    label = f"codex plugins[{entry_name!r}]"

    if entry_name is None:
        return
    if entry_name in plugin_names_seen:
        _fail(
            f"{label}: duplicate plugin name (also at {plugin_names_seen[entry_name]})",
            errors,
        )
    if not isinstance(source, dict):
        _fail(f"{label}: source must be an object", errors)
        return

    source_kind = source.get("source")
    source_path = source.get("path")
    if source_kind != "local":
        _fail(f"{label}: source.source must be 'local'", errors)
    if not isinstance(source_path, str):
        _fail(f"{label}: source.path must be a string", errors)
        return

    plugin_names_seen[entry_name] = source_path
    plugin_dir = _resolve_plugin_dir(label, source_path, errors)
    if plugin_dir is None:
        return

    policy = entry.get("policy")
    if not isinstance(policy, dict):
        _fail(f"{label}: policy must be an object", errors)
    else:
        installation = policy.get("installation")
        authentication = policy.get("authentication")
        if installation not in CODEX_INSTALLATION_POLICIES:
            _fail(f"{label}: invalid policy.installation {installation!r}", errors)
        if authentication not in CODEX_AUTHENTICATION_POLICIES:
            _fail(f"{label}: invalid policy.authentication {authentication!r}", errors)

    _expect_string(entry, "category", label, errors)

    plugin_json_path = plugin_dir / ".codex-plugin" / "plugin.json"
    plugin_json = _load_json(plugin_json_path, errors)
    if plugin_json is None:
        return

    _validate_codex_plugin_manifest(
        plugin_json,
        f"{source_path}/.codex-plugin/plugin.json",
        entry_name,
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


def _validate_claude_marketplace(errors: list[str]) -> int:
    marketplace = _load_json(CLAUDE_MARKETPLACE_JSON, errors)
    if marketplace is None:
        return 0

    _validate_against_schema(
        marketplace,
        CLAUDE_SCHEMAS_DIR / "marketplace.schema.json",
        ".claude-plugin/marketplace.json",
        errors,
    )

    plugin_names_seen: dict[str, str] = {}
    for entry in marketplace.get("plugins", []):
        _validate_claude_plugin_entry(entry, plugin_names_seen, errors)
    return len(plugin_names_seen)


def _validate_codex_marketplace(errors: list[str]) -> int:
    marketplace = _load_json(CODEX_MARKETPLACE_JSON, errors)
    if marketplace is None:
        return 0

    _expect_string(marketplace, "name", ".agents/plugins/marketplace.json", errors)
    interface = marketplace.get("interface")
    if interface is not None and not isinstance(interface, dict):
        _fail(".agents/plugins/marketplace.json: interface must be an object", errors)

    plugins = marketplace.get("plugins")
    if not isinstance(plugins, list) or not plugins:
        _fail(
            ".agents/plugins/marketplace.json: plugins must be a non-empty list",
            errors,
        )
        return 0

    plugin_names_seen: dict[str, str] = {}
    for entry in plugins:
        if not isinstance(entry, dict):
            _fail(
                ".agents/plugins/marketplace.json: plugin entries must be objects",
                errors,
            )
            continue
        _validate_codex_plugin_entry(entry, plugin_names_seen, errors)
    return len(plugin_names_seen)


def _validate_gemini_extension(errors: list[str]) -> bool:
    ext = _load_json(GEMINI_EXTENSION_JSON, errors)
    if ext is None:
        return False

    start = len(errors)
    label = "gemini-extension.json"
    for field in ("name", "contextFileName"):
        _expect_string(ext, field, label, errors)

    context_file = ext.get("contextFileName")
    if isinstance(context_file, str) and context_file:
        context_path = (REPO_ROOT / context_file).resolve()
        try:
            context_path.relative_to(REPO_ROOT)
        except ValueError:
            _fail(
                f"{label}: contextFileName {context_file!r} escapes repo root",
                errors,
            )
            return len(errors) == start
        if not context_path.is_file():
            _fail(
                f"{label}: contextFileName {context_file!r} does not exist",
                errors,
            )
    return len(errors) == start


def main() -> int:
    errors: list[str] = []

    claude_plugin_count = _validate_claude_marketplace(errors)
    codex_plugin_count = _validate_codex_marketplace(errors)
    gemini_ok = _validate_gemini_extension(errors)

    if errors:
        print(f"\n❌ {len(errors)} marketplace validation error(s):\n", file=sys.stderr)
        for e in errors:
            print(f"  - {e}", file=sys.stderr)
        return 1

    parts = [
        f"{claude_plugin_count} Claude plugin(s)",
        f"{codex_plugin_count} Codex plugin(s)",
    ]
    if gemini_ok:
        parts.append("Gemini extension")
    print(f"✅ marketplace manifests OK ({', '.join(parts)} validated)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
