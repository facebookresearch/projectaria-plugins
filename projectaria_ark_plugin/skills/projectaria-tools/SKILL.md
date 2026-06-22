---
name: projectaria-tools
description: Use when working with projectaria_tools (PAT) — the official Python/C++ library for reading Aria VRS recordings, accessing sensor data, device calibration, loading MPS results (eye gaze, hand tracking, SLAM trajectory), time domain mapping for multi-device alignment, and data visualization. Use whenever the user imports projectaria_tools, works with Aria VRS files, or asks about Aria sensor data processing.
---

# ProjectAriaTools (PAT)

PAT is the foundational open-source library for accessing and processing data recorded by Project Aria glasses. It provides Python and C++ interfaces for loading VRS files, accessing calibration, processing sensor data, loading MPS results, and visualizing Aria data.

## How to Use This Skill

This skill is a navigation map — it tells you where the key APIs and source files are, what the gotchas are, and where to find the truth. **Never guess API names from this skill alone.** Read the source file it points to before writing any API call.

- For CLI flags, run `--help` instead of guessing from this skill.
- For API details, read the relevant Python module or C++ pybind header.

## Installation & Documentation

- **GitHub**: https://github.com/facebookresearch/projectaria_tools
- **Docs**: https://facebookresearch.github.io/projectaria_tools/gen2/research-tools/projectariatools/overview
- **Install** (pip in a virtual environment):

  ```bash
  python3 -m venv $HOME/projectaria_gen2_python_env
  source $HOME/projectaria_gen2_python_env/bin/activate
  python3 -m pip install 'projectaria-tools[all]'
  ```

- **Supported**: Linux x64 (Ubuntu/Fedora), macOS Apple Silicon (M1+). Python 3.9–3.12.
- **Build from source**: See `CMakeLists.txt` at repo root and the Advanced Installation docs.

## Key Source Paths

After cloning the repo, these are the source-of-truth files for API details:

| What | Path |
|------|------|
| C++ pybind: VrsDataProvider API | `core/python/VrsDataProviderPyBind.h` |
| C++ pybind: SensorData accessors | `core/python/SensorDataPyBind.h` |
| C++ pybind: Calibration | `core/python/DeviceCalibrationPyBind.h` |
| C++ pybind: MPS data | `core/python/MpsPyBind.h` |
| C++ pybind: SE3/Sophus | `core/python/sophus/` |
| MPS types (eye gaze, hand, trajectory) | `core/mps/` |
| TimeDomain enum | `core/data_provider/TimeTypes.h` |
| Python package (pip-installed API) | `projectaria_tools/core/` |
| Visualization tools | `projectaria_tools/tools/` |
| Gen2 tutorials | `examples/Gen2/python_notebooks/` |

**The Python package** (`projectaria_tools/core/`) exposes the compiled C++ modules. The C++ pybind headers (`core/python/`) are the definitive API reference — read them when you need exact method signatures, return types, or parameter semantics.

## Core API

```python
from projectaria_tools.core import data_provider
from projectaria_tools.core.sensor_data import SensorDataType

provider = data_provider.create_vrs_data_provider("recording.vrs")
```

**Key constraint**: `create_vrs_data_provider` requires a **local file path**. Does NOT accept URLs or remote URIs.

### Data Access

VrsDataProvider offers methods for stream discovery, indexed and time-based data access, calibration, and image configuration. **Read `core/python/VrsDataProviderPyBind.h` for the complete typed API.**

Access sensor data by index or by timestamp. Time-based queries take a `TimeDomain` and `TimeQueryOptions`.

### Sensor Data

Each `SensorData` object has typed accessors for: image, IMU, magnetometer, barometer, GPS, audio, eye tracking, WiFi, Bluetooth. **Read `core/python/SensorDataPyBind.h` for all accessors and return types.**

Gotchas:

- Magnetometer shares the `MotionData` type with IMU — check validity flags to distinguish.
- All sensor data is timestamped; retrieve via the time accessor with an optional `TimeDomain` argument.

### VRS Streams and Stream Labels

Each VRS stream is identified by a `StreamId` = `RecordableTypeId-InstanceId` (e.g. `214-1`). PAT maps these to human-readable labels. Docs: https://facebookresearch.github.io/projectaria_tools/gen2/technical-specs/vrs/streamid-label-mapper

| StreamId | Label | Sensor |
|----------|-------|--------|
| `1201-1` / `1201-2` | `camera-slam-left` / `camera-slam-right` | SLAM cameras (grayscale) |
| `1201-3` / `1201-4` | SLAM cameras 3/4 | Additional SLAM cameras |
| `214-1` | `camera-rgb` | RGB camera (12MP) |
| `211-1` / `211-2` | `camera-et-left` / `camera-et-right` | Eye tracking cameras |
| `1202-1` / `1202-2` | `imu-left` / `imu-right` | IMUs |
| `1203-1` | `mag0` | Magnetometer |
| `247-1` | `baro0` | Barometer |
| `281-2` | `gps` | GPS sensor |
| `281-1` | `gps-app` | GPS from companion app |
| `231-1` | `mic` | 7-channel microphone |
| `246-1` | `temperature` | Temperature sensor |
| `500-1` | `als` | Ambient light sensor |
| `248-1` | `ppg` | Photoplethysmography |
| `373-1` | `eyegaze` | On-device eye gaze |
| `282-1` | `wps` | Wi-Fi |
| `283-1` | `bluetooth` | Bluetooth |

**Dynamic StreamIds**: `handtracking`, `vio`, and `vio_high_frequency` streams have runtime-determined IDs that depend on whether hand tracking is present in the recording.

Each data record contains sensor readout values, timestamps, and acquisition parameters (e.g. exposure/gain for cameras). Image records store one frame + metadata per record; audio records group 4096 samples per chunk. VRS data format docs: https://facebookresearch.github.io/projectaria_tools/gen2/technical-specs/vrs/data-format

### Time Domains

```python
from projectaria_tools.core.sensor_data import TimeDomain
```

| Value | Description |
|-------|-------------|
| `RECORD_TIME` | VRS file order |
| `DEVICE_TIME` | Hardware clock — use for single-device workflows |
| `HOST_TIME` | Wall clock on companion host |
| `TIME_CODE` | External sync signal (Gen1) |
| `SUBGHZ` | Broadcaster's device time — use for multi-device alignment (Gen2) |

`TimeQueryOptions`: `BEFORE` (latest sample ≤ query time), `AFTER` (earliest sample ≥ query time), `CLOSEST` (nearest by absolute difference).

### Calibration

Device and per-sensor calibration — focal length, principal point, distortion models, image undistortion. **Read `core/python/DeviceCalibrationPyBind.h`** for the full API and `core/calibration/` for camera model details.

### SE3 Transforms

6-DOF rigid body transforms (rotation + translation):

```python
from projectaria_tools.core.sophus import SE3
```

Supports translation, rotation, matrix conversion, inversion, composition, point transformation. **Read `core/python/sophus/`** for the full API.

### Detecting Gen1 vs Gen2

Gen1 vs Gen2 can be distinguished from the `device_type` field in the image configuration. Read `core/python/VrsDataProviderPyBind.h` for how to access it.

## MPS Data Loading

Load cloud MPS results alongside VRS data:

```python
from projectaria_tools.core import mps
```

**Read `core/python/MpsPyBind.h`** for all reader functions and return types.

Key concepts:

- **Trajectory**: timestamps + SE3 poses (`T_world_device`)
- **Point cloud**: 3D points in world coordinates; observations: 2D pixel coords per frame. Join observations to points via `uid`.
- **Hand tracking**: `from projectaria_tools.core.mps import hand_tracking`
- **Compression**: `.csv.gz` files are auto-detected from file extension.

**Eye gaze gotcha**: There is **no `.gaze_direction` attribute**. Always use the helper functions from `MpsPyBind.h` to convert yaw/pitch to unit vectors and 3D points.

## Time Domain Mapping (Multi-Device Alignment)

PAT provides time domain mapping to temporally align data across multiple Aria Gen2 devices. The underlying mechanism uses sub-GHz radio hardware for sub-millisecond accuracy.

### Host/Client Model

- **Host (Broadcaster)**: Transmits timestamps over sub-GHz radio. Its VRS does NOT contain a SubGHz stream — its `DEVICE_TIME` IS the reference.
- **Client (Receiver)**: Records `(broadcaster_time, local_time)` pairs into a SubGHz stream in its VRS. PAT uses these to map between device clocks.

### Usage Pattern

1. For host: query data in `DEVICE_TIME`
2. For clients: query data with the host's timestamp using `TimeDomain.SUBGHZ` — PAT handles the clock mapping automatically
3. Check time domain mapping availability on a provider — only present in client/receiver VRS files

Tutorial_6 demonstrates the complete multi-device time domain mapping workflow with Rerun visualization.

### Comparison with Gen1

| Protocol | Generation | Accuracy | Notes |
|----------|-----------|----------|-------|
| SubGHz time domain mapping | Gen2 | Sub-millisecond | Hardware radio, broadcaster/receiver setup |
| TICSync | Gen1 | Moderate | Software-based, client/server over network |
| TimeCode | Gen1 | Varies | External timecode signal (SMPTE) |

## Gen2 Tutorials

Path: `examples/Gen2/python_notebooks/`

| Tutorial | Content |
|----------|---------|
| Tutorial_1 | VrsDataProvider basics — read multimodal sensor data |
| Tutorial_2 | Device calibration |
| Tutorial_3 | Sequential multi-sensor access (queued data streaming) |
| Tutorial_4 | Eye tracking + hand tracking (on-device) |
| Tutorial_5 | On-device VIO |
| Tutorial_6 | Timestamp alignment (multi-device SubGHz) |
| Tutorial_7 | MPS DataProvider basics |

Tutorial_4 covers on-device eye gaze (lower accuracy, immediate). Cloud MPS provides higher accuracy but requires upload + processing.

## Visualization & Data Export

Tools shipped with PAT — installed with `pip install 'projectaria-tools[all]'`, **except** `aria_viewer` which needs a CMake source build.

**Always run `<tool> --help` for the current flag set.** Do not assume flag names from memory or from this skill — they drift across releases, and the `--help` output is the only authoritative reference.

### `aria_rerun_viewer` (Python, Rerun)

Rerun-based interactive viewer for any VRS file. Works on Gen 1 and Gen 2. Renders camera frames alongside IMU / audio / barometer / magnetometer time series, and overlays on-device perception (VIO trajectory, eye gaze, hand tracking) in a 3D scene.

**Use when**: you want a quick interactive look at a VRS file — one tool covers most sensor streams. Default first choice for "just show me what's in this recording".

Source: https://github.com/facebookresearch/projectaria_tools/tree/main/projectaria_tools/tools/aria_rerun_viewer

### `viewer_mps` (Python, Rerun)

Rerun-based viewer specialized for **MPS output overlays** — trajectories, semi-dense point clouds, eye gaze, hand tracking. Auto-detects MPS data under `<vrs_file>/mps/`, or accepts individual file paths. Supports both a desktop window and a web-browser mode.

**Use when**: you need to validate or visually inspect MPS results against the source VRS — see how trajectory + point cloud + sensor frames align in 3D.

Source: https://github.com/facebookresearch/projectaria_tools/tree/main/projectaria_tools/tools/viewer_mps

### `aria_viewer` (C++ / Pangolin)

Native-performance VRS viewer built with Pangolin. **Not in the pip package** — requires a CMake source build (see Advanced Installation in the repo README). If Pangolin isn't found during the build, the viewer simply isn't compiled.

**Use when**: you need native playback performance, or you're already in a C++ build environment.

**Known issue**: high-frequency Gen 2 playback can show asynchronous camera updates (CPU image-decode limits). Workarounds: fall back to `aria_rerun_viewer`, slow down via the speed slider, or use the timestamp slider for random access (always works correctly).

Source: https://github.com/facebookresearch/projectaria_tools/tree/main/tools/visualization

### `vrs_to_mp4`

Converts camera streams from a VRS file into a standard MP4 video.

**Use when**: you need a shareable / previewable video file — for presentations, web embedding, or sharing with non-Aria users who don't have PAT.

**Do NOT use for CV / AI pipelines.** Output is lossy compressed video — feed those pipelines decoded frames from `VrsDataProvider` instead.

Source: https://github.com/facebookresearch/projectaria_tools/tree/main/projectaria_tools/tools/vrs_to_mp4

### `gen2_mp_csv_exporter`

Exports **on-device** machine-perception streams (VIO, eye gaze, hand tracking, online calibration) from a Gen 2 VRS into CSV / JSONL files in the **same format as cloud MPS outputs**.

**Use when**:

- You want to compare on-device perception against cloud MPS on the same recording.
- You want to reuse MPS-loading code on a recording you haven't sent through MPS.

Gen 2 only. Streams not present in the recording are skipped silently.

Source: https://github.com/facebookresearch/projectaria_tools/tree/main/projectaria_tools/tools/gen2_mp_csv_exporter

### `aria_dataset_downloader`

Downloads Aria open datasets in bulk from a CDN URL manifest file. You first obtain the manifest from the dataset's download page, then this tool fetches the full dataset — or a selected subset of sequences and data groups — into a local folder, with resumable downloads.

**Use when**: you're working with any Aria open dataset and want to pull it locally for offline processing, rather than streaming or sequence-by-sequence manual download.

Source: https://github.com/facebookresearch/projectaria_tools/tree/main/projectaria_tools/tools/dataset_downloader

### `dtc_object_downloader`

Downloads 3D object assets from the **Digital Twin Catalog (DTC)** — the object library used by Aria Digital Twin and related dataset projects.

**Use when**: you're working with DTC-based projects and need the underlying 3D object models locally.

Source: https://github.com/facebookresearch/projectaria_tools/tree/main/projectaria_tools/projects/dtc_objects

## Glossary

| Acronym | Meaning |
|---------|---------|
| PAT | ProjectAriaTools — this library |
| VRS | Vision Record Stream — file format for timestamped multi-stream sensor data |
| MPS | Machine Perception Services — cloud processing for SLAM, eye gaze, hand tracking |
| VIO | Visual-Inertial Odometry — real-time 6DoF pose from cameras + IMU |
| SLAM | Simultaneous Localization and Mapping — trajectory in MPS |
| CPF | Central Pupil Frame — reference coordinate frame for eye gaze |
| SE3 | Special Euclidean group in 3D — 6DoF rigid body transforms |
| SubGHz | Sub-GHz radio hardware used for time domain mapping across Gen2 devices |
