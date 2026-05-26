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
 * Express server example wiring transcribeAudio + llmChat into HTTP routes.
 *
 * Routes:
 *   POST /api/voice/transcribe   multipart/form-data { file: <audio blob>, language? }
 *   POST /api/voice/chat         application/json    { messages: ChatMessage[] }
 *
 * Run:
 *   pnpm add express multer
 *   pnpm add -D @types/express @types/multer tsx
 *   OPENAI_API_KEY=sk-... ANTHROPIC_API_KEY=sk-ant-... \
 *     pnpm tsx examples/express-server.ts
 *
 * Required env (any one):
 *   STT_API_KEY  | OPENAI_API_KEY  | BUILT_IN_FORGE_API_KEY     (for transcribe)
 *   LLM_API_KEY  | OPENAI_API_KEY  | ANTHROPIC_API_KEY          (for chat)
 */

import express from "express";
import multer from "multer";
import { transcribeAudio, llmChat } from "../server";

const upload = multer({
  storage: multer.memoryStorage(),
  limits: { fileSize: 16 * 1024 * 1024 }, // 16 MB
});

const app = express();
app.use(express.json({ limit: "20mb" }));

app.post("/api/voice/transcribe", upload.single("file"), async (req, res) => {
  if (!req.file) return res.status(400).json({ error: "Missing 'file' field (multipart/form-data)" });

  const result = await transcribeAudio({
    audioBuffer: req.file.buffer,
    mimeType: req.file.mimetype,
    filename: req.file.originalname,
    language: typeof req.body?.language === "string" ? req.body.language : undefined,
  });

  if ("error" in result) {
    const status = result.code === "MISSING_API_KEY" ? 503 : 500;
    return res.status(status).json(result);
  }
  res.json(result);
});

app.post("/api/voice/chat", async (req, res) => {
  const messages = req.body?.messages;
  if (!Array.isArray(messages)) return res.status(400).json({ error: "Body must be { messages: ChatMessage[] }" });

  const result = await llmChat({ messages });
  if ("error" in result) {
    const status = result.code === "MISSING_API_KEY" ? 503 : 500;
    return res.status(status).json(result);
  }
  res.json(result);
});

const port = Number(process.env.PORT ?? 8000);
app.listen(port, () => {
  console.log(`✅ Voice pipeline server listening on http://localhost:${port}`);
  console.log(`   POST /api/voice/transcribe   (multipart 'file' + optional 'language')`);
  console.log(`   POST /api/voice/chat         { messages: [{ role, content }] }`);
});
