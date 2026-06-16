---
name: cloud-streaming
description: Use when configuring Aria Gen 2 glasses to stream sensor data directly to an internet-accessible HTTPS endpoint — instead of the default local USB / same-network WiFi streaming to a nearby PC. For field deployments, centralized multi-device collection, and cloud processing pipelines. Use whenever the user asks about remote streaming, streaming over the internet, cloud collection servers, or streaming without a laptop on hand.
---

# Aria Cloud Streaming

Remote (cloud) streaming sends Aria Gen 2 data straight to your internet-reachable HTTPS server, bypassing the default local USB / same-network WiFi streaming. The glasses POST data over HTTPS to whatever URL you supply.

> Reference: https://facebookresearch.github.io/projectaria_tools/gen2/ark/client-sdk/remote-streaming
> For local USB / same-network streaming: use the **`client-sdk`** skill.

## When to use

- **Field deployments** — collect data without carrying a laptop.
- **Centralized collection** — many devices → one cloud server.
- **Cloud processing** — feed real-time pipelines (decoders, indexers, alerters) in the cloud.
- **Remote monitoring** — observe device streams from anywhere.

If your collection point is on the **same WiFi** as the glasses, plain local streaming via the Client SDK is simpler — use that.

## Architecture

```
Aria Glasses  ──(WiFi → internet)──►  Your HTTPS Server :6768
                  HTTPS POST              (decode / store / forward)
```

The glasses open an HTTPS connection to a URL you provide and POST sensor data chunks. The server uses Aria's streaming TLS certificates so the connection is mutually trusted.

## Setup (one-time per server)

### 1. Prerequisites

- Client SDK installed and device authenticated (`aria_gen2 auth pair`) — see the `client-sdk` skill.
- Glasses on a WiFi network with **internet access**.
- A server reachable from the public internet on **port 6768**.

### 2. Copy streaming certificates to the server

The certificates were generated when the SDK was first set up. They live on the PC where the SDK was installed at:

```
~/.aria/streaming-certs/persistent/
├── subscriber.pem        # server cert (PEM)
├── subscriber-key.pem    # server private key
└── root_ca.pem
```

Copy `subscriber.pem` and `subscriber-key.pem` to a secure path on the cloud server (e.g. `/etc/aria-certs/`, with `chmod 600`).

### 3. Open inbound port 6768

Open TCP port 6768 in the server's firewall and any cloud-provider security group. Restrict the source to known IP ranges if you can; otherwise allow `0.0.0.0/0`.

### 4. Run an HTTPS server on port 6768

Use any HTTP framework that supports custom TLS — the cert chain is loaded via:

```python
ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
ctx.load_cert_chain("/path/to/subscriber.pem", "/path/to/subscriber-key.pem")
server.socket = ctx.wrap_socket(server.socket, server_side=True)
```

A complete minimal Python server (HTTPServer + BaseHTTPRequestHandler) is shown in the reference page. The handler reads metadata from request headers, reads the binary body, and responds with `200 OK`.

### 5. Start streaming from the glasses pointing at your URL

Both the CLI and Python SDK accept a custom endpoint URL. Run `aria_gen2 streaming start --help` for current flag names, or see the reference page for the Python SDK equivalents (`HttpStreamingConfig.advanced_config.endpoint.url`, `verify_server_certificates`).

## What the server receives per POST

**Headers** carry session and device metadata:

| Header | Value |
|---|---|
| `session-id` | UUID for this streaming session |
| `device-serial` | Device serial number |
| `device-build` | Firmware version |
| `oatmeal-calibration` | JSON with camera + IMU + barometer calibration |
| `Transfer-Encoding` | `chunked` |

**Body** carries binary streaming data: IMU samples, camera frames, audio, eye / hand tracking, VIO poses, etc.

Respond with `200 OK` and any small JSON body (e.g. `{"status":"ok"}`).

## Thermal management

Remote streaming over WiFi generates heat. The single most important setting is **`--batch-period-ms`** (CLI) / `batch_period_ms` (Python config). It batches messages on-device before sending; longer periods = less radio activity = less heat.

| Environment | Suggested batch period |
|---|---|
| Cool (< 25 °C) | 100–200 ms |
| Normal room | 200–400 ms (start here) |
| Warm (> 28 °C) | 400–800 ms |

Without batching, the device will hit its thermal shutdown threshold (~44 °C) — typically within ~20 min of continuous streaming.

## VPN / firewall limitation

**Aria glasses cannot use VPNs.** If your collection server is behind a corporate VPN, the glasses cannot reach it directly.

**Workaround**: deploy a **public relay** — a small VM with a public IP that the glasses POST to — and forward via SSH / WireGuard tunnel into your internal server:

```
Aria Glasses ──► Public Relay (VM, public IP)  ─tunnel─►  Your Internal Server
                  HTTPS POST :6768               SSH /                (behind VPN)
                                                 WireGuard
```

## Certificate security

Treat the streaming certificates like secrets:

- Anyone with both cert files can stand up a server that accepts streams from your devices.
- Limit file permissions on the server (`chmod 600`).
- For production, layer your own application-level authentication on top (e.g. require a bearer token header in the handler).
- Rotate certs periodically for sensitive deployments.

## Troubleshooting

| Symptom | Likely cause | Fix |
|---|---|---|
| No data reaches server | Glasses not on internet WiFi, server unreachable, or wrong URL | Verify WiFi connection from the Companion App or `aria_gen2 device wifi …`; test the URL from another machine with `curl -k https://your-server:6768`; double-check the URL is HTTPS and includes the port |
| SSL / TLS handshake error | Wrong cert paths, file permissions, or missing `--no-verify-server-certs` on the client | Verify cert paths on server, `chmod 600`, add the flag (or set the equivalent Python config field) |
| Connection timeouts | High-latency network, profile too heavy for the link | Use a lighter profile (`profile9`), increase batch period |
| Device overheating | Batch period too short, profile too heavy | Increase `--batch-period-ms`, drop to a lighter profile, allow cooling breaks |
| Firewall blocks 6768 | Port not open inbound on server / security group | Open inbound TCP 6768 |

## Related plugin skills

- `client-sdk` — local streaming, authentication, recording, multi-device basics.
- `aria-knowledge` — Aria platform concepts including streaming certificate model.
