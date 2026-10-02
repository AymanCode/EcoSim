import { defineConfig, devices } from '@playwright/test'

// The no-shift test runs against its own Vite dev server (Node 22, port 4179)
// and the recorded demo at /?view=next&demo; no backend is needed.
export default defineConfig({
  testDir: './e2e',
  timeout: 300_000,
  fullyParallel: false,
  workers: 1,
  reporter: [['list']],
  use: { ...devices['Desktop Chrome'], baseURL: 'http://localhost:4179' },
  webServer: {
    command: 'npx --yes node@22 node_modules/.bin/vite --port 4179 --strictPort',
    url: 'http://localhost:4179',
    reuseExistingServer: false,
    timeout: 120_000,
  },
})
