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
 * ⚠️ MANUS-SPECIFIC EXAMPLE
 *
 * This is the original Manus / Forge router preserved verbatim for users on
 * existing Manus deployments. It depends on Manus framework files
 * (`@shared/const`, `_core/trpc`, `_core/llm`, `_core/voiceTranscription`,
 * `storage`, etc.) that DO NOT exist in this template.
 *
 * For platform-agnostic usage, see:
 *   - server/transcribeAudio.ts
 *   - server/llmChat.ts
 *   - examples/express-server.ts
 */
import { COOKIE_NAME } from "@shared/const";
import { getSessionCookieOptions } from "./_core/cookies";
import { systemRouter } from "./_core/systemRouter";
import { publicProcedure, router } from "./_core/trpc";
import { transcribeAudio } from "./_core/voiceTranscription";
import { invokeLLM } from "./_core/llm";
import { storagePut } from "./storage";
import { TRPCError } from "@trpc/server";
import { z } from "zod";
import { nanoid } from "nanoid";

const SYSTEM_PROMPT = `You are a helpful voice assistant running on Meta Aria smart glasses. 
Keep responses concise and conversational — they will be spoken aloud via TTS.
Aim for 1-3 sentences. Avoid markdown, bullet points, or formatting.
Be natural, friendly, and direct.
You MUST always respond in English, regardless of the language the user speaks in.
If the user speaks in another language, understand their message but always reply in English.`;

// ── Whisper hallucination filter ──
// Whisper is known to hallucinate common phrases (especially YouTube-style
// call-to-action text) when processing near-silent or very short audio clips.
// See: https://huggingface.co/datasets/sachaarbonel/whisper-hallucinations
const HALLUCINATION_EXACT_PHRASES = new Set([
  "thanks for watching",
  "thank you for watching",
  "thank you for watching and see you in the next video",
  "thanks for watching and see you in the next video",
  "thank you for watching and i'll see you in the next one",
  "see you next time",
  "see you in the next video",
  "see you in the next one",
  "bye",
  "bye bye",
  "goodbye",
  "you",
  "thank you",
  "thanks",
  "please subscribe",
  "subscribe",
  "like and subscribe",
  "please like and subscribe",
  "please like subscribe and share",
  "click the bell",
  "click the bell icon",
  "leave a comment",
  "please leave a comment",
  "please leave a comment in the section below",
  "please see the description",
  "check the description",
  "link in the description",
  "links in the description",
  "thumbs up",
  "click the thumbs up",
  "click the thumbs-up and subscribe",
  "please use headphones or earphones",
  "turn on the subscription",
  "please turn on the subscription",
  "please turn on the subscription like and alarm settings",
  "please post them in the comments",
  "if you like this video",
  "if you like this video please click the thumbs-up and subscribe",
  "further details and more at",
  "bell icon",
  "notified when a new video is uploaded",
  "thank you for your support",
  "please see review",
  "the user's voice from aria glasses microphone",
  "please read the user's voice from aria glasses microphone",
  "read the user's voice from aria glasses microphone",
  "the user's working language is english",
  "transcribe the user's voice to text",
  "the user's working language is",
  "subscribe the user's voice to text",
  "please see the video description for a link to the translation",
  "please see the video description",
  "and apply it the correct way",
  "he doesn't want to talk to you",
  "i'll see you in the next video",
  "don't forget to subscribe",
  "hit the like button",
  "hit the bell icon",
  "share this video",
  "comment below",
  "let me know in the comments",
  "what do you think",
  "drop a like",
  "smash the like button",
  "ring the bell",
  "turn on notifications",
  "new video",
  "next video",
  "fin",
  "the end",
  "end",
  "so",
  "okay",
  "um",
  "uh",
  "hmm",
  "ah",
  "oh",
]);

// Keywords that strongly indicate a YouTube-style hallucination
const HALLUCINATION_KEYWORDS = [
  "subscribe",
  "subscription",
  "unsubscribe",
  "thumbs up",
  "thumbs-up",
  "bell icon",
  "notification",
  "like and share",
  "comment section",
  "comment below",
  "description below",
  "link in the description",
  "thanks for watching",
  "thank you for watching",
  "see you in the next",
  "see you next time",
  "don't forget to",
  "smash the like",
  "hit the like",
  "drop a like",
  "ring the bell",
  "new video is uploaded",
  "please use headphones",
  "please see the description",
  "aria glasses microphone",
  "working language",
  "transcribe the user",
  "subscribe the user",
  "video description",
  "link to the translation",
  "further details and more at",
];

/**
 * Check if a transcription is likely a Whisper hallucination.
 * Returns true if the text should be rejected.
 */
function isHallucination(text: string): boolean {
  const normalized = text.toLowerCase().trim().replace(/[.,!?;:'"]+$/g, "").trim();

  // Exact match against known hallucination phrases
  if (HALLUCINATION_EXACT_PHRASES.has(normalized)) {
    console.log(`[Hallucination Filter] EXACT MATCH rejected: "${text}"`);
    return true;
  }

  // Keyword-based detection
  const lowerText = normalized;
  for (const keyword of HALLUCINATION_KEYWORDS) {
    if (lowerText.includes(keyword)) {
      console.log(`[Hallucination Filter] KEYWORD "${keyword}" rejected: "${text}"`);
      return true;
    }
  }

  // Very short single-word transcriptions are often noise
  const wordCount = normalized.split(/\s+/).filter(w => w.length > 0).length;
  if (wordCount <= 1 && normalized.length < 10) {
    console.log(`[Hallucination Filter] TOO SHORT rejected: "${text}" (${wordCount} words)`);
    return true;
  }

  // Repetitive text detection (e.g., "so so so so")
  const words = normalized.split(/\s+/);
  if (words.length >= 3) {
    const uniqueWords = new Set(words);
    if (uniqueWords.size === 1) {
      console.log(`[Hallucination Filter] REPETITIVE rejected: "${text}"`);
      return true;
    }
  }

  return false;
}

export const appRouter = router({
  system: systemRouter,
  auth: router({
    me: publicProcedure.query((opts) => opts.ctx.user),
    logout: publicProcedure.mutation(({ ctx }) => {
      const cookieOptions = getSessionCookieOptions(ctx.req);
      ctx.res.clearCookie(COOKIE_NAME, { ...cookieOptions, maxAge: -1 });
      return { success: true } as const;
    }),
  }),

  voice: router({
    /**
     * Transcribe audio: receives base64-encoded WAV data,
     * uploads to S3, then calls Whisper API for transcription.
     * Includes hallucination filtering to reject known false positives.
     */
    transcribe: publicProcedure
      .input(
        z.object({
          audioBase64: z.string(),
          language: z.string().optional().default("en"),
        })
      )
      .mutation(async ({ input }) => {
        const audioBuffer = Buffer.from(input.audioBase64, "base64");

        const sizeMB = audioBuffer.length / (1024 * 1024);
        if (sizeMB > 16) {
          throw new TRPCError({
            code: "PAYLOAD_TOO_LARGE",
            message: `Audio file is ${sizeMB.toFixed(1)}MB, max 16MB`,
          });
        }

        const fileKey = `aria-voice/clips/${nanoid()}.wav`;
        let audioUrl: string;
        try {
          const result = await storagePut(fileKey, audioBuffer, "audio/wav");
          audioUrl = result.url;
        } catch (error) {
          throw new TRPCError({
            code: "INTERNAL_SERVER_ERROR",
            message: "Failed to upload audio to storage",
            cause: error,
          });
        }

        const result = await transcribeAudio({
          audioUrl,
          language: input.language,
          // No prompt hint — Whisper hallucinates prompt text on near-silent clips
        });

        if ("error" in result) {
          throw new TRPCError({
            code: "INTERNAL_SERVER_ERROR",
            message: result.error,
            cause: result,
          });
        }

        const text = result.text?.trim() || "";

        // Check for Whisper hallucinations
        if (text && isHallucination(text)) {
          return {
            text: "",
            language: result.language || "en",
            duration: result.duration || 0,
            segments: [],
            filtered: true,
            filterReason: "hallucination",
          };
        }

        return {
          text,
          language: result.language || "en",
          duration: result.duration || 0,
          segments:
            result.segments?.map((s) => ({
              start: s.start,
              end: s.end,
              text: s.text,
            })) || [],
          filtered: false,
          filterReason: null as string | null,
        };
      }),

    /**
     * Chat with LLM: sends conversation history and returns a concise response
     * suitable for TTS playback on Aria glasses.
     */
    chat: publicProcedure
      .input(
        z.object({
          messages: z.array(
            z.object({
              role: z.enum(["user", "assistant"]),
              content: z.string(),
            })
          ),
        })
      )
      .mutation(async ({ input }) => {
        try {
          const llmMessages = [
            { role: "system" as const, content: SYSTEM_PROMPT },
            ...input.messages.map((m) => ({
              role: m.role as "user" | "assistant",
              content: m.content,
            })),
          ];

          const result = await invokeLLM({ messages: llmMessages });

          const content = result.choices?.[0]?.message?.content;
          const text =
            typeof content === "string"
              ? content.trim()
              : Array.isArray(content)
                ? content
                    .filter((p) => p.type === "text")
                    .map((p) => (p as { type: "text"; text: string }).text)
                    .join(" ")
                    .trim()
                : "";

          return { text };
        } catch (error) {
          throw new TRPCError({
            code: "INTERNAL_SERVER_ERROR",
            message:
              error instanceof Error
                ? error.message
                : "LLM request failed",
          });
        }
      }),
  }),
});

export type AppRouter = typeof appRouter;
