import { defineConfig, devices } from '@playwright/test';

// Serves the real customer-web app (Issue #138 replaced the throwaway smoke-app from
// Task #109) and runs a real browser-context assertion against it.
export default defineConfig({
  testDir: './tests',
  // auth-flow.spec.ts needs the real backend through the full Compose stack (see
  // playwright.auth.config.ts) -- this config's webServer is `ng serve` only, so exclude it
  // here or it fails against a frontend with nothing behind it.
  testIgnore: 'auth-flow.spec.ts',
  fullyParallel: true,
  reporter: 'list',
  use: {
    baseURL: 'http://localhost:4300',
    trace: 'on-first-retry',
  },
  projects: [
    {
      name: 'chromium',
      use: { ...devices['Desktop Chrome'] },
    },
  ],
  webServer: {
    command: 'npx ng serve customer-web --port 4300',
    url: 'http://localhost:4300',
    cwd: '..',
    reuseExistingServer: !process.env.CI,
    timeout: 120_000,
  },
});
