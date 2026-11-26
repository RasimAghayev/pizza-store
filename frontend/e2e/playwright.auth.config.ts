import { defineConfig, devices } from '@playwright/test';

// Separate from playwright.config.ts on purpose: these tests exercise the real login flow
// against the real backend, so they need the full Docker Compose stack (nginx edge +
// frontend + backend + postgres, per Issue #140's same-origin routing) already running --
// unlike playwright.config.ts's smoke test, there is no `webServer` entry here to start one.
// See frontend/README.md's "Auth-flow E2E tests" section for how to bring the stack up first
// and seed the fixture user these tests log in as.
export default defineConfig({
  testDir: './tests',
  testMatch: 'auth-flow.spec.ts',
  fullyParallel: false,
  reporter: 'list',
  use: {
    baseURL: process.env.E2E_AUTH_BASE_URL ?? 'http://localhost',
    trace: 'on-first-retry',
  },
  projects: [
    {
      name: 'chromium',
      use: { ...devices['Desktop Chrome'] },
    },
  ],
});
