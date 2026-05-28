# Aria ARK Plugin

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

> Support for Codex, Gemini CLI, and Cursor is planned but not yet available.

## Skills

| Skill | Invoke | Purpose |
|-------|--------|---------|
| client-sdk | `/aria-ark:client-sdk` | Control Aria Gen2 glasses from a host PC — device pairing, recording, live streaming, and multi-device time domain mapping via the `aria_gen2` CLI and `aria.sdk_gen2` Python SDK. |
| mps | `/aria-ark:mps` | Submit Aria VRS recordings to Machine Perception Services (MPS) for cloud processing — SLAM trajectories, hand tracking, semi-dense point clouds, and online calibration via the `aria_mps` CLI. |
| pilot-dataset | `/aria-ark:pilot-dataset` | Work with the Aria Gen2 Pilot Dataset — multi-participant egocentric recordings with raw VRS, MPS outputs, and additional algorithm results (ASR, heart rate, hand-object interaction, depth, 3D detection). |
| projectaria-tools | `/aria-ark:projectaria-tools` | Read Aria VRS recordings and access sensor data, device calibration, MPS results (eye gaze, hand tracking, SLAM), and time domain mapping using the `projectaria_tools` Python/C++ library. |
| vrs-health-check | `/aria-ark:vrs-health-check` | Validate Aria recording quality before MPS processing — detect dropped frames, sensor consistency issues, and calibration problems via the `run_vrs_health_check` CLI and Python API. |
| web-app-creator | `/aria-ark:web-app-creator` | Build real-time webapps that stream live Aria Gen2 sensor data via WebSocket (`ws://localhost:17300`) — VIO, hand tracking, eye gaze, IMU, PPG, audio, camera — plus a full bidirectional voice pipeline (VAD, Whisper STT, LLM chat, TTS). macOS only. |

## Requirements

- Python 3.10+ (for projectaria-tools)
- Node.js 18+ (for the `web-app-creator` skill)
- Project Aria glasses (for live streaming features)

## Links

- [Project Aria Documentation](https://facebookresearch.github.io/projectaria_tools/gen2/)
