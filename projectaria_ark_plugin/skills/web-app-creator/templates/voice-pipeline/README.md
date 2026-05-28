# Voice Pipeline Template

A platform-agnostic voice pipeline for Aria Gen2: **mic → STT → LLM → reply**.

Works with **just an OpenAI key** out of the box — or swap in Anthropic Claude, Groq, Azure OpenAI, or fully local whisper.cpp + Ollama.

---

## Layout

```text
voice-pipeline/
├── client/                       React hooks (drop into any React project)
│   ├── useAriaAudio.ts           Subscribe to Aria audio frames over WebSocket
│   └── useVAD.ts                 Voice Activity Detection on the frame stream
│
├── server/                       Pure functions (no framework dependency)
│   ├── transcribeAudio.ts        OpenAI-compatible Whisper client
│   ├── llmChat.ts                OpenAI + Anthropic chat (auto-detects)
│   ├── hallucinationFilter.ts    Whisper hallucination rejection
│   ├── types.ts                  Shared types
│   └── index.ts                  Barrel export
│
├── examples/
│   ├── express-server.ts         Universal Express HTTP wiring (recommended start)
│   └── manus-trpc-router.ts      Original Manus tRPC router (preserved for reference)
│
├── .env.example                  All supported configuration schemes
└── README.md                     This file
```

---

## Quick Start (the literal "OpenAI key only" path)

```bash
# 1. Install (in your project — peer-dep style)
pnpm add express multer
pnpm add -D @types/express @types/multer tsx

# 2. Copy server/ + the express example into your project, then:
export OPENAI_API_KEY=sk-...
pnpm tsx examples/express-server.ts

# 3. From a browser/curl:
curl -X POST http://localhost:8000/api/voice/chat \
  -H "Content-Type: application/json" \
  -d '{"messages":[{"role":"user","content":"Hi"}]}'
```

That's it. Same key handles both transcription and chat.

---

## Use Claude instead of GPT for chat

```bash
export STT_API_KEY=sk-...               # OpenAI (for Whisper — Anthropic has no STT)
export ANTHROPIC_API_KEY=sk-ant-...     # Anthropic (for chat)
export LLM_PROVIDER=anthropic           # auto-detected if set, optional
```

Both keys live side by side; `transcribeAudio` uses the OpenAI one, `llmChat` uses the Anthropic one.

---

## Provider matrix

| Need              | Required key(s)                                  | Notes                                            |
| ----------------- | ------------------------------------------------ | ------------------------------------------------ |
| OpenAI only       | `OPENAI_API_KEY`                                 | Simplest. STT = Whisper, LLM = GPT-4o-mini.      |
| Claude + Whisper  | `STT_API_KEY` (OpenAI) + `ANTHROPIC_API_KEY`     | Best quality chat. Anthropic has no STT.         |
| Groq Whisper      | `STT_API_KEY` (Groq) + `STT_BASE_URL=https://api.groq.com/openai` | 10× faster Whisper, very cheap.                  |
| Azure OpenAI      | `STT_API_KEY` + `STT_BASE_URL=https://<resource>.openai.azure.com/...` | OpenAI-compatible, swap base URL.                |
| Local (free)      | whisper.cpp server + Ollama                      | Set both `STT_BASE_URL` and `LLM_BASE_URL`.      |

See `.env.example` for full configuration recipes. The `examples/manus-trpc-router.ts` file is preserved verbatim for anyone on the legacy Manus / Forge tRPC stack.

---

## Aria audio frame format

Each WebSocket message with `type: "audio"` carries one `AriaAudioFrame`:

```ts
export type AriaAudioFrame = {
  samples:      string;   // Base64-encoded Float32 PCM
  num_samples:  number;   // Samples in this frame
  num_channels: number;   // Always 1 (mono)
  sample_rate:  number;   // Typically 16000 Hz
  dtype:        string;   // Data type descriptor
  level:        number;   // Pre-computed RMS by Aria backend
  peak:         number;   // Pre-computed peak by Aria backend
};
```

Frames arrive at **~50 Hz** (one every ~20ms). Decode `samples` to a `Float32Array`:

```ts
const decodeFrame = (f: AriaAudioFrame): Float32Array => {
  const bin = atob(f.samples);
  const bytes = new Uint8Array(bin.length);
  for (let i = 0; i < bin.length; i++) bytes[i] = bin.charCodeAt(i);
  return new Float32Array(bytes.buffer);
};
```

> **Performance note.** At 50 Hz, React `setState` per frame drops audio. Use a ref-based callback (`registerAudioCallback()`) — see `client/useAriaAudio.ts`.

---

## VAD configuration

`useVAD` runs entirely in the browser and uses **raw per-frame RMS** (no smoothing). It's a 3-state machine:

| State | Meaning | Transition |
|---|---|---|
| `idle` | Waiting for speech; maintains a 300 ms pre-speech ring buffer | → `listening` when RMS > `speechStartThreshold` |
| `listening` | Recording speech; accumulating samples | → `processing` when silence timeout reached **and** clip ≥ `minSpeechDuration` |
| `processing` | Clip captured, sent for transcription | → `idle` when transcription completes / fails |

Defaults (from `client/useVAD.ts`):

```ts
export const DEFAULT_VAD_CONFIG = {
  speechStartThreshold:  0.040,  // RMS to trigger speech detection
  silenceThreshold:      0.012,  // RMS below this = silence
  minSpeechDuration:     0.35,   // Reject clips shorter than this (s)
  baseSilenceDuration:   1.0,    // Base end-of-speech timeout (s)
  maxSilenceDuration:    2.0,    // Max end-of-speech timeout (s)
  longSpeechThreshold:   5.0,    // After this many s, silence timeout grows
  dynamicScalingFactor:  0.2,    // How fast the timeout grows
  maxUtteranceDuration:  30,     // Hard cap on a single clip (s)
  preSpeechBuffer:       0.3,    // Audio kept *before* speech onset (s)
};
```

Why these specific choices:

- **Raw RMS, no EMA smoothing** — smoothing makes the silence threshold un-reachable and gets the VAD stuck in `listening`.
- **300 ms pre-speech buffer** — prevents the first syllable from being clipped.
- **Dynamic silence timeout** — for utterances > 5 s, the silence timeout linearly grows from 1.0 s to 2.0 s, allowing natural pauses without premature cutoff:

  ```ts
  const t = Math.min(base + Math.max(0, dur - long) * scale, maxSilence);
  ```

When a clip is captured it's encoded as a 16-bit PCM WAV blob (44-byte header + samples) and sent directly to the server — no S3 upload required.

---

## Hallucination filter

Whisper hallucinates common phrases on near-silent input ("thanks for watching", "subscribe", etc.). The filter is **on by default** in `transcribeAudio()` — pass `{ skipHallucinationFilter: true }` to disable.

It's also exported as a pure function:

```ts
import { isHallucination, classifyTranscription } from "./server";

isHallucination("thanks for watching"); // true
classifyTranscription("hello world").isHallucination; // false
```

Internally it applies four strategies in order:

1. **Exact phrase match** — 80+ known hallucinations (YouTube CTAs, prompt leaks).
2. **Keyword detection** — ~35 keywords (`subscribe`, `bell icon`, `working language`, `transcribe the user`, …).
3. **Short-text rejection** — single words under 10 chars (`you`, `so`, `um`, …).
4. **Repetitive-text detection** — all words identical (`so so so so`).

When the filter rejects a clip, `transcribeAudio()` returns `{ text: "", filtered: true, filterReason: "hallucination" }` and the client should silently reset VAD to `idle` — never display the rejected text.

---

## TTS echo suppression

When TTS plays through the Aria glasses speaker, the Aria mic picks it up. Without suppression you get an **infinite loop**: TTS → mic → VAD → STT → LLM → TTS → … Pause the VAD for the estimated TTS duration:

```ts
function estimateTTSDuration(text: string): number {
  const words = text.trim().split(/\s+/).length;
  const speaking = words / 2.5;   // ~150 WPM
  const safety   = 1.5;           // padding
  return Math.max(2, speaking + safety);
}

// On send:
sendTTS(text);
setIsTTSPlaying(true);
setTimeout(() => setIsTTSPlaying(false), estimateTTSDuration(text) * 1000);

// In the audio callback:
if (vadEnabled && !isTTSPlayingRef.current) processFrame(frame);
```

A visible cue (e.g. waveform turning orange) while suppression is active makes the behaviour obvious during debugging.

---

## TTS constraints

- **English only.** The Aria on-device TTS engine speaks English. Enforce it in the LLM system prompt:

  > *"You MUST always respond in English, regardless of the language the user speaks in."*

- **Concise output.** Aim for 1–3 sentences. Long replies feel unnatural through the speaker.
- **No formatting.** No markdown, bullets, code, or special characters — plain spoken text only.
- **Send via the same WebSocket** as the audio stream, with `{ "type": "tts", "text": "…" }`.

---

## Pitfalls (read this before debugging)

1. **Never auto-generate Whisper prompts.** Passing any `prompt` (even helpful context like *"The user's working language is English"*) makes Whisper hallucinate the prompt back as the transcription on silent clips. Only pass a prompt if the caller explicitly provides one.
2. **Use raw RMS, not smoothed.** EMA smoothing keeps the VAD stuck in `listening` because the silence threshold never gets reached after speech.
3. **Use a ref-based audio callback, not React state.** At 50 Hz, `setState` per frame drops audio. Register a callback via `registerAudioCallback()` and store it in a `useRef`.
4. **TTS echo suppression is mandatory.** Without it you'll get the infinite TTS↔mic loop above. Even a crude duration estimate is fine; precision isn't required.
5. **Enforce English-only TTS in the system prompt.** The on-device TTS engine garbles or silences non-English text. Make this a non-negotiable rule in the LLM prompt.

---

## Roadmap

- [ ] Hono / Cloudflare Workers example
- [ ] Streaming TTS reply (currently only returns text)
- [ ] Optional cost / latency telemetry hook
