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
 * Shared types for the voice pipeline server module.
 * Platform-agnostic — no framework or ORM dependencies.
 */

// ── Whisper API response types (OpenAI-compatible) ──

export type WhisperSegment = {
  id: number;
  seek: number;
  start: number;
  end: number;
  text: string;
  tokens: number[];
  temperature: number;
  avg_logprob: number;
  compression_ratio: number;
  no_speech_prob: number;
};

export type WhisperResponse = {
  task: "transcribe";
  language: string;
  duration: number;
  text: string;
  segments: WhisperSegment[];
};

// ── Public types ──

export type TranscribeInput =
  | { audioBlob: Blob; filename?: string; language?: string; prompt?: string }
  | { audioBuffer: Uint8Array | Buffer; mimeType?: string; filename?: string; language?: string; prompt?: string }
  | { audioUrl: string; language?: string; prompt?: string };

export type TranscribeResult = {
  text: string;
  language: string;
  duration: number;
  segments: Array<{ start: number; end: number; text: string }>;
  filtered: boolean;
  filterReason: string | null;
};

export type TranscribeError = {
  error: string;
  code:
    | "FILE_TOO_LARGE"
    | "INVALID_FORMAT"
    | "TRANSCRIPTION_FAILED"
    | "UPLOAD_FAILED"
    | "SERVICE_ERROR"
    | "MISSING_API_KEY";
  details?: string;
};

// ── Chat types ──

export type ChatMessage = {
  role: "system" | "user" | "assistant";
  content: string;
};

export type ChatProvider = "openai" | "anthropic";

export type ChatOptions = {
  messages: ChatMessage[];
  /** Default: read from STT_/LLM_ env vars in this priority */
  provider?: ChatProvider;
  model?: string;
  apiKey?: string;
  baseUrl?: string;
  /** System prompt — if not given and messages[0].role !== "system", a sensible default is used. */
  systemPrompt?: string;
  maxTokens?: number;
  temperature?: number;
};

export type ChatResult = { text: string };

export type ChatError = {
  error: string;
  code: "MISSING_API_KEY" | "PROVIDER_ERROR" | "INVALID_RESPONSE";
  details?: string;
};
