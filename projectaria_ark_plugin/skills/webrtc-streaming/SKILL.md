---
name: webrtc-streaming
description: Use when the user wants to stream Aria Gen 2 glasses over WebRTC instead of the default HTTP transport — low-latency interactive use (teleoperation, live assistance), two-way audio (talking back to the wearer), streaming across different networks via a signaling server and STUN/TURN, or recording VRS on-device while streaming. Also relevant for deploying the WebRTC signaling server or interpreting WebRTC image timestamps. Does NOT cover HTTP streaming over USB / same-network WiFi (use the `client-sdk` skill) or POSTing to your own HTTPS ingest server (use the `cloud-streaming` skill).
---

# Aria WebRTC Streaming

WebRTC is an alternative streaming transport to HTTP for Aria Gen 2. The receiver API is unified: the `register_*_callback` surface and typed sensor objects are the same as HTTP, so only the receiver class and its config change.

> **Single source of truth** for setup, CLI flags, Python config fields, profiles, and signaling server deployment: **https://facebookresearch.github.io/projectaria_tools/gen2/ark/client-sdk/webrtc**
>
> This skill encodes only the stable concept. Fetch the docs (or run `aria_gen2 streaming webrtc start --help`) for anything specific. **Never guess flags or profile names.**

## Why WebRTC over HTTP

- **Two-way audio** — host microphone is sent to the glasses; HTTP is receive-only.
- **Low latency** — tuned for realtime delivery, not throughput.
- **Crosses networks** — peer-to-peer through a signaling server, TURN relay as fallback; no inbound port or streaming certificates needed.
- **Record while streaming** — full-rate VRS on the glasses alongside the live stream.

## Mental model

Two topologies:

- **Same network** — the receiver listens on a local port and the glasses dial it directly. Nothing to deploy.
- **Cross network** — both peers join a room on a **signaling server** you host. It only exchanges SDP / ICE and never carries media. Media goes direct peer-to-peer, or through a **TURN** relay when NAT / firewall blocks the direct path.

## Stable gotchas

- **Video timestamps are host receive time** (mapped into the device clock). RTP carries no capture timestamp, so images are slightly late by the network delay. Data-channel sensors (IMU, VIO, eye gaze, hands, …) keep true device-clock timestamps.
- **No batching, so bandwidth is capped by thermals.** A profile that works over HTTP may overheat over WebRTC. Start from the low-latency profile recommended in the docs.
- **Wi-Fi only**, but USB is still needed for the control connection.
- When recording while streaming, the streaming and recording profiles must use the **same camera resolution and format**. Frame rates may differ.

## Related plugin skills

- **`client-sdk`** — HTTP streaming, authentication, `aria_streaming_viewer`.
- **`cloud-streaming`** — glasses POST over HTTPS to your own ingest server.
- **`custom-profile`** — authoring a profile sized for WebRTC.
