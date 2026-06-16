# Aria ARK

AI coding assistant skills for Project Aria smart glasses development, powered by the Aria Research Kit (ARK).

> **ARK** = Aria Research Kit — the developer toolset for Project Aria glasses.

## Installation

### Claude Code

First, add the Project Aria marketplace:

```bash
claude plugin marketplace add https://github.com/facebookresearch/projectaria-plugins.git
```

Then install the plugin:

```bash
claude plugin install aria-ark@projectaria-plugins
```

### Codex

First, add the Project Aria marketplace:

```bash
codex plugin marketplace add https://github.com/facebookresearch/projectaria-plugins.git
```

Then open Codex chat, run `/plugin`, choose the Project Aria Plugins
marketplace, and install `aria-ark`.

## Skills

| Skill | Purpose |
|-------|---------|
| aria-knowledge | Knowledge index for Aria Gen 2 / ARK — encoded high-level concepts (hardware, calibration, coordinate systems, VRS format, time domains, on-device perception, MPS output structure, ALS multispectral pipeline, IMU noise model, hand-tracking schema, etc.) + pointers to the source-of-truth docs at https://facebookresearch.github.io/projectaria_tools/gen2/ for specifics that drift. Use whenever a question is about *what* something is or *where* to look. |
| client-sdk | Control Aria Gen2 glasses from a host PC — device pairing, recording, live streaming, and multi-device time domain mapping via the `aria_gen2` CLI and `aria.sdk_gen2` Python SDK. |
| client-sdk-ros2-integration | Integrate Aria Gen2 sensor streams with ROS2 — custom `AriaRaw` message, publisher / subscriber pattern, calibration sync, common pitfalls (`aria_data_types` package name, `ROS_DOMAIN_ID`, port 6768). |
| cloud-streaming | Configure Aria Gen2 glasses to stream sensor data directly to an internet-accessible HTTPS endpoint — for field deployments, centralized multi-device collection, and cloud processing pipelines. |
| custom-profile | Author a custom profile JSON for Aria Gen 2 — pick the right pre-defined base, change parameters conservatively, validate. A profile works for both recording and streaming. Encodes the risks (thermal, MPS rejection) of custom profiles. |
| mps | Submit Aria VRS recordings to Machine Perception Services (MPS) for cloud processing — SLAM trajectories, hand tracking, semi-dense point clouds, and online calibration via the `aria_mps` CLI. |
| pilot-dataset | Work with the Aria Gen2 Pilot Dataset — multi-participant egocentric recordings with raw VRS, MPS outputs, and additional algorithm results (ASR, heart rate, hand-object interaction, depth, 3D detection). |
| projectaria-tools | Read Aria VRS recordings and access sensor data, device calibration, MPS results (eye gaze, hand tracking, SLAM), and time domain mapping using the `projectaria_tools` Python/C++ library. |
| vrs-cli | Use the native VRS CLI tools (`vrs check`, `vrs print`, …) from facebookresearch/vrs for file-level inspection and validation of Aria VRS files. Distinct from `projectaria-tools` (Aria sensor semantics) and from `vrs-health-check` (Aria recording quality). |
| vrs-health-check | Validate Aria recording quality before MPS processing — detect dropped frames, sensor consistency issues, and calibration problems via the `run_vrs_health_check` CLI and Python API. |
| web-app-creator | Build real-time webapps that stream live Aria Gen2 sensor data via WebSocket (`ws://localhost:17300`) — VIO, hand tracking, eye gaze, IMU, PPG, audio, camera — plus a full bidirectional voice pipeline (VAD, Whisper STT, LLM chat, TTS). macOS only. |

## Requirements

- Python 3.10+ (for projectaria-tools)
- Node.js 18+ (for the `web-app-creator` skill)
- Project Aria glasses (for live streaming features)

## Links

- [Project Aria Documentation](https://facebookresearch.github.io/projectaria_tools/gen2/)
