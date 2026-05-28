# Stream Panels template

A single self-contained HTML file (`StreamPanel.html`) that renders a multi-sensor dashboard demonstrating how to consume **every** Aria stream type from a vanilla JS page. No build step, no React, no tailwind — just open it in a browser (or drop it into a sandbox iframe under `generated_components/`) and it will connect to `ws://localhost:17300`, subscribe, and start rendering.

## Sections rendered

1. **Device Status** — header bar with battery / WiFi / skin-temp / serial badges (consumes `device_status`).
2. **RGB Camera** — main RGB stream as a JPEG `<img>` decoded from binary frame `0x01`.
3. **SLAM Cameras** — dynamically populated grid; one canvas per `camera_id` from binary frame `0x02`.
4. **Eye Tracking** — left/right ET cameras (binary frame `0x03`) plus a crosshair canvas driven by JSON `eye_gaze`.
5. **Hand Tracking** — left/right hand skeletons + gesture emojis (👌 👍 👆) driven by JSON `hand_tracking`.
6. **Statistics** — FPS / messages-received / live-or-offline indicator.
7. **VIO** — position (m), Euler angles (°), and quaternion from JSON `vio`.
8. **IMU** — accel + gyro values plus 2D arrow waveforms drawn on canvas.
9. **Audio** — level waveform + a toggle that pipes the binary samples through a Web Audio ring buffer to the speakers.
10. **Text-to-Speech** — textarea + send button + two quick-send phrase chips; sends `{type:'tts', text}` over the same socket.
11. **PPG** — 150-point min/max-normalized waveform with BPM + raw value readouts.

## When to use this template

Use `StreamPanel.html` as the starting point when the LLM-generated component needs to:

- Show **multiple** sensor streams at once on a single page.
- Demonstrate end-to-end wiring (binary frame parsing, ring-buffer audio, TTS round-trip).
- Be inspected at a glance during development to verify which streams are actually flowing.

For a focused single-purpose demo (e.g. "show only RGB" or "draw only the IMU"), copy `StreamPanel.html`, then delete the sections you don't need — every section is structurally independent.

For 3D / spatial visualizations, use `../device-pose-and-hands/DevicePoseAndHands.html` instead.
