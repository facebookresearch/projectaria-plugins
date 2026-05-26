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
 * Whisper hallucination filter.
 *
 * OpenAI Whisper is known to hallucinate common phrases (especially YouTube
 * call-to-action text and prompt-template echo) when processing near-silent
 * or very short audio clips.
 *
 * Reference dataset: https://huggingface.co/datasets/sachaarbonel/whisper-hallucinations
 *
 * Pure function, zero dependencies — works in any JS runtime (Node / browser /
 * edge). Keeps the same logic that the original Manus router used.
 */

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

export type HallucinationCheck =
  | { isHallucination: false }
  | { isHallucination: true; reason: "exact" | "keyword" | "too_short" | "repetitive"; matched?: string };

/**
 * Classify a transcription string as legitimate vs likely hallucination.
 *
 * @param text Raw text returned by Whisper
 * @returns A discriminated union explaining the verdict.
 */
export function classifyTranscription(text: string): HallucinationCheck {
  const normalized = text.toLowerCase().trim().replace(/[.,!?;:'"]+$/g, "").trim();

  if (HALLUCINATION_EXACT_PHRASES.has(normalized)) {
    return { isHallucination: true, reason: "exact", matched: normalized };
  }

  for (const keyword of HALLUCINATION_KEYWORDS) {
    if (normalized.includes(keyword)) {
      return { isHallucination: true, reason: "keyword", matched: keyword };
    }
  }

  // Single-word noise (e.g. "you", "so") — short and one word
  const words = normalized.split(/\s+/).filter((w) => w.length > 0);
  if (words.length <= 1 && normalized.length < 10) {
    return { isHallucination: true, reason: "too_short" };
  }

  // Repetitive text (e.g. "so so so so")
  if (words.length >= 3 && new Set(words).size === 1) {
    return { isHallucination: true, reason: "repetitive" };
  }

  return { isHallucination: false };
}

/** Convenience boolean wrapper. */
export function isHallucination(text: string): boolean {
  return classifyTranscription(text).isHallucination;
}
