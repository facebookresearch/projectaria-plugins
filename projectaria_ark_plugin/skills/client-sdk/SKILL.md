---
name: client-sdk
description: Use when working with the Aria Client SDK — device pairing, recording, streaming, CLI commands (aria_gen2), Python SDK (aria.sdk_gen2), streaming visualization, multi-device time domain mapping, and device management. Use whenever the user mentions aria_gen2 CLI, aria.sdk_gen2, device pairing, recording start/stop, streaming from Aria glasses, or asks about controlling Aria Gen2 devices programmatically.
---

# Aria Client SDK

The Client SDK lets you control Aria Gen2 glasses from a host PC — pair devices, manage recordings, stream live sensor data, and configure multi-device setups. It ships as a pip package with both a CLI (`aria_gen2`) and a Python SDK (`aria.sdk_gen2`).

## How to Use This Skill

This skill teaches the concepts and capabilities. For exact API details:

- **CLI**: `aria_gen2 <subcommand> --help`
- **Python SDK**: Read `sdk_gen2.pyi` in the installed package (`site-packages/aria/`), or run `help(aria.sdk_gen2)`
- **Sample scripts**: `python -m aria.extract_sdk_samples --output ~/Downloads/`

## Installation

- **Install**: `pip install projectaria-client-sdk` (in a virtual environment, Python 3.10–3.12)
- **Verify**: `aria_doctor` — configures system ports and verifies connectivity
- **Supported**: Linux x64 (Ubuntu/Fedora), macOS Apple Silicon
- **Docs**: https://facebookresearch.github.io/projectaria_tools/gen2/ark/client-sdk/start

## Prerequisites

- Aria Gen2 device with Companion App paired
- USB cable connecting device to PC
- One-time authentication: `aria_gen2 auth pair` (requires approval in Companion App)

## Capabilities Overview

The SDK exposes five capability areas through both CLI and Python SDK:

### Authentication

One-time device-PC pairing. The PC generates a client hash, the user approves in the Companion App, and subsequent connections are automatic. Use `aria_doctor` to verify system readiness before pairing.

### Recording

Start/stop recordings on the device, list recordings, download as VRS files, delete. Recordings use configurable **profiles** that define which sensors are active and at what rate — predefined profiles (e.g. general-purpose, high-res RGB, streaming-optimized) are available on-device, plus custom profiles via JSON. Downloaded VRS files are processed with ProjectAriaTools (PAT).

### Streaming

Stream live sensor data from the device to the host PC in real-time. Three **streaming interfaces** with different tradeoffs:

- **USB** — most reliable, no thermal concern, best for development
- **WiFi Station** — untethered, device and PC on same network, needs message batching for thermal management
- **Device Hotspot** — direct connection for field use without external network, limited to ~20 min sessions due to thermal

Available sensor streams include: RGB camera, SLAM cameras, eye tracking cameras, IMU, magnetometer, barometer, GPS, audio, eye gaze, hand tracking, VIO (visual-inertial odometry), and more.

In the **Python SDK**, streaming uses a callback pattern: create a `StreamDataInterface`, register per-sensor callbacks (e.g. `register_rgb_callback`, `register_imu_callback`, `register_eye_gaze_callback`), then start streaming. Each callback fires when data arrives for that sensor. `StreamDataInterface` also supports `record_to_vrs()` to capture streamed data into a local VRS file on the host — this is the only way to save data during streaming, since on-device recording and streaming cannot run simultaneously.

### Device Management

Query device status (battery, temperature, WiFi, recording state), connect to WiFi networks, start the on-device hotspot, send text-to-speech, list available recording/streaming profiles, and retrieve device calibration.

### Multi-Device Time Domain Mapping

Temporal alignment across multiple Aria Gen2 devices using sub-GHz radio hardware. One device is configured as **broadcaster**, others as **receivers**. The broadcaster transmits its timestamps; receivers record timestamp pairs enabling clock conversion. Configure via `TimeDomainMappingConfig` (Python) or `--all` (CLI) on recording or streaming configs. Post-processing uses PAT's `TimeDomain.SUBGHZ` to query receiver data in the broadcaster's time domain.

## CLI vs Python SDK

Pick by intent:

- **CLI** (`aria_gen2`): One-shot operations, inspection, or chaining a few sequential actions.
- **Python SDK** (`import aria.sdk_gen2 as sdk_gen2`): Streaming with per-sensor callbacks, conditional logic during streaming, host-side VRS capture, or integration into a Python pipeline.
- **Default**: CLI for one-shot, Python SDK for callback-driven workflows.

### Python SDK Architecture

The SDK follows a client → device → operation model:

- `DeviceClient` — discovers and connects to devices. Supports multi-device via `usb_network_devices()` and connecting to specific `DeviceTarget`s.
- `Device` — represents a connected device. All operations (recording, streaming, device management) go through this object.
- `StreamDataInterface` — handles streaming data reception. Register per-sensor callbacks, set queue sizes, and optionally record to local VRS.
- Config objects: `RecordingConfig`, `HttpStreamingConfig`, `TimeDomainMappingConfig` — set on the device before starting operations.

### Streaming Visualization

Default to `aria_streaming_viewer` — more polished and actively maintained. `aria_rerun_viewer` is for playback of downloaded VRS files, not live streaming.

**`aria_streaming_viewer` is a persistent GUI window** — it displays live sensor data for as long as the streaming session lasts. It does NOT exit after launch. When launching it:

- Start streaming first (`aria_gen2 streaming start`), then launch the viewer.
- Run it as a background process (`run_in_background` or `&`) — it blocks the terminal indefinitely.
- Do NOT wait for it to exit, kill it, or treat it as a one-shot command.
- It stays alive until the user closes the window or streaming stops.

### Streaming Certificates (TLS)

Streaming between device and host uses TLS with self-signed certificates. Two cert types exist:

- **Persistent** — stored in `~/.aria/streaming-certs/persistent/`, survive across sessions, installed via `aria_gen2 streaming install-certificates` or auto-generated on first `aria_gen2 streaming start`
- **Ephemeral** — stored in `~/.aria/streaming-certs/ephemeral/`, regenerated each session

The CLI `aria_gen2 streaming start` auto-installs a persistent cert if none exists — no manual cert setup needed for the typical workflow.

**Viewer only loads persistent certs.** Both `aria_streaming_viewer` and the multi-device streaming viewer hardcode to `~/.aria/streaming-certs/persistent/`. If streaming was started with ephemeral certs (e.g. via Python SDK with `StreamingSecurityOptions.use_ephemeral_certs = True`), the viewer's TLS handshake will silently fail — the viewer appears to start but shows no data. There is no error message indicating a cert mismatch.

**Rule**: When using the viewer, always ensure streaming uses persistent certs (the default). If you must use ephemeral certs for a custom Python SDK workflow, do not use `aria_streaming_viewer` — handle stream data via SDK callbacks instead.

## Key Constraints

- **Auth before anything**: All connections fail without prior `aria_gen2 auth pair`.
- **Recording and streaming are exclusive**: Cannot run both on-device simultaneously. Use `record_to_vrs()` for host-side capture during streaming.
- **USB required for control**: USB connection is needed to start/stop streaming, even when streaming wirelessly.
- **Streaming before viewer**: The viewer connects to an active stream — start streaming first.
- **Viewer requires persistent certs**: The viewer only loads certs from `~/.aria/streaming-certs/persistent/`. Streaming with ephemeral certs will silently fail to display in the viewer.
- **Guest WiFi won't work**: Guest networks block peer-to-peer communication required for streaming.
- **Errors → Troubleshooting section FIRST**: When any SDK command fails or returns unexpected output, you MUST check the Troubleshooting section below and the official troubleshooting page before attempting your own diagnosis. Do not guess root causes from training data — Aria errors have Aria-specific causes that generic debugging will miss.

## Gen1 vs Gen2

The pip package includes both. Gen1 uses `aria` CLI and `import aria.sdk`. Gen2 uses `aria_gen2` CLI and `import aria.sdk_gen2`. Type stubs: `sdk.pyi` (Gen1), `sdk_gen2.pyi` (Gen2). Gen1 and Gen2 SDK are **NOT interchangeable**.

## ⛔ MANDATORY: Troubleshooting

**When any Client SDK command fails or returns unexpected output, you MUST consult this section and the official troubleshooting page BEFORE attempting your own diagnosis.** This is not optional. Aria failures have Aria-specific root causes (sandbox blocks, cert mismatches, thermal shutdowns, mDNS issues) that generic debugging will misdiagnose.

Anti-patterns:
- ❌ "I think I know what's wrong" — check the table first; your guess wastes the user's time when the documented fix is one row away.
- ❌ "Let me try a different approach" — the documented fix exists for a reason. Try it before improvising.
- ❌ "This looks like a generic Python/network error" — it almost certainly has an Aria-specific cause.

**Resources**:
- **First step always**: `aria_doctor` — configures ports and diagnoses connectivity.
- **Official troubleshooting page**: https://facebookresearch.github.io/projectaria_tools/gen2/ark/support/sdk — covers symptoms not listed below.

### Common Issues

| Symptom | Action |
|---------|--------|
| Device not detected | Run `aria_doctor`. Try different USB 3.0+ port/cable. Disable VPN. |
| `auth pair` hangs | Open Companion App, navigate to pairing screen. Check phone internet. |
| Streaming disconnects | USB: use quality cable, avoid hubs. WiFi: check signal/firewall. |
| Device overheating | Shuts down at ~44°C. Cool 5-10 min. Limit hotspot streaming to ~20 min. |
| Viewer starts but no data | Cert mismatch: streaming used ephemeral certs but the viewer only loads persistent certs. Restart streaming without `use_ephemeral_certs`, or run `aria_gen2 streaming install-certificates` then restart streaming. |
| `GLIBCXX_3.4.31 not found` (Ubuntu 22) | `sudo apt install g++-13` |
