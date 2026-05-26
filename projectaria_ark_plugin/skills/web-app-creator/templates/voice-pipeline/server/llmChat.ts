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
 * llmChat — single function, two providers (OpenAI / Anthropic), zero deps.
 *
 * Auto-detects provider from env, but can be overridden per-call:
 *   LLM_PROVIDER=openai|anthropic   (default: anthropic if ANTHROPIC_API_KEY set, else openai)
 *   LLM_API_KEY                     (fallback to OPENAI_API_KEY / ANTHROPIC_API_KEY)
 *   LLM_MODEL                       (default: gpt-4o-mini / claude-sonnet-4-20250514)
 *   LLM_BASE_URL                    (override default endpoint)
 *
 * Uses native fetch — no SDK install required.
 *
 * @example
 * const result = await llmChat({
 *   messages: [{ role: "user", content: "Hi" }],
 *   systemPrompt: "Be brief.",
 * });
 * if ("text" in result) console.log(result.text);
 */

import type { ChatOptions, ChatResult, ChatError, ChatMessage } from "./types";

const DEFAULT_SYSTEM_PROMPT = `You are a helpful voice assistant running on Meta Aria smart glasses.
Keep responses concise and conversational — they will be spoken aloud via TTS.
Aim for 1-3 sentences. Avoid markdown, bullet points, or formatting.
Be natural, friendly, and direct.`;

type ResolvedChat = {
  provider: "openai" | "anthropic";
  apiKey: string;
  model: string;
  baseUrl: string;
};

function resolveChat(opts: ChatOptions): ResolvedChat | ChatError {
  const provider: "openai" | "anthropic" =
    opts.provider ??
    (process.env.LLM_PROVIDER as "openai" | "anthropic" | undefined) ??
    (process.env.ANTHROPIC_API_KEY ? "anthropic" : "openai");

  const apiKey =
    opts.apiKey ??
    process.env.LLM_API_KEY ??
    (provider === "anthropic"
      ? process.env.ANTHROPIC_API_KEY
      : process.env.OPENAI_API_KEY ?? process.env.BUILT_IN_FORGE_API_KEY);

  if (!apiKey) {
    return {
      error: `LLM API key is not configured for provider "${provider}"`,
      code: "MISSING_API_KEY",
      details:
        provider === "anthropic"
          ? "Set ANTHROPIC_API_KEY (or LLM_API_KEY)."
          : "Set OPENAI_API_KEY (or LLM_API_KEY).",
    };
  }

  const model =
    opts.model ??
    process.env.LLM_MODEL ??
    (provider === "anthropic" ? "claude-sonnet-4-20250514" : "gpt-4o-mini");

  const baseUrl = (
    opts.baseUrl ??
    process.env.LLM_BASE_URL ??
    (provider === "anthropic"
      ? "https://api.anthropic.com"
      : process.env.OPENAI_BASE_URL ?? process.env.BUILT_IN_FORGE_API_URL ?? "https://api.openai.com")
  ).replace(/\/+$/, "");

  return { provider, apiKey, model, baseUrl };
}

function splitSystem(messages: ChatMessage[], fallback: string): { system: string; rest: ChatMessage[] } {
  if (messages.length > 0 && messages[0].role === "system") {
    return { system: messages[0].content, rest: messages.slice(1) };
  }
  return { system: fallback, rest: messages };
}

async function callOpenAI(cfg: ResolvedChat, opts: ChatOptions): Promise<ChatResult | ChatError> {
  const messages: ChatMessage[] =
    opts.messages.length > 0 && opts.messages[0].role === "system"
      ? opts.messages
      : [{ role: "system", content: opts.systemPrompt ?? DEFAULT_SYSTEM_PROMPT }, ...opts.messages];

  let response: Response;
  try {
    response = await fetch(`${cfg.baseUrl}/v1/chat/completions`, {
      method: "POST",
      headers: {
        authorization: `Bearer ${cfg.apiKey}`,
        "content-type": "application/json",
      },
      body: JSON.stringify({
        model: cfg.model,
        messages,
        max_tokens: opts.maxTokens ?? 512,
        temperature: opts.temperature ?? 0.7,
      }),
    });
  } catch (err) {
    return {
      error: "Network error calling OpenAI",
      code: "PROVIDER_ERROR",
      details: err instanceof Error ? err.message : "Unknown error",
    };
  }

  if (!response.ok) {
    const t = await response.text().catch(() => "");
    return {
      error: "OpenAI request failed",
      code: "PROVIDER_ERROR",
      details: `${response.status} ${response.statusText}${t ? `: ${t}` : ""}`,
    };
  }

  let data: any;
  try {
    data = await response.json();
  } catch (err) {
    return { error: "Invalid OpenAI response", code: "INVALID_RESPONSE", details: String(err) };
  }

  const content = data?.choices?.[0]?.message?.content;
  const text =
    typeof content === "string"
      ? content.trim()
      : Array.isArray(content)
        ? content
            .filter((p: any) => p?.type === "text")
            .map((p: any) => String(p.text ?? ""))
            .join(" ")
            .trim()
        : "";

  return { text };
}

async function callAnthropic(cfg: ResolvedChat, opts: ChatOptions): Promise<ChatResult | ChatError> {
  // Anthropic API uses `system` as a top-level field, not in messages
  const { system, rest } = splitSystem(opts.messages, opts.systemPrompt ?? DEFAULT_SYSTEM_PROMPT);

  // Anthropic only allows user/assistant roles in messages
  const messages = rest
    .filter((m) => m.role === "user" || m.role === "assistant")
    .map((m) => ({ role: m.role, content: m.content }));

  let response: Response;
  try {
    response = await fetch(`${cfg.baseUrl}/v1/messages`, {
      method: "POST",
      headers: {
        "x-api-key": cfg.apiKey,
        "anthropic-version": "2023-06-01",
        "content-type": "application/json",
      },
      body: JSON.stringify({
        model: cfg.model,
        max_tokens: opts.maxTokens ?? 512,
        temperature: opts.temperature ?? 0.7,
        system,
        messages,
      }),
    });
  } catch (err) {
    return {
      error: "Network error calling Anthropic",
      code: "PROVIDER_ERROR",
      details: err instanceof Error ? err.message : "Unknown error",
    };
  }

  if (!response.ok) {
    const t = await response.text().catch(() => "");
    return {
      error: "Anthropic request failed",
      code: "PROVIDER_ERROR",
      details: `${response.status} ${response.statusText}${t ? `: ${t}` : ""}`,
    };
  }

  let data: any;
  try {
    data = await response.json();
  } catch (err) {
    return { error: "Invalid Anthropic response", code: "INVALID_RESPONSE", details: String(err) };
  }

  // Response shape: { content: [{ type: "text", text: "..." }, ...] }
  const blocks: Array<{ type: string; text?: string }> = Array.isArray(data?.content) ? data.content : [];
  const text = blocks
    .filter((b) => b.type === "text" && typeof b.text === "string")
    .map((b) => b.text!)
    .join(" ")
    .trim();

  return { text };
}

export async function llmChat(opts: ChatOptions): Promise<ChatResult | ChatError> {
  const cfg = resolveChat(opts);
  if ("error" in cfg) return cfg;

  return cfg.provider === "anthropic" ? callAnthropic(cfg, opts) : callOpenAI(cfg, opts);
}
