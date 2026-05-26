---
name: mps
description: Use when working with Aria Machine Perception Services (MPS) — cloud-based processing of Aria VRS recordings for SLAM trajectories, hand tracking, semi-dense point clouds, and online calibration. Covers the aria_mps CLI, single and multi-sequence processing, output formats, data lifecycle, and loading MPS results with ProjectAriaTools. Use whenever the user mentions MPS, aria_mps, SLAM processing, cloud hand tracking, trajectory generation, or submitting VRS files for processing.
---

# Machine Perception Services (MPS)

MPS is a cloud-based post-processing service for Aria recordings. You submit VRS files via the `aria_mps` CLI, MPS runs proprietary Spatial AI algorithms, and you download the derived outputs (trajectories, point clouds, hand tracking). The data is only used to serve requests — not accessible to Meta researchers.

## How to Use This Skill

This skill teaches concepts and capabilities. For details, use the authoritative sources:

- **CLI**: `aria_mps --help`, `aria_mps single --help`, `aria_mps multi --help`
- **Data formats, coordinate conventions, CSV columns**: https://facebookresearch.github.io/projectaria_tools/gen2/technical-specs/mps/data_formats
- **CLI workflow details**: https://facebookresearch.github.io/projectaria_tools/gen2/technical-specs/mps/mps_cli_guide
- **Service versions and algorithm details**: https://facebookresearch.github.io/projectaria_tools/gen2/ark/mps/mps_versioning
- **Benchmarks and performance**: https://facebookresearch.github.io/projectaria_tools/gen2/technical-specs/mps/benchmarks/performance
- **Python API for loading results**: Read `help(projectaria_tools.core.mps)` or `MpsPyBind.h` in the cloned repo. See the projectaria-tools skill.

## Installation

- **Install**: `pip install projectaria-mps` (automatically includes `projectaria-tools` and `projectaria-vrs-health-check`)
- **CLI command**: `aria_mps`
- **Auth**: On first run, authenticate with your Project Aria account. Tokens are cached in the system keychain for subsequent runs.
- **Configuration**: `$HOME/.projectaria/mps.ini` — concurrency, chunk sizes, retry logic.
- **Docs**: https://facebookresearch.github.io/projectaria_tools/gen2/ark/mps/start

## Capabilities Overview

### Services

MPS provides three services. Services are independent — you can request any combination. VRS health check runs automatically before processing.

- **SLAM**: 6DoF trajectory (open-loop VIO + closed-loop bundle-adjusted, both at 1kHz), semi-dense point cloud, time-varying sensor calibration. Requires CV cameras + IMU.
- **Multi-SLAM**: Processes multiple recordings of the same physical space together to produce outputs in a shared coordinate frame. Use when you need spatially aligned trajectories and point clouds across devices.
- **Hand Tracking**: 21 hand landmark positions, 6DoF hand-to-device transform, wrist and palm normals, per-frame confidence. Requires CV cameras ≥10fps + IMU.

Check the versioning docs for current service versions and the benchmarks page for accuracy metrics.

### Processing Modes

- **Single** (`aria_mps single`): Process recordings independently. When pointed at a directory, recursively discovers all VRS files and processes concurrently (default 25, configurable up to 100).
- **Multi** (`aria_mps multi`): Process multiple recordings together for Multi-SLAM in a shared coordinate frame.
- **`--features`**: Select specific services (e.g. `SLAM`, `HAND_TRACKING`). Default: all applicable.
- **`--force`**: Bypass deduplication cache and reprocess.
- **`--no-ui`**: Headless mode for scripted/automated pipelines.

### Processing Pipeline

The CLI executes stages sequentially: status check → health check → encryption → upload (resumable within 24h) → server processing → download. Quitting after upload lets processing continue in the background — results download automatically when you rerun.

## Output Structure

Results are saved alongside the input VRS file in a sibling folder. The structure includes separate directories for each service (slam/, hand_tracking/) plus a VRS health check report. Each service folder contains data files (CSV/JSON) and a `summary.json` with quality metrics.

See the data formats docs for exact CSV column definitions, coordinate conventions, and timestamp semantics.

### Key Concepts for Working with Outputs

- **Closed-loop vs open-loop trajectory**: Closed-loop is drift-corrected via loop closure — use for research. Open-loop is VIO-only — good local accuracy but drifts over time.
- **Coordinate frames**: Closed-loop trajectory is in a gravity-aligned world frame. Hand tracking is in device frame. Combine them via matching timestamps.
- **Timestamps**: `tracking_timestamp_us` (device clock, monotonic, stable) is for time calculations. `utc_timestamp_ns` (wall clock) is NOT monotonic — avoid for durations.
- **`graph_uid`**: Identifies the world coordinate frame. Data sharing the same `graph_uid` is spatially consistent.
- **`quality_score`**: Per-pose confidence (0–1). Filter low-quality poses for downstream use.
- **Semi-dense point cloud**: Join observations to points via `uid` for per-frame 2D-3D correspondences.

## Data Lifecycle

- **Uploaded VRS**: Stored up to 30 days, then auto-deleted
- **MPS outputs**: Available for re-download for 30 days
- **Access**: Only the requesting account can download
- **Deduplication**: Same VRS file hash returns cached results. Use `--force` to bypass.

## On-Device vs Cloud Processing

On-device eye gaze and VIO are embedded in the VRS during recording (accessible via PAT Tutorial_4 and Tutorial_5). Cloud MPS produces substantially better results using offline algorithms — higher accuracy for both SLAM and hand tracking. See the benchmarks page for quantitative comparisons.

## Troubleshooting

- Check `summary.json` for per-service status (SUCCESS/WARNING/ERROR) and quality metrics
- MPS requires a valid VRS health check — fix health check issues first
- Short recordings (<30s) may lack enough data for SLAM loop closure
- Featureless environments, pure rotation, or extreme motion blur degrade SLAM quality
- Docs: https://facebookresearch.github.io/projectaria_tools/gen2/ark/support/sdk
