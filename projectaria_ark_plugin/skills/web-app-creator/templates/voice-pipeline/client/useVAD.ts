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

import { useRef, useState, useCallback } from "react";
import type { AriaAudioFrame } from "./useAriaAudio";

// ── VAD parameters ──
export type VADConfig = {
  speechStartThreshold: number;
  silenceThreshold: number;
  minSpeechDuration: number;
  baseSilenceDuration: number;
  maxSilenceDuration: number;
  longSpeechThreshold: number;
  dynamicScalingFactor: number;
  maxUtteranceDuration: number;
  preSpeechBuffer: number;
};

export const DEFAULT_VAD_CONFIG: VADConfig = {
  speechStartThreshold: 0.040,
  silenceThreshold: 0.012,
  minSpeechDuration: 0.35,
  baseSilenceDuration: 1.0,
  maxSilenceDuration: 2.0,
  longSpeechThreshold: 5.0,
  dynamicScalingFactor: 0.2,
  maxUtteranceDuration: 30,
  preSpeechBuffer: 0.3,
};

export type VADState = "idle" | "listening" | "processing";

export type VADDebugInfo = {
  rawRMS: number;
  computedRMS: number;
  frameLevel: number;
  framePeak: number;
  silenceTimer: number;
  silenceTimeout: number;
  speechDuration: number;
  isBelowSilence: boolean;
  sampleRate: number;
  numSamples: number;
  frameDuration: number;
};

type CapturedClip = {
  samples: Float32Array;
  sampleRate: number;
  duration: number;
};

/**
 * Voice Activity Detection hook.
 *
 * Uses RAW per-frame RMS for speech/silence detection (no smoothing).
 * Exposes debug info for diagnosing threshold issues.
 */
export function useVAD(
  config: VADConfig = DEFAULT_VAD_CONFIG,
  onClipCaptured: (clip: CapturedClip) => void
) {
  const [state, setState] = useState<VADState>("idle");
  const [currentRMS, setCurrentRMS] = useState(0);
  const [debugInfo, setDebugInfo] = useState<VADDebugInfo | null>(null);

  // Internal refs
  const stateRef = useRef<VADState>("idle");
  const silenceTimerRef = useRef(0);
  const recordingStartTimeRef = useRef(0);
  const sampleRateRef = useRef(48000);

  // Audio buffer for current recording
  const audioBufferRef = useRef<Float32Array[]>([]);
  const audioBufferSamplesRef = useRef(0);

  // Pre-speech ring buffer
  const preSpeechRingRef = useRef<Float32Array[]>([]);
  const preSpeechSamplesRef = useRef(0);

  // Throttle UI updates
  const lastUIUpdateRef = useRef(0);
  // Throttle debug logs (log every 500ms, not every frame)
  const lastDebugLogRef = useRef(0);

  const configRef = useRef(config);
  configRef.current = config;

  const onClipRef = useRef(onClipCaptured);
  onClipRef.current = onClipCaptured;

  const getDynamicSilenceDuration = useCallback(
    (speechDuration: number): number => {
      const c = configRef.current;
      if (speechDuration < c.longSpeechThreshold) {
        return c.baseSilenceDuration;
      }
      const extra = speechDuration - c.longSpeechThreshold;
      const dynamic = c.baseSilenceDuration + extra * c.dynamicScalingFactor;
      return Math.min(dynamic, c.maxSilenceDuration);
    },
    []
  );

  const computeRMS = useCallback((samples: Float32Array): number => {
    let sum = 0;
    for (let i = 0; i < samples.length; i++) {
      sum += samples[i] * samples[i];
    }
    return Math.sqrt(sum / Math.max(samples.length, 1));
  }, []);

  const decodeFrame = useCallback((frame: AriaAudioFrame): Float32Array => {
    const binaryStr = atob(frame.samples);
    const bytes = new Uint8Array(binaryStr.length);
    for (let i = 0; i < binaryStr.length; i++) {
      bytes[i] = binaryStr.charCodeAt(i);
    }
    return new Float32Array(bytes.buffer);
  }, []);

  const flattenBuffer = useCallback(
    (chunks: Float32Array[], totalSamples: number): Float32Array => {
      const result = new Float32Array(totalSamples);
      let offset = 0;
      for (const chunk of chunks) {
        result.set(chunk, offset);
        offset += chunk.length;
      }
      return result;
    },
    []
  );

  const encodeWAV = useCallback(
    (samples: Float32Array, sampleRate: number): Blob => {
      const numChannels = 1;
      const bitsPerSample = 16;
      const byteRate = (sampleRate * numChannels * bitsPerSample) / 8;
      const blockAlign = (numChannels * bitsPerSample) / 8;
      const dataSize = samples.length * blockAlign;
      const buffer = new ArrayBuffer(44 + dataSize);
      const view = new DataView(buffer);

      writeString(view, 0, "RIFF");
      view.setUint32(4, 36 + dataSize, true);
      writeString(view, 8, "WAVE");
      writeString(view, 12, "fmt ");
      view.setUint32(16, 16, true);
      view.setUint16(20, 1, true);
      view.setUint16(22, numChannels, true);
      view.setUint32(24, sampleRate, true);
      view.setUint32(28, byteRate, true);
      view.setUint16(32, blockAlign, true);
      view.setUint16(34, bitsPerSample, true);
      writeString(view, 36, "data");
      view.setUint32(40, dataSize, true);

      let offset = 44;
      for (let i = 0; i < samples.length; i++) {
        const s = Math.max(-1, Math.min(1, samples[i]));
        const val = s < 0 ? s * 0x8000 : s * 0x7fff;
        view.setInt16(offset, val, true);
        offset += 2;
      }

      return new Blob([buffer], { type: "audio/wav" });
    },
    []
  );

  const processFrame = useCallback(
    (frame: AriaAudioFrame) => {
      const c = configRef.current;
      const samples = decodeFrame(frame);
      sampleRateRef.current = frame.sample_rate || 48000;
      const frameDuration = samples.length / sampleRateRef.current;

      // Compute our own RMS from the decoded samples
      const computedRMS = computeRMS(samples);

      // Use our computed RMS for VAD decisions (not frame.level which may have different scaling)
      const rawRMS = computedRMS;

      const now = performance.now();
      const currentState = stateRef.current;

      // Build debug info
      const speechDuration =
        currentState === "listening"
          ? now / 1000 - recordingStartTimeRef.current
          : 0;
      const silenceTimeout =
        currentState === "listening"
          ? getDynamicSilenceDuration(speechDuration)
          : c.baseSilenceDuration;
      const isBelowSilence = rawRMS < c.silenceThreshold;

      const debug: VADDebugInfo = {
        rawRMS,
        computedRMS,
        frameLevel: frame.level,
        framePeak: frame.peak,
        silenceTimer: silenceTimerRef.current,
        silenceTimeout,
        speechDuration,
        isBelowSilence,
        sampleRate: sampleRateRef.current,
        numSamples: samples.length,
        frameDuration,
      };

      // Throttled debug logging to console (every 500ms)
      if (now - lastDebugLogRef.current > 500) {
        lastDebugLogRef.current = now;
        if (currentState === "listening") {
          console.log(
            `[VAD:${currentState}] computedRMS=${computedRMS.toFixed(6)} frameLevel=${frame.level?.toFixed(6)} ` +
            `belowSilence=${isBelowSilence} silenceTimer=${silenceTimerRef.current.toFixed(3)}/${silenceTimeout.toFixed(1)}s ` +
            `speechDur=${speechDuration.toFixed(1)}s threshold=${c.silenceThreshold} ` +
            `sampleRate=${sampleRateRef.current} numSamples=${samples.length}`
          );
        } else {
          console.log(
            `[VAD:${currentState}] computedRMS=${computedRMS.toFixed(6)} frameLevel=${frame.level?.toFixed(6)} ` +
            `startThreshold=${c.speechStartThreshold} aboveStart=${rawRMS > c.speechStartThreshold}`
          );
        }
      }

      // Throttled UI update (~10Hz)
      if (now - lastUIUpdateRef.current > 100) {
        lastUIUpdateRef.current = now;
        setCurrentRMS(rawRMS);
        setDebugInfo(debug);
      }

      if (currentState === "idle") {
        // Maintain pre-speech ring buffer
        preSpeechRingRef.current.push(samples);
        preSpeechSamplesRef.current += samples.length;
        const maxPreSpeechSamples = Math.ceil(
          c.preSpeechBuffer * sampleRateRef.current
        );
        while (
          preSpeechSamplesRef.current > maxPreSpeechSamples &&
          preSpeechRingRef.current.length > 0
        ) {
          const removed = preSpeechRingRef.current.shift()!;
          preSpeechSamplesRef.current -= removed.length;
        }

        if (rawRMS > c.speechStartThreshold) {
          console.log(
            `[VAD] >>> SPEECH START detected! RMS=${rawRMS.toFixed(6)} > threshold=${c.speechStartThreshold}`
          );
          audioBufferRef.current = [...preSpeechRingRef.current, samples];
          audioBufferSamplesRef.current =
            preSpeechSamplesRef.current + samples.length;
          preSpeechRingRef.current = [];
          preSpeechSamplesRef.current = 0;
          silenceTimerRef.current = 0;
          recordingStartTimeRef.current = now / 1000;
          stateRef.current = "listening";
          setState("listening");
        }
      } else if (currentState === "listening") {
        audioBufferRef.current.push(samples);
        audioBufferSamplesRef.current += samples.length;

        const maxSamples = c.maxUtteranceDuration * sampleRateRef.current;
        if (audioBufferSamplesRef.current > maxSamples) {
          while (
            audioBufferSamplesRef.current > maxSamples &&
            audioBufferRef.current.length > 1
          ) {
            const removed = audioBufferRef.current.shift()!;
            audioBufferSamplesRef.current -= removed.length;
          }
        }

        const curSpeechDuration = now / 1000 - recordingStartTimeRef.current;

        if (rawRMS < c.silenceThreshold) {
          silenceTimerRef.current += frameDuration;
          const curSilenceTimeout = getDynamicSilenceDuration(curSpeechDuration);

          if (silenceTimerRef.current >= curSilenceTimeout) {
            console.log(
              `[VAD] >>> SILENCE TIMEOUT reached! silenceTimer=${silenceTimerRef.current.toFixed(3)}s >= timeout=${curSilenceTimeout.toFixed(1)}s, speechDur=${curSpeechDuration.toFixed(1)}s`
            );
            if (curSpeechDuration >= c.minSpeechDuration) {
              console.log(
                `[VAD] >>> CLIP CAPTURED! duration=${curSpeechDuration.toFixed(2)}s, samples=${audioBufferSamplesRef.current}`
              );
              stateRef.current = "processing";
              setState("processing");

              const allSamples = flattenBuffer(
                audioBufferRef.current,
                audioBufferSamplesRef.current
              );
              const clip: CapturedClip = {
                samples: allSamples,
                sampleRate: sampleRateRef.current,
                duration: curSpeechDuration,
              };

              audioBufferRef.current = [];
              audioBufferSamplesRef.current = 0;

              onClipRef.current(clip);
            } else {
              console.log(
                `[VAD] >>> DISCARDED (too short): duration=${curSpeechDuration.toFixed(2)}s < min=${c.minSpeechDuration}s`
              );
              audioBufferRef.current = [];
              audioBufferSamplesRef.current = 0;
              stateRef.current = "idle";
              setState("idle");
            }
          }
        } else {
          // Speech continues — reset silence timer
          if (silenceTimerRef.current > 0.1) {
            // Log when silence timer resets after accumulating some time
            console.log(
              `[VAD] silence timer RESET (was ${silenceTimerRef.current.toFixed(3)}s) — RMS=${rawRMS.toFixed(6)} >= silenceThreshold=${c.silenceThreshold}`
            );
          }
          silenceTimerRef.current = 0;
        }
      }
    },
    [decodeFrame, computeRMS, getDynamicSilenceDuration, flattenBuffer]
  );

  const resetToIdle = useCallback(() => {
    console.log("[VAD] >>> RESET TO IDLE");
    stateRef.current = "idle";
    setState("idle");
    silenceTimerRef.current = 0;
    audioBufferRef.current = [];
    audioBufferSamplesRef.current = 0;
  }, []);

  return {
    state,
    currentRMS,
    debugInfo,
    processFrame,
    resetToIdle,
    encodeWAV,
  };
}

function writeString(view: DataView, offset: number, str: string) {
  for (let i = 0; i < str.length; i++) {
    view.setUint8(offset + i, str.charCodeAt(i));
  }
}
