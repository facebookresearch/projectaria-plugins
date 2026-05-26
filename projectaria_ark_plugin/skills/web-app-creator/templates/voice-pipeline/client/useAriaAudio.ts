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

import { useState, useEffect, useRef, useCallback } from "react";

export type AriaAudioFrame = {
  samples: string; // base64 float32
  num_samples: number;
  num_channels: number;
  sample_rate: number;
  dtype: string;
  level: number;
  peak: number;
};

export type ConnectionStatus = "disconnected" | "connecting" | "connected";

/**
 * Hook to connect to Aria WebSocket and receive raw audio frames.
 * Audio frames are delivered via a direct callback (bypasses React state)
 * to avoid dropping frames at ~50Hz.
 */
export function useAriaAudio(wsUrl = "ws://localhost:17300") {
  const [status, setStatus] = useState<ConnectionStatus>("disconnected");
  const [stats, setStats] = useState({ fps: 0, totalFrames: 0 });
  const wsRef = useRef<WebSocket | null>(null);
  const audioCallbackRef = useRef<((frame: AriaAudioFrame) => void) | null>(null);
  const reconnectTimeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const reconnectAttemptsRef = useRef(0);
  const fpsCounterRef = useRef({ count: 0, lastTime: Date.now() });
  const MAX_RECONNECT = 20;
  const BASE_DELAY = 2000;

  const registerAudioCallback = useCallback(
    (cb: (frame: AriaAudioFrame) => void) => {
      audioCallbackRef.current = cb;
    },
    []
  );

  const sendTTS = useCallback((text: string) => {
    if (wsRef.current && wsRef.current.readyState === WebSocket.OPEN) {
      wsRef.current.send(JSON.stringify({ type: "tts", text }));
      return true;
    }
    return false;
  }, []);

  const connect = useCallback(() => {
    try {
      setStatus("connecting");
      const ws = new WebSocket(wsUrl);

      ws.onopen = () => {
        setStatus("connected");
        reconnectAttemptsRef.current = 0;
        // Subscribe only to audio stream for performance
        ws.send(JSON.stringify({ type: "subscribe", streams: ["audio"] }));
      };

      ws.onmessage = (event) => {
        try {
          const msg = JSON.parse(event.data);
          if (msg.type === "audio" && msg.data) {
            // Direct callback — bypass React state for performance
            audioCallbackRef.current?.(msg.data as AriaAudioFrame);

            // Update stats (ok to batch/drop)
            const now = Date.now();
            fpsCounterRef.current.count++;
            if (now - fpsCounterRef.current.lastTime >= 1000) {
              const fps = fpsCounterRef.current.count;
              fpsCounterRef.current.count = 0;
              fpsCounterRef.current.lastTime = now;
              setStats((prev) => ({
                fps,
                totalFrames: prev.totalFrames + fps,
              }));
            }
          }
        } catch {
          // ignore parse errors
        }
      };

      ws.onerror = () => {
        // onclose handles reconnection
      };

      ws.onclose = () => {
        setStatus("disconnected");
        wsRef.current = null;
        const attempts = reconnectAttemptsRef.current;
        if (attempts < MAX_RECONNECT) {
          const delay = Math.min(BASE_DELAY * Math.pow(1.5, attempts), 30000);
          reconnectAttemptsRef.current = attempts + 1;
          reconnectTimeoutRef.current = setTimeout(connect, delay);
        }
      };

      wsRef.current = ws;
    } catch {
      const attempts = reconnectAttemptsRef.current;
      if (attempts < MAX_RECONNECT) {
        const delay = Math.min(BASE_DELAY * Math.pow(1.5, attempts), 30000);
        reconnectAttemptsRef.current = attempts + 1;
        reconnectTimeoutRef.current = setTimeout(connect, delay);
      }
    }
  }, [wsUrl]);

  useEffect(() => {
    connect();
    return () => {
      if (reconnectTimeoutRef.current) clearTimeout(reconnectTimeoutRef.current);
      if (wsRef.current) wsRef.current.close();
    };
  }, [connect]);

  return { status, stats, registerAudioCallback, sendTTS };
}
