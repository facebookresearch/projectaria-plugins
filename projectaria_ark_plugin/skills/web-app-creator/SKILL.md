---
name: web-app-creator
description: "Build webapps that integrate with Meta Aria Gen2 (Nebula) smart glasses, usable by any agent that supports skills (Manus, Claude Code, etc.). macOS only — the backend launcher and auto-`open` browser hooks are written for macOS; Windows and Linux are not supported. Covers the full Web App Creator stack: real-time sensor data via WebSocket at ws://localhost:17300 (VIO, hand tracking, eye gaze, IMU, PPG, audio, camera), the nebulaDataUpdate event bridge pattern used by Web App Creator, and the complete bidirectional voice pipeline (VAD, Whisper STT, hallucination filtering, LLM chat, TTS echo suppression). Use this skill for any Aria-connected webapp — from simple data visualizations to full conversational AI experiences."
---

# Web App Creator Skill

> Build webapps that stream live data from Meta Aria Gen2 smart glasses.
> This skill is **agent-agnostic** — it works inside Manus, Claude Code, or any
> agent runtime that loads skills from a folder. A few sections below are flagged
> as **Manus-only** because they describe constraints or APIs unique to that host;
> ignore them when running under another agent.

> [!IMPORTANT]
> **Supported host OS: macOS only (for now).**
> The bundled backend launcher (`start-web-app-creator-backend.command`) and the
> auto-`open` browser hooks are written for macOS. Windows and Linux are **not
> yet supported** — running the launcher on those platforms will fail at the
> Gatekeeper/`open` step, and the Python venv bootstrap has not been tested
> against non-mac toolchains. If the user is not on macOS, tell them up front
> that this skill can't run end-to-end on their machine yet, rather than
> walking them down a path that will dead-end later.

## Architecture Overview

The Aria backend runs locally and exposes two interfaces:

1. **Raw WebSocket** — `ws://localhost:17300` — push-based JSON text + binary image frames, server → client
2. **nebulaDataUpdate event bridge** — the Web App Creator frontend re-dispatches WebSocket messages as DOM `CustomEvent`s so generated HTML components can consume data without managing their own WebSocket connection

**Which pattern to use:**

| Use Case | Pattern |
|---|---|
| Standalone webapp / new project | Raw WebSocket (`ws://localhost:17300`) |
| Component generated inside Web App Creator iframe | `nebulaDataUpdate` event listener |
| Full voice pipeline (STT + LLM + TTS) | Requires full-stack project (`web-db-user`) |

---

## Starting the Backend

The Web App Creator backend is what serves `ws://localhost:17300` and what every template in this skill connects to. **Nothing in the skill works until this is running.**

### The only supported way: double-click the launcher

Tell the user to:

1. Open Finder, navigate to the skill folder (`skills/web-app-creator/`), then into the `web-app-creator-backend/` subfolder
2. **Double-click** `start-web-app-creator-backend.command`
3. A Terminal window opens, the colored launcher banner appears, and it prints `WebSocket listening on ws://localhost:17300` once the device is streaming
4. **Leave that Terminal window open** while you use the skill. To stop, press `Ctrl+C` in that window (or just close it)

> **Do NOT instruct the user to run `bash start-web-app-creator-backend.command` from a terminal.** That path looks equivalent but on many setups it does not behave the same (Terminal.app vs raw bash differs in TTY, environment, and how the launcher's foreground/keep-alive loop interacts with Ctrl+C). Always direct the user to the Finder double-click. The raw `python backend/websocket_bridge.py` entrypoint is for backend developers only — do not surface it to end users.

### If macOS shows a security alert (first launch only)

The launcher is an unsigned `.command` file, so on first run macOS Gatekeeper may show a dialog saying *"start-web-app-creator-backend.command was not opened because Apple cannot verify it is free of malware"* or similar. Guide the user through this one-time unblock:

1. In the alert dialog, click **Done** (or **Cancel**) — **do NOT** click "Move to Bin" / "Move to Trash".
2. Open **System Settings → Privacy & Security**.
3. Scroll down to the **Security** section. There will be a message about `start-web-app-creator-backend.command` being blocked.
4. Click **Open Anyway** next to that message. macOS will ask for confirmation; approve it.
5. Now go back to Finder and double-click `start-web-app-creator-backend.command` again. This time it will run.

This unblock only has to be done once per machine.

### Prerequisites

- Aria Gen2 glasses **connected via USB** and unlocked
- In the **Aria Companion App** on your phone, open the paired glasses' settings and turn on the **"Enable USB Network"** toggle. The backend uses mDNS over the USB network to discover and stream from the device — without this it will not see any sensor data even though the cable is connected.
- Python 3.11+ with `pip install -r skills/web-app-creator/web-app-creator-backend/requirements.txt` already done (the launcher will guide the user through any missing deps)

Once the banner shows `WebSocket listening on ws://localhost:17300`, the templates below will start receiving live data the moment they open in a browser.

---

## 🎯 Start Here: Bundled Templates

> **Rule of thumb: copy + trim a template > write from scratch.** The two HTML templates below already cover ~90% of what generated components need. Copy one into your project, delete what you don't use, then customize. Only fall back to the raw `WebSocket` / `nebulaDataUpdate` patterns below if neither template fits.

### Decision tree

| What you're building | Start from | Where it lives |
|---|---|---|
| 3D scene — glasses pose, hand skeleton, AR overlay, head/hand-tracked game | `DevicePoseAndHands.html` | `templates/device-pose-and-hands/` |
| Any sensor visualization — RGB / SLAM / ET cameras, VIO, IMU, audio, PPG, gestures, TTS UI, multi-sensor dashboard | `StreamPanel.html` | `templates/stream-panels/` |
| Voice loop (mic → STT → LLM → TTS) | `voice-pipeline/` (React hooks + server functions) | `templates/voice-pipeline/` |
| None of the above (rare) | Pattern 1 — raw WebSocket | see below |

Both HTML templates are single self-contained files (no React, no build step) and auto-connect to `ws://localhost:17300`. Drop them into `generated_components/<id>/component.html` and they just work.

### Do not recreate things the templates already do

| Don't write your own | The template already has it |
|---|---|
| Binary frame parser (`0x01` / `0x02` / `0x03` header decode → Blob → `URL.createObjectURL`) | `StreamPanel.html` (`handleBinaryFrame` + blob URL revocation) |
| WebSocket auto-reconnect with exponential backoff | Both HTML templates |
| 21-joint hand skeleton renderer (bone connections + joint spheres) | `StreamPanel.html` `drawHand()` and `DevicePoseAndHands.html` |
| Audio ring buffer + Web Audio playback (`ScriptProcessorNode`, underrun handling) | `StreamPanel.html` `writeAudioSamples()` |
| IMU 2D arrow / waveform renderer | `StreamPanel.html` `drawIMU()` + `drawArrow()` |
| Eye-gaze crosshair canvas | `StreamPanel.html` `drawGaze()` |
| PPG min/max-normalized waveform | `StreamPanel.html` `drawPpgWaveform()` |
| TTS textarea + quick-send chips + status badge | `StreamPanel.html` TTS section |
| 3D glasses model loader (OBJ + JSON wireframe) | `DevicePoseAndHands.html` |
| Orbit camera (drag-rotate + scroll-zoom) | `DevicePoseAndHands.html` |
| VAD state machine, hallucination filter, TTS echo suppression | `voice-pipeline/` (see its `README.md`) |

If you find yourself re-implementing any of the rows above, **stop and copy the template instead.**

---

## ⚠️ Manus Preview Limitation (Manus-only)

Due to a recent change in Manus, the side-preview can no longer access local WebSocket services (`ws://localhost`). To use the webapp with live Aria data, **publish** the project and **open it in a new browser tab**.

> Not running under Manus (e.g. Claude Code, local dev)? Skip this section — `ws://localhost` works in normal browser tabs.

---

## ⚠️ Migrating Projects Built with Older Web App Creator Skill

If a user is working on a project created with an older version of the Web App Creator skill, **three things need updating**. (Quick check: does the WebSocket URL use port `8080`? If yes, it's an old project and needs migration.)

### 1. WebSocket Port Changed
- Old: `ws://localhost:8080`
- New: `ws://localhost:17300`
- **Action:** Find and replace all `8080` → `17300` in WebSocket connection URLs.

### 2. Stream Subscription is Now Mandatory
- Old behavior: clients received ALL streams by default on connect.
- New behavior: clients receive NOTHING until they send a `subscribe` message.
- **Action:** Ensure `ws.onopen` sends `{"type": "subscribe", "streams": ["vio", "hand_tracking", ...]}` with the streams the project actually needs.

### 3. Video Streams Now Use Binary WebSocket Frames
- Old: image data arrived as JSON with base64-encoded JPEG in `data.image` field, rendered via `data:image/jpeg;base64,...` data URI.
- New: image data arrives as binary WebSocket frames (ArrayBuffer) with a compact header (1 byte type + camera_id + raw JPEG bytes).
- **Action:**
  - Add `ws.binaryType = 'arraybuffer'` after creating WebSocket
  - In `onmessage`: check `event.data instanceof ArrayBuffer` — if true, parse the binary header, create a `Blob`, use `URL.createObjectURL()` for `<img>` src
  - If false (text): `JSON.parse()` as before for non-image data
  - Remember to `URL.revokeObjectURL()` old URLs to avoid memory leaks
  - Binary frame header format: byte 0 = frame type (`0x01`=RGB, `0x02`=SLAM, `0x03`=ET), byte 1 = camera_id length, bytes 2..N = camera_id string, rest = JPEG bytes

---

## Pattern 1 — Raw WebSocket

> **Reference only.** For any browser visualization, copy `templates/stream-panels/StreamPanel.html` and trim — it already implements everything below plus binary frame decoding, auto-reconnect, FPS tracking, and per-stream rendering. Use this raw pattern only when neither HTML template fits: non-browser clients, Node.js servers, or deeply custom data flows.

```javascript
class AriaClient {
  constructor(url = 'ws://localhost:17300') {
    this.ws = null;
    this.url = url;
    this.handlers = {};
  }
  connect() {
    this.ws = new WebSocket(this.url);
    this.ws.binaryType = 'arraybuffer';
    this.ws.onopen = () => {
      // Must subscribe to receive data
      this.ws.send(JSON.stringify({ type: 'subscribe', streams: Object.keys(this.handlers) }));
      this.onConnect?.();
    };
    this.ws.onmessage = (e) => {
      if (e.data instanceof ArrayBuffer) {
        // Binary image frame
        const view = new Uint8Array(e.data);
        const frameType = view[0]; // 0x01=RGB, 0x02=SLAM, 0x03=ET
        const camIdLen = view[1];
        const camId = camIdLen > 0 ? new TextDecoder().decode(view.slice(2, 2+camIdLen)) : '';
        const jpegBytes = view.slice(2+camIdLen);
        const blob = new Blob([jpegBytes], { type: 'image/jpeg' });
        const url = URL.createObjectURL(blob);
        const type = frameType === 0x01 ? 'rgb_frame' : frameType === 0x02 ? 'slam_frame' : 'et_frame';
        this.handlers[type]?.({ image: url, camera_id: camId });
      } else {
        const msg = JSON.parse(e.data);
        this.handlers[msg.type]?.(msg.data, msg.timestamp);
      }
    };
    this.ws.onclose = () => {
      this.onDisconnect?.();
      setTimeout(() => this.connect(), 3000); // auto-reconnect
    };
  }
  on(type, fn) { this.handlers[type] = fn; return this; }
  sendTTS(text) { this.ws?.send(JSON.stringify({ type: 'tts', text })); }
}

const aria = new AriaClient();
aria
  .on('vio', (data) => { /* head pose */ })
  .on('hand_tracking', (data) => { /* hands */ })
  .on('eye_gaze', (data) => { /* gaze */ })
  .on('imu', (data) => { /* motion */ })
  .on('ppg', (data) => { /* heart rate */ })
  .on('rgb_frame', (data) => { /* camera */ });
aria.connect();
```

> **HTTPS/WSS note:** Browsers block `ws://` (insecure) from `https://` pages. For deployed sites, users must run Chrome with `--allow-insecure-localhost` or access the site via `http://`.

---

## ⚡ Stream Subscription (Performance Optimization)

**IMPORTANT:** Always subscribe to only the streams your app needs. This dramatically reduces bandwidth and CPU usage — the backend skips expensive processing (image encoding, base64 conversion) for streams nobody is watching.

### How it works

Send a `subscribe` message immediately after connecting:

```javascript
ws.onopen = () => {
  ws.send(JSON.stringify({
    type: 'subscribe',
    streams: ['vio', 'hand_tracking']  // Only what you need
  }));
};
```

**Valid stream types:** `vio`, `hand_tracking`, `eye_gaze`, `imu`, `rgb_frame`, `slam_frame`, `et_frame`, `audio`, `ppg`

**Always received (no subscription needed):** `calibration`, `device_status`

**Default (no subscribe sent):** No streams are delivered — clients must subscribe.

### React hook usage

```javascript
// Subscribe at mount time
const { streamData, subscribe } = useNebulaStream({
  subscribeTo: ['vio', 'hand_tracking', 'eye_gaze']
});

// Or subscribe dynamically later
subscribe(['vio', 'hand_tracking', 'audio']);
```

### TypeScript hook usage

```typescript
const { vioRef, handTrackingRef, subscribe } = useAriaStream(
    'ws://localhost:17300',
    ['vio', 'hand_tracking']  // subscribe on connect
  );
```

### Guidelines for choosing streams

| App Type | Recommended Streams |
|---|---|
| 3D visualization (hands + head) | `vio`, `hand_tracking` |
| Eye tracking heatmap | `vio`, `eye_gaze` |
| Voice assistant | `audio`, `vio` |
| Heart rate monitor | `ppg` |
| Camera feed overlay | `rgb_frame`, `vio` |
| Full dashboard / debug | Subscribe to all: `['vio','hand_tracking','eye_gaze','imu','rgb_frame','slam_frame','et_frame','audio','ppg']` |

---

## Pattern 2 — nebulaDataUpdate Event (Web App Creator components)

Components generated inside Web App Creator receive data via a DOM event. The host app dispatches it; components only need to listen:

```javascript
window.addEventListener('nebulaDataUpdate', (e) => {
  const data = e.detail;
  const vio        = data.vio;          // head pose
  const hands      = data.handTracking; // hand joints + gestures
  const eyeGaze    = data.eyeGaze;      // gaze direction
  const imu        = data.imu;          // accelerometer + gyro
  const ppg        = data.ppg;          // heart rate
  const rgbFrame   = data.rgbFrame;     // camera (base64 JPEG)
  const audio      = data.audio;        // audio level/samples
});
```

---

## Sensor Data Reference

See `references/sensor_schemas.md` for full TypeScript interfaces and examples for all 9 message types.

See `references/visual_style_guide.md` for the **optional** Project Aria visual style guide (colors, typography, spacing, etc.).

**Quick reference — key fields:**

| Type | Key Fields | Frequency |
|---|---|---|
| `vio` | `position{x,y,z}`, `euler{yaw,pitch,roll}`, `quaternion_full` | ~100 Hz |
| `hand_tracking` | `left/right.joints[21]`, `.gestures.pinch/thumbsUp/pointing` | ~30 Hz |
| `eye_gaze` | `yaw`, `pitch`, `depth` | ~30 Hz |
| `imu` | `accel{x,y,z}`, `gyro{x,y,z}` | ~10 Hz |
| `ppg` | `heart_rate` (BPM), `value` (raw) | ~25 Hz |
| `rgb_frame` | Binary WebSocket frame (blob URL) | ~10 Hz |
| `audio` | `samples` (base64 float32), `level`, `peak`, `sample_rate` | ~50 Hz |
| `slam_frame` | Binary WebSocket frame (blob URL), `camera_id` | ~10 Hz |
| `et_frame` | Binary WebSocket frame (blob URL), `camera_id` | ~10 Hz |

---

## Common Patterns

### Display camera feed
```javascript
// RGB frames arrive as binary WebSocket frames (blob URLs from useNebulaStream)
// If using the AriaClient class:
aria.on('rgb_frame', (data) => {
  // data.image is already a blob URL from URL.createObjectURL()
  const oldSrc = document.getElementById('cam').src;
  document.getElementById('cam').src = data.image;
  if (oldSrc.startsWith('blob:')) URL.revokeObjectURL(oldSrc);
});
```

### Detect pinch gesture
```javascript
aria.on('hand_tracking', (data) => {
  if (data.right?.gestures.pinch.detected) triggerAction();
});
```

### Gaze cursor
```javascript
aria.on('eye_gaze', (data) => {
  const x = Math.tan(data.yaw * Math.PI / 180) * 100;
  const y = -Math.tan(data.pitch * Math.PI / 180) * 100;
  cursor.style.transform = `translate(${x}px, ${y}px)`;
});
```

### Transform hand joints to world space (3D scenes)
```javascript
// Hand positions are already in world coordinates (X-mirrored by backend)
// Simply use them directly with VIO position offset
function toWorld(jointPos, vio) {
  return new THREE.Vector3(jointPos.x, jointPos.y, jointPos.z)
    .add(new THREE.Vector3(vio.position.x, vio.position.y, vio.position.z));
}
```

### Decode audio samples
```javascript
aria.on('audio', (data) => {
  const bytes = Uint8Array.from(atob(data.samples), c => c.charCodeAt(0));
  const float32 = new Float32Array(bytes.buffer);
  // float32 = PCM mono at data.sample_rate Hz
});
```

### Send TTS to glasses speaker
```javascript
aria.sendTTS('Hello from the webapp!');
// Or via raw WebSocket:
ws.send(JSON.stringify({ type: 'tts', text: 'Hello!' }));
```

---

## Voice Pipeline (STT + LLM + TTS)

The full bidirectional voice pipeline turns Aria glasses into a conversational AI device. It requires a **full-stack project** (`web-db-user`) because Whisper, LLM, and S3 are server-side only.

### Pipeline Architecture

```
Aria mic → ws://localhost:17300 (audio frames at 50Hz)
  → useAriaAudio hook (frame reception, ref-based callback)
  → useVAD hook (3-state machine: idle → listening → processing)
  → WAV encoding (Float32 → 16-bit PCM)
  → trpc.voice.transcribe (Base64 → S3 → Whisper API)
  → Hallucination filter (80+ phrases, 4 strategies)
  → trpc.voice.chat (LLM with last 10 messages context)
  → sendTTS(responseText) → ws://localhost:17300
  → Aria glasses speaker plays response
  → VAD paused for estimated TTS duration (echo suppression)
```

### VAD Default Parameters

```typescript
const DEFAULT_VAD_CONFIG = {
  speechStartThreshold: 0.040,  // RMS to trigger speech detection
  silenceThreshold: 0.012,      // RMS below which counts as silence
  minSpeechDuration: 0.35,      // Minimum clip length (seconds)
  baseSilenceDuration: 1.0,     // Silence timeout (seconds)
  maxSilenceDuration: 2.0,      // Max silence timeout for long speech
  longSpeechThreshold: 5.0,     // Speech duration before timeout scales up
  preSpeechBuffer: 0.3,         // Pre-speech ring buffer (seconds)
  maxUtteranceDuration: 30,     // Hard cap (seconds)
};
```

### TTS Echo Suppression

```typescript
// Pause VAD for estimated TTS duration to prevent feedback loop
function estimateTTSDuration(text: string): number {
  const words = text.trim().split(/\s+/).length;
  return Math.max(2, words / 2.5 + 1.5); // ~150 WPM + 1.5s buffer
}
```

### LLM System Prompt for Voice

```typescript
const SYSTEM_PROMPT = `You are a helpful voice assistant on Meta Aria smart glasses.
Keep responses concise — 1-3 sentences, no markdown or bullet points.
Always respond in English regardless of the user's language.
(Aria TTS is English-only.)`;
```

### Integration Steps

**Default (platform-agnostic, OpenAI key only):**

1. Copy `client/useAriaAudio.ts` and `client/useVAD.ts` into your React project's `src/hooks/`
2. Copy the entire `server/` folder into your backend (any Node 18+ runtime)
3. Set `OPENAI_API_KEY` in your environment (or see `.env.example` for other providers)
4. Wire `transcribeAudio()` and `llmChat()` into HTTP routes — see `examples/express-server.ts`
5. Use `useAriaAudio` for the WebSocket connection and `useVAD` for speech detection
6. On VAD capture, POST the audio Blob to `/api/voice/transcribe`, then POST messages to `/api/voice/chat`
7. Send the LLM response back: `sendTTS(responseText)`

**Manus / Forge (legacy):** copy `examples/manus-trpc-router.ts` verbatim into your tRPC tree — it still works against the original Manus framework files.

### Critical Pitfalls

| Pitfall | Consequence | Fix |
|---|---|---|
| Auto-generated Whisper prompts | Whisper hallucinates the prompt text verbatim on silent audio | Only pass `prompt` if user explicitly provides one |
| Smoothed RMS in VAD | Silence threshold never reached; VAD stuck in "listening" | Use raw per-frame RMS, no EMA smoothing |
| No TTS echo suppression | Infinite loop: TTS → mic → VAD → STT → LLM → TTS → ... | Pause VAD for estimated TTS duration after every `sendTTS` call |
| React state for audio frames | Frames dropped at 50 Hz | Use ref-based callback via `registerAudioCallback()` |
| Non-English TTS text | Garbled or silent playback | Enforce English-only in LLM system prompt |

### Environment Variables

The new `server/transcribeAudio.ts` and `server/llmChat.ts` auto-detect any of these schemes — set whichever applies:

| Scheme | STT | LLM | Notes |
|---|---|---|---|
| **OpenAI only** | `OPENAI_API_KEY` | (same key) | Simplest. GPT-4o-mini default. |
| **Claude + Whisper** | `STT_API_KEY` (OpenAI) | `ANTHROPIC_API_KEY` | Best quality chat. Claude Sonnet 4 default. |
| **Local (free)** | `STT_BASE_URL=http://localhost:8080` (whisper.cpp) | `LLM_BASE_URL=http://localhost:11434/v1` (Ollama) | Zero cost. |
| **Manus** | `BUILT_IN_FORGE_API_KEY` + `BUILT_IN_FORGE_API_URL` | (same) | Auto-fallback for legacy. |

See `templates/voice-pipeline/.env.example` for full configuration recipes and `templates/voice-pipeline/README.md` for the provider matrix, VAD configuration, hallucination filter, TTS echo suppression, and pitfalls.

---

## Bundled Templates

| Template | Description |
|---|---|
| `templates/device-pose-and-hands/DevicePoseAndHands.html` | **🎯 PRIMARY TEMPLATE for 3D visualization** — Use this as your starting point for any project requiring device pose, hand tracking, or 3D glasses rendering. Features: WebSocket + nebulaDataUpdate dual data sources, interactive 3D glasses model, hand skeleton with gestures, multiple view modes (Toon/Wireframe/Hologram/X-Ray/Normal), orbit camera controls. Loads geometry from sibling `templates/resources/`. |
| `templates/device-pose-and-hands/README.md` | One-paragraph overview + "when to use" guidance for the 3D template. |
| `templates/stream-panels/StreamPanel.html` | **Multi-sensor sandbox dashboard** — single self-contained HTML file (no React, no build step) that subscribes to every Aria stream type and renders 11 sections: Device Status, RGB, SLAM, Eye Tracking, Hand Tracking, Statistics, VIO, IMU, Audio (with ring-buffer playback), TTS, PPG. Use as a starting point for any sensor-dashboard component. |
| `templates/stream-panels/README.md` | One-paragraph overview + section list + "when to use" guidance for the sensor-dashboard template. |
| `templates/voice-pipeline/client/useAriaAudio.ts` | React hook: WebSocket connection with auto-reconnect, audio frame reception, and TTS send |
| `templates/voice-pipeline/client/useVAD.ts` | React hook: browser-side VAD — 3-state machine, raw RMS, pre-speech buffer, dynamic silence timeout |
| `templates/voice-pipeline/server/transcribeAudio.ts` | Platform-agnostic Whisper client — Blob/Buffer/URL inputs, hallucination filter built-in |
| `templates/voice-pipeline/server/llmChat.ts` | Dual-provider chat — OpenAI + Anthropic Claude, native fetch (no SDK) |
| `templates/voice-pipeline/server/hallucinationFilter.ts` | Pure function: classify Whisper output as legitimate vs hallucination |
| `templates/voice-pipeline/server/types.ts` | Shared types — no framework or ORM dependency |
| `templates/voice-pipeline/examples/express-server.ts` | Universal Express HTTP wiring — recommended starting point |
| `templates/voice-pipeline/examples/manus-trpc-router.ts` | **Legacy** original Manus / Forge tRPC router (only works inside Manus) |
| `templates/voice-pipeline/.env.example` | All supported configuration recipes |
| `templates/voice-pipeline/README.md` | Layout, provider matrix, migration notes |
| `templates/resources/aria-glasses.obj` | Aria Gen2 glasses 3D mesh (OBJ format, 2.9MB) |
| `templates/resources/glasses.json` | Glasses geometry in JSON format for Three.js direct loading |
| `templates/resources/glasses_wireframe.json` | Wireframe geometry for the hologram/wireframe view modes |
| `templates/resources/aria-icon-dark.png` | Aria glasses icon (dark variant) for UI use |
| `templates/resources/aria-specs.png` | Aria glasses specs/profile image (used as the StreamPanel device-status thumbnail) |

---

## 🎯 DevicePoseAndHands.html — The Go-To Template for 3D

**When to use DevicePoseAndHands.html:**
- ✅ Any project showing 3D glasses model
- ✅ Any project with hand tracking visualization
- ✅ Any project displaying device pose/orientation
- ✅ Any AR preview or spatial visualization
- ✅ Games or interactive experiences using head/hand tracking

**What's included:**
- WebSocket connection to `ws://localhost:17300` (auto-reconnect)
- nebulaDataUpdate event listener (for iframe compatibility)
- 3D Aria glasses model (OBJ + JSON wireframe)
- Hand skeleton rendering with joint spheres and bone connections
- Gesture detection display (pinch, thumbsUp, pointing)
- 6 view modes: Vertices, Toon, Wireframe, Hologram, X-Ray, Normal
- Orbit camera with mouse drag rotation and scroll zoom
- Developer panel with coordinate debugging

**How to use as starting point:**
1. Copy `templates/device-pose-and-hands/DevicePoseAndHands.html` to your project (and copy the sibling `templates/resources/` folder, or update the asset paths inside the file)
2. Modify the visual style, add your UI elements
3. Add your application logic in the animation loop
4. The data connection and 3D rendering are already working

**Key code sections to customize:**
```javascript
// Animation loop — add your logic here
function animate(time) {
  // vioData contains: position, quaternion, euler
  // handData contains: left/right hands with joints and gestures

  // Your custom logic goes here
  if (handData?.right?.gestures.pinch.detected) {
    // React to pinch gesture
  }
}
```

---

## 🎯 StreamPanel.html — The Go-To Template for Sensor Panels

**When to use StreamPanel.html:**
- ✅ Any panel / dashboard showing live sensor data (RGB, SLAM, ET, VIO, IMU, audio, PPG)
- ✅ Single-sensor mini components (copy the file, delete every section except the one you need)
- ✅ Multi-sensor debug overlays inside Web App Creator
- ✅ Anything that needs binary frame decoding, ring-buffer audio playback, or a TTS input UI
- ✅ First-pass scaffold for *any* 2D visualization component — the section structure is your starting point

**What's included:**
- WebSocket connection to `ws://localhost:17300` with auto-reconnect (exponential backoff, 20 attempts)
- Subscription to every stream type (`rgb_frame`, `slam_frame`, `et_frame`, `vio`, `hand_tracking`, `eye_gaze`, `imu`, `audio`, `ppg`, `device_status`)
- Binary frame decoder (`0x01` / `0x02` / `0x03` headers → Blob → `URL.createObjectURL`) with blob-URL revocation
- 11 prebuilt sensor sections (Device Status, RGB, SLAM, Eye Tracking, Hand Tracking, Statistics, VIO, IMU, Audio, TTS, PPG)
- Canvas drawing helpers: `drawHand()` (21-joint skeleton), `drawGaze()` (crosshair), `drawIMU()` + `drawArrow()`, `drawAudioWaveform()`, `drawPpgWaveform()`
- Web Audio ring buffer with `ScriptProcessorNode` for live mic playback
- TTS textarea + quick-send chips + status badge sending `{type:'tts', text}` over the same socket
- FPS counter, connection indicator, and inline SVG icons (no external CDN deps)
- Single light theme, single-column scrollable layout — designed to drop into a sandbox iframe

**How to use as starting point:**
1. Copy `templates/stream-panels/StreamPanel.html` into your project (e.g. `generated_components/<id>/component.html`).
2. Open it in a browser (or load it inside an iframe) with the Aria backend running on `ws://localhost:17300`. Verify the live data flows.
3. **Delete every section you don't need** — every section in the `<div class="grid">` is structurally independent, and dropping a section also lets you remove its CSS rules and its `update*()` handler in the script block.
4. Restyle the surviving sections to match your design; the data wiring keeps working without changes.
5. Add your application logic alongside the existing `update*()` handlers in the inline `<script>`.

**Key code sections to customize:**
```javascript
// Sensor data handlers — add your logic here
function updateVio(d)    { /* head pose: position, euler, quaternion */ }
function updateHands(d)  { /* d.left / d.right hand joints + gestures */ }
function updateGaze(d)   { /* d.yaw, d.pitch, d.depth */ }
function updateImu(d)    { /* d.accel, d.gyro */ }
function updateAudio(d)  { /* d.level + d.samples (base64 float32) */ }
function updatePpg(d)    { /* d.value, d.heart_rate */ }
```

The inline WebSocket logic (binary frame parser + auto-reconnect + FPS counter + ring-buffer audio playback) lives in the `<script>` block at the bottom of the file. **Reuse it as-is** — do not write your own.

### Using the 3D Glasses Model

For Three.js projects, load `glasses.json` directly:

```javascript
fetch('/glasses.json')
  .then(r => r.json())
  .then(json => {
    const geometry = new THREE.BufferGeometry();
    geometry.setAttribute('position',
      new THREE.Float32BufferAttribute(json.vertices, 3));
    geometry.setIndex(json.faces);
    geometry.computeVertexNormals();
    const mesh = new THREE.Mesh(geometry,
      new THREE.MeshStandardMaterial({ color: 0x00d4ff }));
    scene.add(mesh);
  });
```

For the `.obj` file, use Three.js `OBJLoader` from `three/examples/jsm/loaders/OBJLoader.js`.

---

## Coordinate System

All spatial data uses **Y-up coordinates** with **X-axis mirrored** for intuitive "mirror view" display:
- X: right (+) / left (−) — **mirrored at backend** so moving left shows left movement on screen
- Y: up (+) / down (−)
- Z: forward (+) / backward (−)
- Position unit: **meters**
- Rotation: quaternion `(w, x, y, z)` or Euler degrees

**Important:** Backend data is "what you see is what you get" — no CSS transforms or coordinate negation needed on frontend.

---

## ⚠️ Critical: Quaternion Usage for 3D Scenes

When building 3D scenes with **both device (glasses) and hands**, you must use the correct quaternion field:

### Device Pose (Glasses Model)
```javascript
// ✅ CORRECT: Use `quaternion` (relative rotation in odometry frame)
const q = vio.quaternion;
glassesModel.quaternion.set(q.x, q.y, q.z, q.w);
glassesModel.position.set(vio.position.x, vio.position.y, vio.position.z);
```

### Hand Positions
```javascript
// ✅ CORRECT: Use joint positions directly (already in world coordinates)
handData.joints.forEach(joint => {
  const pos = new THREE.Vector3(joint.position.x, joint.position.y, joint.position.z);
  // Use pos directly — no transformation needed
});
```

### Common Mistake ❌
```javascript
// ❌ WRONG: Using quaternion_full for device causes mismatch with hands
const q = vio.quaternion_full;  // DON'T use this for device pose in 3D scenes
glassesModel.quaternion.set(q.x, q.y, q.z, q.w);
// Result: Hands appear in wrong positions relative to glasses!
```

### Quaternion Field Reference

| Field | Description | Use For |
|-------|-------------|---------|
| `quaternion` | Relative rotation (odometry frame) | **Device/glasses model in 3D scenes** |
| `quaternion_full` | Absolute rotation (gravity-aligned) | Standalone orientation display, compass, etc. |
| `hand.joints[].position` | World coordinates (pre-computed by backend) | **Hand skeleton rendering** |

**Why this matters:** The backend pre-computes hand joint positions in world coordinates that match the device's `quaternion` frame. Using `quaternion_full` for the device will cause a coordinate frame mismatch — hands will appear in wrong positions relative to the glasses.

---

## Troubleshooting

| Symptom | Fix |
|---|---|
| Connection refused | Start the backend: double-click `skills/web-app-creator/web-app-creator-backend/start-web-app-creator-backend.command`. See the "Starting the Backend" section above — including the macOS security-alert workaround if it's the first launch on this machine. |
| Backend connects but no data flows | Open the Aria Companion App on your phone, go to the paired glasses' settings, and turn on "Enable USB Network" toggle. |
| Launcher fails with auth/cert errors ("not paired", "couldn't read cert file", "silent-success pairing", or it hangs after `auth pair` succeeds) | The Aria SDK keeps device-pair credentials and streaming TLS certs in `~/.aria/`. These can get into a stale or corrupted state — e.g. after switching glasses, after a partial pairing, or after the SDK was upgraded. **Reset it**: back up the folder (`mv ~/.aria ~/.aria.backup.$(date +%Y%m%d-%H%M%S)`), then re-run the launcher. It will re-pair from scratch (approve the prompt in the Aria Companion App when it appears) and regenerate fresh certs. |
| No data | Glasses must be connected (USB) and streaming |
| `heart_rate` is null | Wait 5+ seconds for PPG buffer |
| Hand tracking absent | Hands must be in camera FOV |
| `ws://` blocked by browser | Use `http://` origin or enable `--allow-insecure-localhost` |
| VAD stuck in "listening" | Check RMS thresholds; ensure raw (not smoothed) RMS is used |
| Whisper returns hallucinations | Check hallucination filter is active; never pass auto-generated prompts |
| TTS feedback loop | Ensure `sendTTSWithSuppression` is used, not raw `sendTTS` |
