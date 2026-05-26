# Aria Gen2 WebSocket Sensor Schemas

All messages follow: `{ type: string, timestamp: number, data: object }`

> ⚠️ **FOR AI AGENTS:** All sensor values in this document are **live data from the physical device**.
> When building UIs, **NEVER** use example values from this file as hardcoded defaults or fallback data.
> If a sensor message hasn't been received yet, display `"Waiting for device…"`, `"--"`, or `null` — **not** made-up numbers.
> Example values in this file are illustrative only and will differ on every device and session.

---

## Stream Subscription

**Always subscribe to only the streams your app needs.** Send this as the first message after connecting:

```javascript
ws.send(JSON.stringify({ type: 'subscribe', streams: ['vio', 'hand_tracking'] }));
```

**Subscribable streams:** `vio`, `hand_tracking`, `eye_gaze`, `imu`, `rgb_frame`, `slam_frame`, `et_frame`, `audio`, `ppg`

**Always received (no subscription needed):** `calibration`, `device_status`, `tts_sent`, `subscription_update`

**Default:** If no `subscribe` message is sent, **no streams are delivered** (clients must subscribe).

---

## VIO — Head Pose (~100 Hz)

```typescript
data: {
  position: { x: number, y: number, z: number }; // meters, Y-up, X-mirrored for "mirror view"
  quaternion: { w, x, y, z };                     // relative rotation — USE THIS for device model
  quaternion_full: { w, x, y, z };                // absolute rotation (gravity-aligned) — advanced use only
  euler: { yaw: number, pitch: number, roll: number }; // degrees
  status: number;      // 0 = OK
  poseQuality: number; // higher = better
}
```

> ⚠️ **IMPORTANT for 3D scenes with device + hands:**
> - **Device model:** Use `quaternion` (not `quaternion_full`)
> - **Hand positions:** Use joint positions directly (already in matching world coordinates)
> - **Mixing `quaternion_full` with pre-computed hand positions causes mismatch!**

---

## hand_tracking — Hand Joints & Gestures (~30 Hz)

```typescript
data: {
  left?: HandData;
  right?: HandData;
}

interface HandData {
  joints: Array<{ id: number, position: { x, y, z } }>; // 21 joints, X-mirrored in world space
  confidence: number; // 0.0–1.0
  gestures: {
    pinch:    { detected: boolean, distance: number | null }; // < 3cm = pinch
    thumbsUp: { detected: boolean };
    pointing: { detected: boolean, debug?: { direction: "up"|"down"|"left"|"right"|"forward" } };
  };
}
// Note: Joint positions are already in world coordinates with X-axis mirrored
```

**Joint IDs:**
```
0=THUMB_TIP  1=INDEX_TIP  2=MIDDLE_TIP  3=RING_TIP  4=PINKY_TIP
5=WRIST      6=THUMB_IP   7=THUMB_MCP   8=THUMB_CMC
9=INDEX_DIP  10=INDEX_MCP 11=INDEX_PIP
12=MIDDLE_DIP 13=MIDDLE_MCP 14=MIDDLE_PIP
15=RING_DIP  16=RING_MCP  17=RING_PIP
18=PINKY_DIP 19=PINKY_MCP 20=PALM_CENTER
```

**Connection pairs for skeleton rendering:**
```javascript
const HAND_CONNECTIONS = [
  [5,7],[7,6],[6,0],               // Thumb
  [5,10],[10,11],[11,9],[9,1],     // Index
  [5,13],[13,14],[14,12],[12,2],   // Middle
  [5,16],[16,17],[17,15],[15,3],   // Ring
  [5,19],[19,18],[18,4],           // Pinky (corrected)
  [6,11],[11,14],[14,17]           // Palm
];
```

---

## eye_gaze — Gaze Direction (~30 Hz)

```typescript
data: {
  yaw: number;          // horizontal angle (degrees)
  pitch: number;        // vertical angle (degrees)
  depth: number | null; // estimated gaze depth (meters)
}
```

---

## imu — Accelerometer & Gyroscope (~10 Hz)

```typescript
data: {
  sensor: "imu-left" | "imu-right";
  accel: { x, y, z }; // m/s², includes gravity (~9.8 on Y when upright)
  gyro:  { x, y, z }; // rad/s
}
```

---

## ppg — Heart Rate (~25 Hz)

```typescript
data: {
  value?: number;      // raw PPG sensor value
  heart_rate?: number; // BPM (40–150), available after ~5 seconds
  ir?: number;
  red?: number;
  green?: number;
}
```

---

## rgb_frame — RGB Camera (~10 Hz)

> **Binary WebSocket frame** — not JSON. See binary frame header format below.

Binary header: byte 0 = `0x01` (RGB), byte 1 = `0x00` (no camera_id), remaining bytes = raw JPEG.

After parsing, create a `Blob` and use `URL.createObjectURL()` for `<img>` src.

JPEG quality: 65. Resolution: typically 704×704 (downsampled from 1408).

---

## audio — Microphone (~50 Hz, 20ms frames)

```typescript
data: {
  samples: string;     // base64 float32 array
  num_samples: number;
  num_channels: 1;     // always mono
  sample_rate: number; // typically 48000 Hz
  dtype: "float32";
  level: number;       // RMS 0.0–1.0
  peak: number;        // peak amplitude 0.0–1.0
}
```

---

## slam_frame — SLAM Camera (~10 Hz)

> **Binary WebSocket frame** — not JSON. See binary frame header format below.

Binary header: byte 0 = `0x02` (SLAM), byte 1 = camera_id length, bytes 2..N = camera_id string (`"slam1"` | `"slam2"` | `"slam3"` | `"slam4"`), remaining bytes = raw grayscale JPEG.

JPEG quality: 65. Resolution: typically 320×240 (downsampled).

---

## et_frame — Eye Tracking Camera (~10 Hz)

> **Binary WebSocket frame** — not JSON. See binary frame header format below.

Binary header: byte 0 = `0x03` (ET), byte 1 = camera_id length, bytes 2..N = camera_id string (`"et-left"` | `"et-right"`), remaining bytes = raw infrared JPEG.

JPEG quality: 65.

---

## Binary Frame Header Format (Image Streams)

Image streams (RGB, SLAM, ET) are sent as **binary WebSocket frames** (not JSON text):

| Byte offset | Content | Description |
|---|---|---|
| 0 | Frame type | `0x01` = RGB, `0x02` = SLAM, `0x03` = ET |
| 1 | camera_id length N | 0 for RGB, varies for SLAM/ET |
| 2..2+N | camera_id | UTF-8 string (e.g. `"slam1"`, `"et-left"`) |
| 2+N.. | JPEG bytes | Raw JPEG image data |

**Client-side parsing:**
```javascript
ws.binaryType = 'arraybuffer';
ws.onmessage = (event) => {
  if (event.data instanceof ArrayBuffer) {
    const view = new Uint8Array(event.data);
    const frameType = view[0]; // 0x01=RGB, 0x02=SLAM, 0x03=ET
    const camIdLen = view[1];
    const camId = camIdLen > 0 ? new TextDecoder().decode(view.slice(2, 2 + camIdLen)) : '';
    const jpegBytes = view.slice(2 + camIdLen);
    const blob = new Blob([jpegBytes], { type: 'image/jpeg' });
    const url = URL.createObjectURL(blob);
    // Use url as <img> src — remember to URL.revokeObjectURL() old URLs!
  } else {
    const msg = JSON.parse(event.data); // non-image JSON message
  }
};
```

---

## Client → Server: TTS

```typescript
{ type: "tts", text: string }
```

---

## device_status — Device Info (~1 Hz, polled)

> ⚠️ **CRITICAL FOR AI AGENTS:** All values below are **live sensor data from the device**.
> **NEVER** hardcode or fake these values. If no `device_status` message has been received yet,
> display a "Waiting for device…" or "No data" placeholder — **not** made-up numbers.
> Users will be confused if they see fake battery percentages, temperatures, or WiFi names
> that don't match their actual device.

```typescript
data: {
  serial: string;                    // unique per device (e.g. "1M0XXXXXXXXX")
  battery_level: number;             // 0–100 (%) — LIVE from device, do NOT hardcode
  charging: boolean;
  wifi_connected: boolean;
  wifi_ssid: string | null;          // actual SSID the device is connected to
  skin_temp_celsius: number;         // LIVE device temperature — do NOT hardcode
  thermal_mitigation_triggered: boolean;
}
```

**Example** _(values are illustrative only — real values come from the device):_
```json
{
  "type": "device_status",
  "timestamp": 1710254400.123,
  "data": {
    "serial": "1M0XXXXXXXXX",
    "battery_level": 71,
    "charging": true,
    "wifi_connected": false,
    "wifi_ssid": null,
    "skin_temp_celsius": 31.0,
    "thermal_mitigation_triggered": false
  }
}
```

**Usage — always handle the "no data yet" state:**
```javascript
let deviceStatus = null; // null until first message arrives

aria.on('device_status', (data) => {
  deviceStatus = data;
  updateUI(data);
});

function updateUI(data) {
  if (!data) {
    // No device_status received yet — show placeholder, NOT fake values
    document.getElementById('battery').textContent = 'Waiting for device…';
    document.getElementById('temp').textContent = '—';
    return;
  }
  document.getElementById('battery').textContent = `${data.battery_level}%`;
  document.getElementById('temp').textContent = `${data.skin_temp_celsius}°C`;
}
```
