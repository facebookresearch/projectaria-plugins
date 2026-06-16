---
name: vrs-cli
description: Use when the user wants to inspect, validate, or manipulate a VRS file using the native VRS command-line tools from facebookresearch/vrs — `vrs check`, `vrs print`, etc. VRS is the file format used by Aria recordings, and the native CLI is separate from `projectaria-tools` (PAT). Reach for it for file-level operations (validate, list streams, slice, copy) when you do not need Aria sensor semantics. Use whenever the user asks about the `vrs` CLI, validating a VRS file outside PAT, or quick VRS inspection without writing Python.
---

# Native VRS CLI

VRS is Meta's open container format for timestamped multi-modal sensor data — every Aria recording is one VRS file. The native VRS library ships a CLI (`vrs`) for inspecting and manipulating VRS files at the file / stream level. It is a **separate codebase** from `projectaria-tools` (PAT) and is not Aria-aware.

> VRS source + install instructions: https://github.com/facebookresearch/vrs
> Aria-specific VRS notes: https://facebookresearch.github.io/projectaria_tools/gen2/technical-specs/vrs/data-format

## When to use VRS CLI vs PAT vs vrs-health-check

| Goal | Use |
|---|---|
| Validate that a VRS file is not corrupted | `vrs check` |
| Inspect a VRS file (streams, record counts) | `vrs` CLI |
| Slice / extract / copy streams at the file level | `vrs` CLI |
| Read **decoded sensor data** (images, IMU samples in physical units) | **PAT** — see the `projectaria-tools` skill |
| Anything that needs camera calibration / projection | **PAT** |
| Aria-specific recording quality (drop rates, timing checks) | **`vrs-health-check`** (a different tool, despite the name overlap) |

The CLI does not understand Aria-specific semantics — StreamId→label mapping, the `factory_calibration` JSON, profile names, MPS outputs, etc. It only knows about VRS streams and records.

## Install

The CLI lives in the VRS GitHub repository. Follow the README at https://github.com/facebookresearch/vrs for current build and install instructions — they cover supported package managers, building from source, and per-OS dependencies. Use the latest `main` if you hit unsupported-feature errors against a newer Aria recording.

**HEVC decoder is required** for image-related operations. Aria VRS files use H.265 / HEVC for camera streams. On most Linux distros, installing `ffmpeg` from the system package manager pulls in HEVC support. See the VRS README for the specific FFmpeg version / build flags it expects.

## Usage — defer to `--help`

The CLI is self-documenting. **Always** run:

```bash
vrs --help               # list subcommands
vrs <subcommand> --help  # flag reference for the subcommand
```

Subcommand names and exact flags drift across releases — `--help` is the source of truth. Do not memorize flag spellings from this skill.

## Common patterns

- **Is this file valid?** Run `vrs check <file.vrs>`.
- **What streams are in here, and how many records?** Use the inspection / list subcommand surfaced by `vrs --help`.
- **Quick textual dump** of stream contents: the `vrs print`-family subcommands.
- **Pull out one stream** to its own VRS file, or merge several streams: file-level copy / slice subcommands.

For anything beyond inspection — actually reading and interpreting sensor data — switch to PAT.

## Gotchas

- **Missing HEVC decoder** → image operations fail or produce empty output. Install FFmpeg with HEVC.
- **Old CLI vs new file** → a VRS file from a newer firmware may use features an older CLI version does not support. Rebuild the CLI from latest `main`.
- **CLI is not Aria-aware** → it sees streams and records, not Aria's StreamId-to-label mapping. For Aria semantics, use PAT.
- **Don't confuse with `vrs-health-check`** → the `vrs-health-check` tool (separate Python package, different skill in this plugin) checks **Aria recording quality** (drop rates, timing); `vrs check` only validates the **VRS file format** is well-formed.

## Related plugin skills

- `aria-knowledge` — VRS format concept (streams, records, StreamId) + StreamId→label table.
- `projectaria-tools` — PAT API for reading sensor data with Aria semantics.
- `vrs-health-check` — Aria-specific recording quality validation (distinct from `vrs check`).
