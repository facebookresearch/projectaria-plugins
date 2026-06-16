---
name: custom-profile
description: Use when authoring a custom profile JSON for Aria Gen 2. A profile fixes which sensors are enabled and at what rate, resolution, and encoding — **the same profile works for both recording and streaming**, despite the historical "recording profile" name. Custom profiles carry real risks (thermal shutdown, fragmented data, MPS rejection), so this skill encodes the conservative authoring workflow plus the full released profile schema (top-level keys, per-sensor fields, enums, validation rules, rate-handling behaviors). Use whenever the user asks how to write a custom profile, modify a profile, define sensor rates, deploy a profile to the device, or asks what a specific profile field means.
---

# Custom Profile Authoring

A **profile** is a JSON-shaped configuration that fixes which Aria Gen 2 sensors are enabled, at what rate, resolution, and encoding. **The same profile applies to both recording and streaming** — historically called "recording profile" (and the Companion App still labels them that way), which is misleading; profiles are not recording-only. The device ships with **pre-defined profiles** validated for thermal, battery, and data quality — use these by default. Custom profiles are for cases where no pre-defined profile fits.

---

## Mental model

A profile is a **high-level intent**, not a literal sensor list. The device expands it: enabling a vertical (`vio`, `et`, `ht`) auto-adds its raw-sensor dependencies (cameras, IMU); unset fields fall back to defaults; illegal values reject the profile.

Key consequences:

- **Presence is meaning.** Many fields are empty-object toggles (`"button_state": {}`); present = on.
- **Omit prerequisites.** `et` alone is fine; `et_cameras` + IR LED are auto-added. Express intent, not plumbing.
- **Spelling matters.** Misspelled or unknown fields are **rejected outright** on upload.
- **Selection is by `name`**, not by filename, not by index, not by `type`.

---

## When NOT to write a custom profile

Stop and use a pre-defined profile if any of these apply:

- The user is new to Aria.
- The data will be processed by MPS — custom profiles risk MPS incompatibility.
- The data needs to be sharable or comparable across studies.
- The user has not first tried a pre-defined profile.

---

## Pre-defined profiles (use as base)

| Profile | Best for | Notable | Bundled JSON |
|---|---|---|---|
| `profile8` | General-purpose recording | RGB 10 Hz @ 2560×1920, SLAM 30 Hz, all environmental sensors on | `references/profile8.json` |
| `profile9` | General-purpose streaming | RGB 5 Hz CBR (8 Mbps + blur filter), no GPS / BLE / WiFi / ET cameras | `references/profile9.json` |
| `profile10` | High-frame-rate RGB | RGB 30 Hz @ 2016×1512, otherwise like `profile8` | `references/profile10.json` |
| `mp_streaming_demo` | Machine-perception streaming demo | Streaming-only, lighter encoding for thermal, no ALS / baro / mag / GPS / BLE / WiFi | `references/mp_streaming_demo.json` |

**Each profile's full JSON is bundled in `references/` inside this skill** — read the one closest to your use case, copy it, rename, and edit. These four are validated for thermal, battery, and data quality, and the per-field settings encode tested combinations — they are the only safe starting points.

The pre-defined profile set may grow over releases — also check the docs:
https://facebookresearch.github.io/projectaria_tools/gen2/technical-specs/device/profile

---

## Risks (always communicate to the user)

A custom profile can cause:

- **Thermal shutdown** — device shuts down around 44 °C. High frame rates / resolutions / many active sensors push it harder.
- **Battery drain** — shorter recording sessions than pre-defined profiles.
- **Missing streams** — some sensor combinations have known bugs.
- **MPS rejection** — non-standard configurations may not be processable by cloud services.
- **PAT load failures** — unusual encoding settings can break downstream tooling.
- **Reduced support** — Meta does not guarantee compatibility for custom profiles.

If the user needs heavy customization, **first** check whether one of the pre-defined profiles is acceptable.

---

## JSON conventions

- **Field names use `snake_case`.**
- **Enums can be written as the integer OR the enum name string** — both `"encoding": 4` and `"encoding": "H265"` are valid.
- **`0` / `UNDEFINED` usually means "unset"** for enums — the value yields to defaults or to the other side of a merge. Don't write explicit `0` expecting it to *force* anything.
- **`OptionalBool` is a 3-state enum, NOT a JSON boolean**: `0`=UNDEFINED, `1`=TRUE, `2`=FALSE. Write `"ir_led": 1` for true, `2` for false.
- **A top-level file is a JSON array of profile objects**, or a single profile for the inline path.

### Units

- `rate_hz` — Hz (float)
- `period_ms` — milliseconds (int32)
- `*_us`, `exposure_time_us`, `exposure_us` — microseconds (int32)

### `SensorConfig`: choose `rate_hz` *or* `period_ms`

Several sensors share the `SensorConfig` message. **Specify exactly one** of:

- `rate_hz` (float) — used by: `imus`, `magnetometer`, `barometer`, `gps`, `ppg`, `temperature`, `ht`, `utc_time_sync`.
- `period_ms` (int32) — used by: `device_info`.

`ble` and `wifi` are NOT `SensorConfig`; they're dedicated messages that use `period_ms`. `als`, `vio`, `et` are dedicated messages that use `rate_hz` plus extra fields.

On merge: `rate_hz` keeps the **max** and `period_ms` keeps the **min** of the two sides.

### Empty messages are on/off toggles

These fields have no required content — **their mere presence enables the feature**:

- `button_state`

Write them as `"button_state": {}`.

---

## Profile schema

### Top-level metadata

| Field | Type | Meaning |
|---|---|---|
| `name` | string | **Required.** Selection key. Must be unique across **all 3 on-device profile sources** (native + cloud + user) on the target device. List existing profile names via the Client SDK — run `aria_gen2 device profile --help` for the exact subcommand. |
| `description` | string | Free text shown in tooling. |
| `type` | `ProfileType` enum: `1`=RECORDING, `2`=STREAMING | **Metadata only** — does NOT affect runtime. Recording-vs-streaming behavior is driven by which name is chosen as the recording-default vs streaming-default at session time, not by this field. By convention `*_recording` profiles set `1`, streaming set `2`. |
| `recommended` | bool | UI hint surfaced by the phone app / Wearables Dev Center. Does not change behavior. |
| `public` | bool | Controls **SDK visibility**: only `public=true` profiles appear in the SDK's profile list. Does not change what runs. |

### Raw inertial & environmental sensors

| Field | Sub-field | Valid values | Behavior on invalid |
|---|---|---|---|
| `imus` | `rate_hz` | One of `200, 400, 800, 1600, 3200, 6400` Hz. **800 standard**; VIO forces 800. | REJECT |
| `magnetometer` | `rate_hz` | One of `1.562, 3.125, 6.25, 12.5, 25, 50, 100, 200, 400` Hz. **100 standard.** | REJECT |
| `barometer` | `rate_hz` | One of `0.125, 0.25, 0.5, 1, 2, 3, 4, 5, 10, 15, 20, 25, 30, 35, 40, 45, 50, 60, 70, 80, 90, 100, 120, 130, 140, 150, 160, 180, 200, 220, 240` Hz (exact-match table). **50 standard.** | REJECT |
| `gps` | `rate_hz` | One of `1, 2, 4, 5, 8, 10` Hz. **1 standard.** | REJECT |
| `ppg` | `rate_hz` | Any value in ≈1 Hz … ≈1927 Hz. **128 standard.** | SNAP within range; REJECT outside |
| `temperature` | `rate_hz` | Any value ≥ 1 Hz. **Sensor is always on even if omitted.** 1 standard. | CLAMP to ≥1 Hz |
| `als` | `rate_hz` | Any value in ≈0.19 Hz … ≈131.6 Hz. Snaps to a **20.5 ms inter-measurement grid** (e.g. requesting 10 → ≈9.8 Hz). | SNAP within range; REJECT outside |
| `als` | `exposure_time_us` | Any value in `1600 … 1,600,000` µs. Rounded to nearest **1600 µs tick**. 3200 standard (=2 ticks). | SNAP within range; REJECT outside |
| `utc_time_sync` | `rate_hz` | UTC time-sync cadence. | NOT VALIDATED |
| `device_info` | `period_ms` | Battery + proximity polling period. 5000–30000 typical. | NOT VALIDATED |

### Audio

```jsonc
"audio": {
  "sample_rate": 1,           // AudioSampleRate: 1=16kHz, 2=48kHz
  "frame_period": 3,          // AudioFramePeriod: 1=5ms, 2=10ms, 3=20ms
  "sample_format": 1,         // AudioSampleFormat: 1=S16, 2=S32
  "encoding_format": 2,       // AudioEncodingFormat: 1=PCM, 2=OPUS
  "mic_selection": { "1": true, "3": true },        // optional; keys 1-8; empty/omitted = all 8 mics
  "opus_config": { "complexity": 10, "bitrate": 256000 }   // only when encoding=OPUS
}
```

- All four enum fields **hard-reject** invalid values.
- `mic_selection`: 1-indexed map; max 8 mics. Empty or omitted = all 8 enabled.
- `opus_config.complexity`: 0–10. `opus_config.bitrate` in bps; no min/max enforced.
- **Defaults if `audio` omitted entirely**: 48 kHz / 20 ms / S32 / PCM.

### Connectivity

```jsonc
"ble":  { "period_ms": 30000, "duration_ms": 2000 }
"wifi": { "period_ms": 30000, "scan_mode": 2 }      // WifiScanMode: 1=PASSIVE, 2=ACTIVE
```

No validation on the values; passthrough.

### Cameras

#### Shared timing rule

All cameras share a single **180 Hz master trigger**. A camera group's actual rate is always **`180 / N`** for an integer divider N. A requested `rate_hz` that is not exactly `180/N` is **SNAPPED** (rounded **up** to the next achievable rate) — it is **NOT rejected**. This snap-don't-reject behavior is camera-specific (IMU/Mag/GPS reject off-list rates instead).

- `rate_hz = 0` disables the group.
- `rate_hz > 90` (90 Hz hard ceiling) → REJECT.
- Achievable rates ≤ 90: `90, 60, 45, 36, 30, 22.5, 20, 18, 15, 12, 10, 9, 6, 5, ...`
- Snap example: requesting 25 Hz → divider = floor(180000/25000) = 7 → actual ≈ 25.7 Hz.

#### `encoding` — `CameraEncodingFormat`

| int | name | Notes |
|---|---|---|
| `1` | `RAW8` | Raw 8-bit. Required for CV inputs — VIO / HT / ET cameras forced to RAW8. |
| `2` | `RAW10` | Raw 10-bit. |
| `3` | `YUV` | **RGB camera ONLY.** YUV on a mono cam is a hard reject. |
| `4` | `H265` | Compressed. Requires a `video_config`. |

#### `video_config` (`oneof` — pick exactly one arm)

```jsonc
"video_config": {
  "iframe_period": 30,           // optional; <=0 → 1 on device
  "cqp":  { "qp": 24 }           // constant QP
  // or "cbr": { "bitrate": 10000000 }    // constant bitrate (bps)
}
```

| Arm | Field | Limit |
|---|---|---|
| `cqp` | `qp` | General HW range **0–51**. For **RGB (POV)**, qp must be **0 (=disable encoding) or ≥ 20**. SLAM/ET have no QP floor. |
| `cbr` | `bitrate` (bps) | No min/max enforced. Examples: 900 kbps (SLAM) … 30 Mbps (RGB). |
| top-level `iframe_period` | int | ≤0 → 1 on device. |

> Deprecated scalar `qp` at top-level is auto-migrated to `cqp` — don't use in new profiles.

#### Exposure (`oneof` — `auto_exposure` *or* `fixed_exposure`)

```jsonc
"auto_exposure": {}                                   // enable auto-exposure
// or
"fixed_exposure": { "exposure_us": 250, "gain": 6 }  // fixed
```

- **`auto_exposure` subfields are ignored** — only presence matters. Filling `exposure_us` / `gain` / `target_intensity` inside `auto_exposure` does nothing.
- **`fixed_exposure`**: `exposure_us` and `gain` are honored; non-positive falls back to 1000 µs / 1.0.

#### Camera gain ranges (validated; out-of-range rejected)

| Camera | Range |
|---|---|
| SLAM | 0.1–8.0 |
| ET | 1.0–16.0 |
| RGB (POV) | 1.0–255.94 |

#### SLAM-specific exposure rules

- **SLAM auto-exposure only at ≤ 45 Hz.** Enabling auto-exposure with SLAM rate > 45 Hz → rejected.
- **SLAM exposure cap is rate-dependent**: max = `frame_period_us − 8500 µs`, clamped to `[1000, 10000]` µs.

#### `slam_cameras`

```jsonc
"slam_cameras": {
  "rate_hz": 30,
  "auto_exposure": {},
  "encoding": 4,
  "video_config": { "cqp": { "qp": 24 } }
}
```

- Fixed **512×512** capture. **All four SLAM cameras are always configured together — you cannot disable individual SLAM cameras from a profile.**

#### `et_cameras`

```jsonc
"et_cameras": {
  "rate_hz": 5,
  "auto_exposure": {},            // or "fixed_exposure": { "exposure_us": ..., "gain": ... }
  "encoding": 4,
  "video_config": { "cqp": { "qp": 22 } },
  "resolution": 1,                // EtCameraResolution: 1=200×200, 2=400×400
  "ir_led": 1                     // OptionalBool: 1=on, 2=off
}
```

- `resolution` REJECT on invalid; default 200×200.
- `ir_led`: FALSE(2) → off; else on (UNDEFINED → on).
- **You cannot select individual ET cameras from a profile** — both ET cameras are always configured together.

#### `rgb_camera`

```jsonc
"rgb_camera": {
  "rate_hz": 10,
  "auto_exposure": {},
  "encoding": 4,
  "video_config": { "cqp": { "qp": 22 } },
  "resolution": 3,                // RgbCameraResolution: 1=1008×756, 2=2016×1512, 3=4032×3024
  "width": 2560, "height": 1920,  // downscaled OUTPUT size (device resizes capture → output before encode)
  "blur_filter_config": {
    "enabled": 1,                 // OptionalBool: UNDEFINED → false
    "threshold": 60,              // frames with blur score > threshold are dropped
                                  //   <0 → warn + default 60; 0 = drop nothing; 9999 = compute, never drop
    "window_ms": 400              // guarantees ≥1 frame per window; <=0 → default 100
  },
  "sharpening_level": 0,          // Edge sharpening, 0-10 (0=off). Passthrough, NOT validated.
  "denoising_level": 0,           // Spatial denoise, 0-10 (0=off). Passthrough, NOT validated.
  "awb": { "source": 1 },         // Auto White Balance. Present = enabled.
                                  //   source: 1 = use ALS color-temp (requires `als` enabled)
                                  //           2 = estimate from image pixels
  "lsc_enabled": 1,               // Lens Shading Correction (OptionalBool). Requires `awb` enabled.
  "cnr": { "strength": 5 },       // Color Noise Reduction. Present = enabled. strength 0-10 (validated).
  "cac_enabled": 1                // Chromatic Aberration Correction (OptionalBool).
}
```

| Field | Notes |
|---|---|
| `resolution` | REJECT on invalid; default 2016×1512. |
| `rate_hz` at full res | **4032×3024 supports max 24 fps.** > 24 fps at full res → rejected. |
| `width` / `height` | No allow-list; passthrough. 2560×1920 and 320×240 known-working. |
| `blur_filter_config` | **Enabling blur transitively requires the VIO stack.** Device auto-adds `vio_high_frequency_pose` → `vio` → `slam_cameras` + `imus`. Validator rejects blur without VIO. |
| `awb.source=ALS` | Requires `als` enabled in the same profile. |
| `lsc_enabled` | Requires `awb` enabled. |
| `cnr.strength` | Must be 0–10 (validated). |

### Machine-Perception verticals (you enable; device adds dependencies)

| Field | Form | What it does | Auto-adds |
|---|---|---|---|
| `vio` | `{rate_hz, extract_image_keypoints, output_tracks}` | Visual-inertial odometry | `slam_cameras`@rate (RAW8) + `imus`@800 |
| `vio_high_frequency_pose` | `{rate_hz}` | High-rate pose output | `vio` (→ SLAM+IMU); sets imus@its rate |
| `et` | `{rate_hz}` | Eye gaze | `et_cameras`@rate (RAW8) + IR LED on |
| `ht` | `{rate_hz}` | Hand tracking | `slam_cameras`@rate (RAW8) |

#### Notes

- **`et_cameras.rate_hz` must be ≤ 5 Hz when `et` (gaze tracking) is enabled** — IP-protection cap. If you need ET camera frames at > 5 Hz, do not enable `et`: configure `et_cameras` alone and you get raw ET frames without gaze inference.
- **`vio.extract_image_keypoints`**: defaults to **off**. Set `1` explicitly if you want keypoints.
- **`vio.output_tracks`**: enables image-track output from VIO.

### Misc events

- `button_state: {}` — capture button-state events.

---

## Rate-handling behaviors (per sensor)

| Behavior | Sensors | Meaning |
|---|---|---|
| **REJECT** | `imus`, `magnetometer`, `gps`, `barometer` | Off-list value → the sensor does not start. |
| **SNAP** | cameras (all), `ppg`, `als` (rate + exposure) | Value silently adjusted to the nearest achievable; no error. |
| **CLAMP** | `temperature` | Value forced to ≥ 1 Hz. |

---

## Validation & failure modes

| When | What happens on bad input |
|---|---|
| Upload | Unknown / misspelled field → rejected. Duplicate `name` across sources → rejected. |
| Loading | Invalid enums (audio formats, resolutions, encoding, YUV on a non-RGB camera) → profile rejected; the session won't start. |
| Validation | Off-list rates (IMU / Mag / GPS); camera > 90 Hz; RGB full-res > 24 fps; POV qp not (0 or ≥ 20); gain out of range; SLAM auto-exposure > 45 Hz; SLAM exposure too long; CNR strength > 10; blur without VIO → profile rejected. |
| Soft fixes (warn, not reject) | temperature < 1 Hz → clamped to 1; invalid blur threshold/window → defaults; `fixed_exposure` ≤ 0 → defaults; `iframe_period` ≤ 0 → 1. |

**Bad enums fail hardest.** Prefer to start from a working built-in profile and change values one at a time.

---

## Authoring checklist

1. **Start from a pre-defined profile** (`profile8` / `profile9` / `profile10` / `mp_streaming_demo`). Copy and rename — don't start blank.
2. **Give it a unique `name`** across all sources.
3. **Express intent, not plumbing** — enable verticals (`vio`, `et`, `ht`); let the device add raw cameras / IMUs.
4. **Respect the hard limits**: rates (per-sensor tables above), resolutions, POV QP (0 or ≥ 20), camera gain, SLAM auto-exposure ≤ 45 Hz, RGB full-res ≤ 24 fps.
5. **Spell every field exactly** — the SDK upload path rejects unknowns.
6. **Test with a short recording first** — verify all expected streams are present, monitor device temperature + battery, validate the recording loads in PAT.
7. **If passing to MPS, run `vrs-health-check` first** (see the `vrs-health-check` skill).
8. **Selection is by `name`**, not by filename, not by index, not by `type`.

---

## Deploying a custom profile

Profiles live in one of three on-device sources: **native** (read-only, baked into the image), **cloud** (server-pushed), and **user** (your custom profiles).

### Path 1: Companion App (per-device, GUI)

1. Headset Details → **Recording Profiles** → **Manage recording profiles**.
2. Select a pre-defined profile → **Make a copy** → edit in the editor → **Save**.
   (Or: tap **+** for a blank editor → paste your JSON → **Save**.)
3. The new profile appears under **My profiles** and is selectable when starting a recording or a stream.

The UI is labelled "Recording Profiles" but the saved profile works for both recording and streaming.

Reference: https://facebookresearch.github.io/projectaria_tools/gen2/ark/companion-app/recording-profiles

### Path 2: Client SDK (programmatic)

Upload to the **`user`** profile source via the Client SDK before starting a recording or stream. See the **`client-sdk`** skill for how to drive recording/streaming, and run the relevant CLI's `--help` for current flag names.

---

## After deploying

- **Run `vrs-health-check` first** (see the `vrs-health-check` skill). If it fails, the profile likely has issues.
- **Load in PAT** (see the `projectaria-tools` skill) to verify the streams are accessible.
- **Compare actual data rates** to your configured rates — significant deviation suggests thermal throttling or sensor failure.

---

## Worked examples — the 4 pre-defined profiles

Don't author from scratch. The 4 pre-defined profiles bundled in this skill are the validated starting points:

| Base | Bundled JSON | When to copy this one |
|---|---|---|
| `profile8` | `references/profile8.json` | You want general-purpose **recording** with full sensor coverage. |
| `profile9` | `references/profile9.json` | You want general-purpose **streaming** with thermally-safe RGB CBR encoding. |
| `profile10` | `references/profile10.json` | You want recording with **30 fps RGB at 2 MP**. |
| `mp_streaming_demo` | `references/mp_streaming_demo.json` | You want a lightweight **streaming-only** machine-perception demo profile. |

Workflow:

1. Read the bundled JSON file matching your closest use case.
2. Copy it to a new file and rename — give it a unique `name` field.
3. Change one parameter at a time. Don't strip fields you don't understand; if a sensor isn't relevant, leave the block alone or omit the whole top-level key.
4. Deploy via Companion App or Client SDK (see below).

---

## Related plugin skills

- `aria-knowledge` — what a profile is at the concept level + list of pre-defined ones.
- `client-sdk` — deploy a profile via CLI / Python SDK; recording / streaming workflow.
- `vrs-health-check` — validate a recording before downstream use.
- `projectaria-tools` — inspect what's actually in the resulting VRS file.
