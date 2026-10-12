import { defineConfig } from "@playwright/test";

// Own ports, so a dev server already running on :8000 / :5173 (possibly older code) is never reused.
const API = 8010, UI = 5180;

export default defineConfig({
  testDir: "e2e",
  timeout: 60_000,
  use: { baseURL: `http://localhost:${UI}`, viewport: { width: 1366, height: 768 } },
  webServer: [
    { command: `cd .. && uv run uvicorn api.main:app --port ${API}`, port: API, reuseExistingServer: false, timeout: 60_000 },
    { command: `API_PORT=${API} npx vite --port ${UI} --strictPort`, port: UI, reuseExistingServer: false },
  ],
});
