---
name: pilot-dataset
description: Use when working with the Aria Gen2 Pilot Dataset — a multi-participant egocentric dataset with raw VRS sensor data, MPS outputs, and additional algorithm results (ASR, heart rate, hand-object interaction, depth estimation, 3D detection). Covers the projectaria-gen2-pilot-dataset package, data loaders, visualizers, and tutorials. Use whenever the user mentions pilot dataset, Gen2 pilot dataset, loading pilot data, pilot data loader, pilot dataset visualizer, projectaria_gen2_pilot_dataset, or any task involving the Aria Gen2 Pilot Dataset recordings or algorithm outputs.
---

# Aria Gen2 Pilot Dataset

A multi-participant egocentric dataset collected with Aria Gen2 glasses. Includes raw sensor data, on-device perception, cloud MPS outputs, and additional offline algorithm results.

## Sources of Truth

- **Source code** (API, data types, folder structure, CSV formats): https://github.com/facebookresearch/projectaria_gen2_pilot_dataset — if the user has cloned the repo, read the code directly. If not, fetch from GitHub or ask the user to clone it.
- **Dataset overview** (high-level description): https://facebookresearch.github.io/projectaria_tools/gen2/research-tools/dataset/pilot/content
- **Download guide**: https://facebookresearch.github.io/projectaria_tools/gen2/research-tools/dataset/pilot/download
- **Dataset explorer** (preview before download): https://explorer.projectaria.com/gen2pilot
- **Paper**: https://arxiv.org/abs/2510.16134

The source code is the authoritative source for dataset format and API. Key files in `data_provider/`:

- `aria_gen2_pilot_data_provider.py` — main `AriaGen2PilotDataProvider` class
- `aria_gen2_pilot_data_paths.py` — dataset directory structure and file locations
- `aria_gen2_pilot_dataset_data_types.py` — all data types (HeartRateData, DiarizationData, BoundingBox2D/3D, HandObjectInteractionData, etc.)
- Per-algorithm providers: `heart_rate_data_provider.py`, `diarization_data_provider.py`, `hand_object_interaction_data_provider.py`, `stereo_depth_data_provider.py`, `egocentric_voxel_lifting_data_provider.py`

## Installation

This is a **separate package** from projectaria-tools and the client SDK:

```bash
python3 -m pip install 'projectaria-gen2-pilot-dataset[all]'
```

The `[all]` extra includes core data loaders, Rerun visualization tools, all dependencies, and tutorial notebooks. Verify: `python3 -c "import projectaria_gen2_pilot_dataset"`

## Core API

The package provides a unified `AriaGen2PilotDataProvider` interface for loading all data layers — raw VRS, on-device perception, MPS outputs, and algorithm results. This is the main entry point for programmatic access.

Raw VRS data is also accessible via ProjectAriaTools (PAT) `VrsDataProvider`. MPS outputs via `projectaria_tools.core.mps`. See the projectaria-tools skill for those APIs.

For API details, read the source code — see Sources of Truth above.

## Visualizers

- **`aria_gen2_pilot_dataset_viewer --sequence-path <path>`** — interactive viewer for algorithm outputs
- **`aria_rerun_viewer --vrs <path>`** — Rerun-based viewer for raw sensor streams

## Key Details

- **License**: CC BY-NC 4.0 (non-commercial use)
- **Preview before download**: Use the Dataset Explorer for MP4 video previews and interactive 3D visualization
