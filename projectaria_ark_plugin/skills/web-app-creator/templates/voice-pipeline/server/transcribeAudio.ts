/**
 * Copyright (c) Meta Platforms, Inc. and affiliates.
 *
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 *     http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 */

/**
 * transcribeAudio — platform-agnostic Whisper-API client.
 *
 * Works with **any OpenAI-compatible STT endpoint**. Tested against:
 *   • OpenAI                  https://api.openai.com
 *   • Groq Whisper            https://api.groq.com/openai
 *   • Azure OpenAI Whisper    https://<resource>.openai.azure.com/openai/deployments/<deployment>
 *   • whisper.cpp server      http://localhost:8080
 *   • Manus forge             (set BUILT_IN_FORGE_API_URL / KEY)
 *
 * Three input modes:
 *   1. Direct Blob          (recommended — no storage required)
 *   2. Raw bytes (Buffer)   (when caller already has bytes)
 *   3. URL                  (when audio is hosted somewhere — e.g. S3)
 *
 * Hallucination filtering is applied automatically (can be disabled).
 *
 * Required env (any one of these schemes):
 *   STT_API_KEY              + optional STT_BASE_URL / STT_MODEL
 *   OPENAI_API_KEY           + optional OPENAI_BASE_URL  (used as fallback)
 *   BUILT_IN_FORGE_API_KEY   + BUILT_IN_FORGE_API_URL    (Manus compatibility)
 */

import { classifyTranscription } from "./hallucinationFilter";
import type {
  TranscribeInput,
  TranscribeResult,
  TranscribeError,
  WhisperResponse,
} from "./types";

const MAX_AUDIO_MB = 16;

type ResolvedConfig = {
  baseUrl: string;
  apiKey: string;
  model: string;
};

function resolveConfig(override?: { baseUrl?: string; apiKey?: string; model?: string }): ResolvedConfig | null {
  const apiKey =
    override?.apiKey ??
    process.env.STT_API_KEY ??
    process.env.OPENAI_API_KEY ??
    process.env.BUILT_IN_FORGE_API_KEY;
  if (!apiKey) return null;

  const baseUrl =
    override?.baseUrl ??
    process.env.STT_BASE_URL ??
    process.env.OPENAI_BASE_URL ??
    process.env.BUILT_IN_FORGE_API_URL ??
    "https://api.openai.com";

  const model = override?.model ?? process.env.STT_MODEL ?? "whisper-1";

  return {
    baseUrl: baseUrl.replace(/\/+$/, ""),
    apiKey,
    model,
  };
}

const MIME_TO_EXT: Record<string, string> = {
  "audio/webm": "webm",
  "audio/mp3": "mp3",
  "audio/mpeg": "mp3",
  "audio/wav": "wav",
  "audio/wave": "wav",
  "audio/x-wav": "wav",
  "audio/ogg": "ogg",
  "audio/m4a": "m4a",
  "audio/mp4": "m4a",
  "audio/flac": "flac",
};

function extFor(mime?: string): string {
  if (!mime) return "wav";
  return MIME_TO_EXT[mime.toLowerCase()] ?? "wav";
}

async function inputToBlob(
  input: TranscribeInput
): Promise<{ blob: Blob; filename: string } | TranscribeError> {
  // ── Mode 1: Direct Blob ──
  if ("audioBlob" in input) {
    return {
      blob: input.audioBlob,
      filename: input.filename ?? `audio.${extFor(input.audioBlob.type)}`,
    };
  }

  // ── Mode 2: Raw bytes ──
  if ("audioBuffer" in input) {
    const mime = input.mimeType ?? "audio/wav";
    const bytes =
      input.audioBuffer instanceof Uint8Array
        ? input.audioBuffer
        : new Uint8Array(input.audioBuffer);
    return {
      blob: new Blob([bytes], { type: mime }),
      filename: input.filename ?? `audio.${extFor(mime)}`,
    };
  }

  // ── Mode 3: URL ──
  try {
    const res = await fetch(input.audioUrl);
    if (!res.ok) {
      return {
        error: "Failed to download audio file",
        code: "INVALID_FORMAT",
        details: `HTTP ${res.status}: ${res.statusText}`,
      };
    }
    const buf = new Uint8Array(await res.arrayBuffer());
    const mime = res.headers.get("content-type") ?? "audio/mpeg";
    return {
      blob: new Blob([buf], { type: mime }),
      filename: `audio.${extFor(mime)}`,
    };
  } catch (err) {
    return {
      error: "Failed to fetch audio file",
      code: "SERVICE_ERROR",
      details: err instanceof Error ? err.message : "Unknown error",
    };
  }
}

export type TranscribeAudioOptions = {
  /** Disable hallucination filtering. Default: false (filter enabled). */
  skipHallucinationFilter?: boolean;
  /** Override config (otherwise read from env). */
  baseUrl?: string;
  apiKey?: string;
  model?: string;
};

/**
 * Transcribe audio to text using an OpenAI-compatible Whisper endpoint.
 *
 * @example
 * // Browser → Server: client uploads multipart/form-data, server passes the Blob
 * const result = await transcribeAudio({ audioBlob: req.file.buffer });
 *
 * @example
 * // Pass raw bytes
 * const result = await transcribeAudio({
 *   audioBuffer: Buffer.from(base64String, 'base64'),
 *   mimeType: 'audio/wav',
 * });
 */
export async function transcribeAudio(
  input: TranscribeInput,
  options: TranscribeAudioOptions = {}
): Promise<TranscribeResult | TranscribeError> {
  const config = resolveConfig(options);
  if (!config) {
    return {
      error: "STT API key is not configured",
      code: "MISSING_API_KEY",
      details:
        "Set STT_API_KEY (or OPENAI_API_KEY) in your environment. " +
        "Optionally STT_BASE_URL to point at a different OpenAI-compatible endpoint.",
    };
  }

  const prepared = await inputToBlob(input);
  if ("error" in prepared) return prepared;

  // Size guard
  const sizeMB = prepared.blob.size / (1024 * 1024);
  if (sizeMB > MAX_AUDIO_MB) {
    return {
      error: "Audio file exceeds maximum size limit",
      code: "FILE_TOO_LARGE",
      details: `File size is ${sizeMB.toFixed(2)}MB, max allowed is ${MAX_AUDIO_MB}MB`,
    };
  }

  // Build multipart body
  const formData = new FormData();
  formData.append("file", prepared.blob, prepared.filename);
  formData.append("model", config.model);
  formData.append("response_format", "verbose_json");

  const lang = "language" in input ? input.language : undefined;
  if (lang) formData.append("language", lang);

  // Only attach a prompt if the caller explicitly provided one — Whisper will
  // hallucinate the prompt text back on near-silent clips.
  const prompt = "prompt" in input ? input.prompt : undefined;
  if (prompt) formData.append("prompt", prompt);

  // Call API
  const url = `${config.baseUrl}/v1/audio/transcriptions`;
  let response: Response;
  try {
    response = await fetch(url, {
      method: "POST",
      headers: {
        authorization: `Bearer ${config.apiKey}`,
        "Accept-Encoding": "identity",
      },
      body: formData,
    });
  } catch (err) {
    return {
      error: "Network error calling STT service",
      code: "SERVICE_ERROR",
      details: err instanceof Error ? err.message : "Unknown error",
    };
  }

  if (!response.ok) {
    const errorText = await response.text().catch(() => "");
    return {
      error: "Transcription service request failed",
      code: "TRANSCRIPTION_FAILED",
      details: `${response.status} ${response.statusText}${errorText ? `: ${errorText}` : ""}`,
    };
  }

  let whisper: WhisperResponse;
  try {
    whisper = (await response.json()) as WhisperResponse;
  } catch (err) {
    return {
      error: "Invalid response from STT service",
      code: "TRANSCRIPTION_FAILED",
      details: err instanceof Error ? err.message : "JSON parse failed",
    };
  }

  // Normalise (some providers return slightly different shapes)
  const text = (whisper.text ?? "").trim();
  const language = whisper.language ?? "en";
  const duration = typeof whisper.duration === "number" ? whisper.duration : 0;
  const segments = Array.isArray(whisper.segments) ? whisper.segments : [];

  // Hallucination filtering
  if (text && !options.skipHallucinationFilter) {
    const verdict = classifyTranscription(text);
    if (verdict.isHallucination) {
      return {
        text: "",
        language,
        duration,
        segments: [],
        filtered: true,
        filterReason: verdict.reason,
      };
    }
  }

  return {
    text,
    language,
    duration,
    segments: segments.map((s) => ({ start: s.start, end: s.end, text: s.text })),
    filtered: false,
    filterReason: null,
  };
}
