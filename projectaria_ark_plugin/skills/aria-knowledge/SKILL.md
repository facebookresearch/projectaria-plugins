---
name: aria-knowledge
description: Encoded knowledge for Project Aria Gen 2 and the Aria Research Kit (ARK) — hardware, profiles, calibration, coordinate systems, VRS format, time domains, on-device perception, MPS outputs (SLAM, point cloud, hand tracking), plus pointers to the source-of-truth docs for specifics. Use whenever the user asks ANY conceptual question about Aria Gen 2 / ARK and you need to either answer from encoded knowledge or know where to look next. This skill is the single index that tells an agent how to fetch official Aria knowledge: encoded stable concepts for what does not drift, explicit public-doc pointers for hardware specs / schemas / numerical values that do, and "go read the code" or "run --help" for things owned by source. Pair with the domain skills in this plugin (`projectaria-tools`, `client-sdk`, `mps`, `vrs-health-check`, `pilot-dataset`, `web-app-creator`, `custom-profile`, `vrs-cli`, `client-sdk-ros2-integration`, `cloud-streaming`) for hands-on work.
---

# Aria Knowledge

This skill is the **knowledge index** for Project Aria Gen 2 and the Aria Research Kit (ARK). It encodes the high-level concepts that are stable across releases, and for specifics that drift (sensor specs, CSV column lists, exact API signatures, CLI flags) it tells you where the source-of-truth lives so you can fetch a current answer rather than guess.

## How to use this skill

```text
Question type                         → Action
─────────────────────────────────────────────────────────────────────────
What is X? / How does Y work?         → Answer from this skill
Specific numeric value / schema       → Read the public doc page this skill
                                        names (under `DOCS_BASE` below)
Exact API call / API signature        → Read the code (see corresponding
                                        skill for header locations)
Exact CLI flag                        → Run `<cmd> --help`
Hands-on workflow                     → Defer to the matching plugin skill
                                        (listed at the end of each section)
```

**Source-of-truth rule.** Anything that may change with a release — sample rates, profile JSON, stream IDs, calibration model parameters, MPS service versions, API names, CSV columns — lives in the docs or the source code. This skill repeats only the conceptual definitions that are unlikely to evolve.

## Where to look (source-of-truth map)

| Source | URL |
|---|---|
| **`DOCS_BASE`** — Aria Gen 2 public docs | `https://facebookresearch.github.io/projectaria_tools/gen2` |
| Open-source PAT library | `https://github.com/facebookresearch/projectaria_tools` |
| VRS file-format library | `https://github.com/facebookresearch/vrs` |
| Project Aria home | `https://www.projectaria.com/` |

Throughout this skill, paths like `/technical-specs/device/als` are **relative to `DOCS_BASE`** — prepend the base to construct a fetchable URL. The four top-level sections of the public docs site:

| Section | Covers |
|---|---|
| `/` (root) | Welcome / Gen 2 platform overview |
| `/ark/...` | Aria Research Kit user docs (devices, recording, streaming, MPS, companion app, support) |
| `/research-tools/...` | Open Science Initiative, `projectaria-tools` (PAT), open datasets, pre-trained models |
| `/technical-specs/...` | Hardware specs, profiles, calibration, VRS format, MPS data formats, coordinate systems, client SDK reference |

## Related plugin skills (defer to these for hands-on work)

| Skill | Use when |
|---|---|
| `projectaria-tools` | Reading VRS / loading MPS / calibration / SE3 — PAT Python/C++ API |
| `client-sdk` | Device pairing, recording, local streaming, multi-device basics, troubleshooting |
| `mps` | Submitting jobs to Machine Perception Services, CLI workflow, output structure |
| `vrs-health-check` | Validating recording quality before MPS or analysis |
| `pilot-dataset` | Working with the Aria Gen 2 Pilot Dataset |
| `web-app-creator` | Building webapps that stream live sensor data over WebSocket (macOS) |
| `custom-profile` | Authoring a custom profile JSON (recording or streaming) |
| `vrs-cli` | Installing and using the native VRS CLI tools |
| `client-sdk-ros2-integration` | ROS2 integration |
| `cloud-streaming` | Streaming Aria data to internet-accessible HTTPS endpoints |

---

## Platform overview

**Project Aria** is Meta Reality Labs Research's egocentric research platform. The current generation is **Aria Gen 2** — a wearable with multi-camera + multi-sensor capture and on-device ML acceleration. The platform splits into:

- **Aria Research Kit (ARK)** — device + companion app + Client SDK + cloud processing (MPS) for partner researchers.
- **Open Science Initiative (OSI)** — open datasets, models, tools for researchers without hardware.

Welcome page: `/`. ARK landing: `/ark`. OSI landing: `/research-tools`.

---

## Hardware

### Sensor inventory (high-level)

Aria Gen 2 carries:

- 4 monochrome **computer-vision (CV) cameras** with HDR + global shutter
- 1 **RGB camera** (12 MP, rolling shutter)
- 2 IR **eye-tracking cameras**
- 7 spatial **microphones** + 1 contact mic in the nosepad
- Dual 6-axis **IMUs**
- **Barometer**, **magnetometer**, **GNSS**
- **ALS** (ambient light, multispectral with UV)
- **PPG** (heart rate)
- **Proximity** sensor
- Force-cancelling **speakers**
- Custom low-power **coprocessor** for on-device perception
- **Sub-GHz radio** for sub-millisecond multi-device time alignment

For full hardware specs (FOV, resolution, sample rates, focal lengths): `/technical-specs/device/hardware`.

### ALS (Ambient Light Sensor) — VD6281 multispectral pipeline

Aria Gen 2 carries the **STMicroelectronics VD6281** 6-channel multispectral ambient-light sensor (R, G, B, UV, IR, broadband Clear).

The on-device firmware turns raw ADC counts into normalized channel signals, then applies factory-calibrated transforms to produce flux (W/m² for UV / IR / Clear) and CIE-XYZ-derived lux and CCT. **Both the normalized channels and the cooked outputs (lux / CCT / flux) are written to VRS** — researchers do not need to re-apply the calibration to get lux / CCT / flux.

Key behavior:

- **Auto-exposure adjusts exposure time, not gain.** `gain*` fields are effectively constant per recording; `exposureTimeUs` varies per sample.
- **No saturation flag is stored** — derive one from the recorded exposure + gain if needed.
- **No live ALS streaming** for external users — contact `AriaOps@meta.com` if needed.

For channel peak wavelengths, sample rate, the full processing equations (normalize / flux / lux / CCT), factory calibration JSON layout, gain LUT, saturation rate, and PAT loading code: `/technical-specs/device/als`.

### IMU noise model

Aria's stochastic IMU error is modeled as three additive components:

- **Turn-on bias** — Gaussian, sampled at power-on.
- **Bias random walk** — slow drift.
- **White noise** — per-sample Gaussian. The continuous strength is sometimes called Angle Random Walk (gyro) or Velocity Random Walk (accel).

**Provenance**: Gen 2 inherits its IMU noise parameters from Gen 1 Allan Variance analysis (same IMU chips). Bias random walk is a tuned parameter, not directly measured — the original Allan Variance dataset was not long enough to fit it.

For per-sensor numerical values, units, and bandwidths: `/technical-specs/device/imu_noise_model`.

### Profiles

A **profile** is a JSON-shaped configuration that fixes which Aria Gen 2 sensors are enabled, at what rate, what resolution, and what encoding (H.265 CQP vs CBR). **The same profile applies to both recording and streaming** — historically called "recording profile", which is misleading; profiles are not recording-only.

**Pre-defined profiles** (tested for thermal, battery, data quality — recommended starting points):

- `profile8`, `profile9`, `profile10`
- `mp_streaming_demo` — streaming-focused for machine-perception demos

**Custom profiles carry real risk** — overheating, fragmented datasets, broken downstream tooling, MPS rejection. Only advanced users should author one, and always derive from a tested profile rather than starting blank.

For full parameter tables, sensor combinations per profile, encoding choices, custom profile risks: `/technical-specs/device/profile`.

To **author** a custom profile end-to-end: use the **`custom-profile`** skill in this plugin.

### CAD models & size variants

Aria Gen 2 ships in **8 mechanical size configurations** — narrow vs wide frame × short vs long temples × high vs low nosepad. A tripod-mount reference design is also published.

For CAD files and dimensions: `/technical-specs/device/cad`.

---

## Calibration

### Camera projection models

Aria cameras use polar-coordinate projection with several lens-specific variants:

| Model | Used by | Notes |
|---|---|---|
| Linear / pinhole | Rectified outputs | Standard textbook |
| Spherical | (for fisheye visualization) | Pixel linear in solid angle; fisheye looks curved |
| **KannalaBrandtK3 (KB3)** | Eye-tracking cameras | Radial distortion via 9th-order polynomial |
| **FisheyeRadTanThinPrism** | RGB + SLAM cameras | Full radial + tangential + thin-prism |

`project` (3D → 2D) is closed-form; `unproject` (2D → 3D ray) requires **Newton iteration**.

For math, parameter lists per model, projection / unprojection algorithms: `/technical-specs/device/calibration_insights/camera_intrinsics_models`.

### Sensor measurement rectification

IMU, magnetometer, barometer, and audio raw outputs are converted to physical units via **affine transforms** with bias offsets. Gyro has additional **G-sensitivity** (cross-axis response to linear acceleration).

For the rectification matrices and equations: `/technical-specs/device/calibration_insights/sensor_measurement_model`.

### Factory calibration

Each Aria Gen 2 is **individually calibrated at the factory**. The calibration is stored as a **JSON string embedded in every sensor stream's configuration record** (`factory_calibration` field). All streams in a recording carry **identical copies** — read it from any stream with PAT.

Calibration covers per-sensor intrinsics, extrinsics as `T_Device_Sensor`, and sensor-specific blocks (e.g. ALS RGB matrix + flux coefficients).

For schema, what is calibrated vs not, and how to read with PAT: `/technical-specs/device/calibration`.

### Online vs factory calibration

MPS SLAM produces **online calibration** — a time-varying re-estimation of selected sensors' calibration parameters to compensate for drift from temperature, mechanical deformation, or wear over the course of a recording.

**Use online calibration when**: drift-sensitive workflows over long recordings, or when factory calibration has visibly drifted.

For exactly which sensors are re-optimized vs copied from factory, and the JSONL schema: `/technical-specs/mps/data_formats/slam/mps_calibration`.

For PAT loaders and read code, use the **`projectaria-tools`** skill.

---

## Coordinate Systems

### 3D conventions

- **Right-handed XYZ** frame.
- 6-DoF poses as **SE(3)** via Sophus (`https://github.com/strasdat/Sophus`).
- **Naming `T_dest_source`** (PAT API also calls this `transform_dest_source`): "transforms a point from `source` frame to `dest` frame":
  - `p_dest = T_dest_source @ p_source`
  - chaining: `T_a_c = T_a_b @ T_b_c`
- **Device frame** defaults to the local frame of the `slam-front-left` camera. Every other sensor's pose is expressed relative to this default.

**Quaternion convention differs by language** — verify, do not assume:

| Language / API | Order |
|---|---|
| Python `to_quat()` | `(w, x, y, z)` |
| C++ Sophus `unit_quaternion()` | `(x, y, z, w)` |

For the canonical convention reference: `/technical-specs/coordinate/3d-coor`.

### 2D image conventions

- Pixel at coordinate `(u, v)` spans `(u - 0.5, v - 0.5)` to `(u + 0.5, v + 0.5)` — i.e. integer coordinates are pixel **centers**.
- In-bound check: `0 ≤ u < width` AND `0 ≤ v < height`.
- Bilinear interpolation bounds and downsampling formulas live in the doc.

For the formulas: `/technical-specs/coordinate/2d-coor`.

### CPF (Central Pupil Frame) — avoid using

CPF is the midpoint of the left and right nominal pupil frames. **It exists only in the CAD model** — it is not directly observable from device calibration. This makes both forms of `T_CPF_sensor` problematic:

- `T_CPF_sensor(getCadValue=true)` — well-defined, but lives in CAD space. Applying it to real (calibration-space) data carries CAD error that is **generally much larger** than calibration error.
- `T_CPF_sensor(getCadValue=false)` — mixes CAD and calibration spaces. **Mathematically ill-defined.** PAT's implementation anchors the alignment via the device frame, so the value of `T_CPF_sensor` depends on which device frame is chosen, and would change if you switched the device frame convention.

**Recommendation: don't use CPF.** Use a sensor-frame relative pose instead:

```text
T_sensor1_sensor2 = T_Device_sensor1.inverse() * T_Device_sensor2
```

This stays in one well-defined space (CAD or calibration) and is invariant under device-frame switches.

For the full rationale with diagrams: `/technical-specs/coordinate/cpf-coor`.

---

## VRS Format

VRS is Meta's open container for timestamped multi-modal sensor recordings (`https://github.com/facebookresearch/vrs`). An Aria recording is one VRS file.

### Stream structure

- **StreamId** = `RecordableTypeId-InstanceId` (e.g. `1201-1` for SLAM camera 1).
- Each stream is one sensor or one on-device perception output.
- Each stream stores three record kinds:
  - **Configuration** — static metadata: sensor model, resolution, `factory_calibration` JSON.
  - **Data** — one frame, one IMU sample, one 4096-sample audio chunk, etc., with timestamps + acquisition parameters (exposure, gain).
  - **State** — rarely used.
- PAT maps StreamIds to human-readable labels (e.g. `1201-1` → `camera-slam-left`).

For the VRS data format details: `/technical-specs/vrs/data-format`.

### StreamId → label mapping

Each Aria sensor / on-device perception output is identified by a static StreamId (e.g. `1201-1`) that PAT maps to a human-readable label (e.g. `camera-slam-left`).

**Dynamic StreamIds** for some on-device perception streams (`handtracking`, `vio`, `vio_high_frequency`) are assigned at recording time based on what was enabled — **always resolve dynamically via PAT, never hardcode**.

For the canonical StreamId ↔ label table: `/technical-specs/vrs/streamid-label-mapper`.

### Native VRS CLI tools

Use `vrs check`, `vrs print`, etc. for inspection without PAT. Requires an H.265 / HEVC decoder for image streams.

For install + use: see the **`vrs-cli`** skill in this plugin.

---

## Time Domains

Aria Gen 2's key cross-device timing primitive is **SubGHz multi-device time-domain mapping** — a hardware-radio-based mechanism that aligns timestamps across multiple Aria glasses without NTP, network, or handshake.

To **trigger** SubGHz mapping:

- **Via the Client SDK** — see the `client-sdk` skill.
- **Via the Companion App** — https://facebookresearch.github.io/projectaria_tools/gen2/ark/companion-app/time-domain-mapping

To **read and apply** the mapping in post-processing — see the `projectaria-tools` skill.

### How SubGHz alignment works

One device acts as **broadcaster**, the others as **receivers**:

- **Broadcaster** transmits its device clock over the sub-GHz radio. Its VRS does **NOT** contain a SubGHz stream — its device time **IS** the reference.
- **Receivers** record `(broadcaster_time, local_time)` pairs into a SubGHz stream inside their VRS.
- PAT maps a receiver's local clock onto the broadcaster's with **sub-millisecond accuracy**.

For multi-sequence alignment in the pilot dataset: `/research-tools/dataset/pilot/tutorials/multi_sequences_timestamp_alignment`.

---

## On-Device Machine Perception

Three ML pipelines run on the custom coprocessor; output is recorded to VRS or streamed to a host. All three are configured by the profile.

| Pipeline | Rate | What it produces |
|---|---|---|
| **VIO** (Visual-Inertial Odometry) | ~10 Hz regular, ~800 Hz high-frequency | 6-DoF pose from 4 CV cameras + 2 IMUs; HF VIO uses IMU pre-integration on top of regular VIO. Use HF VIO for low-latency pose. |
| **Eye Tracking** | up to ~90 Hz | Per-eye gaze ray (origin + direction), pupil center, pupil diameter, blink. Combined gaze adds vergence depth + IPD. |
| **Hand Tracking** | ~30 Hz | Per-hand 21-joint 3-DoF positions + 6-DoF wrist (`T_device_wrist`) + palm and wrist normals, in device frame. |

For overview: `/ark/device/on_device_mp`.
For PAT API usage: see the `projectaria-tools` skill.

---

## MPS (Machine Perception Services) — Cloud Processing

MPS is the cloud post-processing service for Aria recordings. You submit a VRS via the `aria_mps` CLI and receive derived outputs that on-device perception alone cannot produce.

For the current set of services, CLI workflow, output folder structure, and troubleshooting: see the **`mps`** skill in this plugin.

### Output data formats

Output schemas (CSV columns, JSON fields, file layouts) are large and evolve with releases. **Do not memorize them.** Two sources of truth:

- For **exact column names and types**: read them from code via the **`projectaria-tools`** skill — its data loaders are canonical.
- For **explanations of what each format means and how to interpret the values**: `/technical-specs/mps`.

### Performance benchmarks

Metrics, datasets, and numbers are published per service version and change across releases. Always fetch the current page: `/technical-specs/mps/benchmarks/performance`.

### Data lifecycle and privacy

- **Raw VRS retained 30 days** on Meta servers, then deleted.
- **MPS outputs persist** indefinitely.
- **Partner data isolation** — Meta researchers do not have access.

For details: `/ark/mps/mps_data_lifecycle`.

### Service versioning

Service set and version numbers drift across releases — always check the docs rather than relying on memorized numbers: `/ark/mps/mps_versioning`.

---

## Client SDK adjacent knowledge

For install, auth, recording, local streaming, multi-device basics, troubleshooting, streaming-certificate gotchas: see the **`client-sdk`** skill.

### Camera ID bitmask (streaming callbacks ≠ VRS labels)

Streaming callbacks identify a camera via a **bitmask integer**, distinct from the StreamId-derived label used by VRS. Examples (verify the full mapping in the doc):

- `1` = `slam-front-left`
- `2`, `4`, `8` = other SLAM cameras
- `64` = `camera-rgb`

These appear in `ImageDataRecord.camera_id` in the streaming Python SDK. **Do NOT confuse with VRS StreamIds** — different namespace.

For the full mapping: `/technical-specs/client-sdk/camera-id-mapper`.

### Action button programming

The hardware button on the temple can be bound to short-press and long-press actions: start/stop recording OR start/stop streaming. The binding **lives on the device** and **persists across SDK and standalone use** — the SDK does not override it.

For programming: `/ark/companion-app/action-button`.

### Bluetooth audio pairing

Aria glasses can pair as a **Bluetooth audio device** with a phone — speaker + microphone passthrough for media playback and calls.

For pairing: `/ark/companion-app/bluetooth-audio`.

### Other Client SDK adjacent skills

- **Streaming to cloud HTTPS endpoints** — see the **`cloud-streaming`** skill.
- **ROS2 integration** — see the **`client-sdk-ros2-integration`** skill.
- **Multi-device streaming server** (headless HTTPS server receiving from N devices) — see the `client-sdk` skill's multi-device section.

---

## Pre-trained Open-Science models

### EgoBlur

Face + license-plate detection for blurring egocentric imagery before publication (privacy anonymization). Open-source.

GitHub: `https://github.com/facebookresearch/EgoBlur`

### Boxer

Lifts open-world 2D bounding boxes into static, global, fused **3D oriented bounding boxes** from posed images and semi-dense point clouds. Open-source.

GitHub: `https://github.com/facebookresearch/boxer`

---

## Glossary

| Acronym | Expansion |
|---|---|
| ARK | Aria Research Kit |
| OSI | Open Science Initiative |
| PAT | Project Aria Tools |
| MPS | Machine Perception Services |
| VIO | Visual-Inertial Odometry |
| SLAM | Simultaneous Localization And Mapping |
| CV | Computer Vision (cameras) |
| ET | Eye Tracking |
| HT | Hand Tracking |
| IMU | Inertial Measurement Unit |
| ALS | Ambient Light Sensor |
| PPG | Photoplethysmography (heart rate) |
| CPF | Central Pupil Frame |
| SE3 | Special Euclidean group in 3D (6-DoF rigid transform) |
| SubGHz | Sub-gigahertz radio for multi-device time alignment |
| GNSS | Global Navigation Satellite System |
| IPD | Inter-Pupillary Distance |
| FOV | Field of View |
| HDR | High Dynamic Range |
| HEVC | H.265 video codec |
| AEC | Auto-Exposure Controller |
| RTC | Real-Time Clock (Aria UTC source) |
| CCT | Correlated Color Temperature (Kelvin) |
| MKPE | Mean Keypoint Position Error (hand-tracking metric) |
| LTR | Long-Term Tracking Rate (hand-tracking metric) |
