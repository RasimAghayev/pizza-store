import { defineConfig, devices } from '@playwright/test';

// Serves the throwaway smoke-app (Task #109) and runs a real browser-context
// assertion against it. Phase 7 (Epic #11) points this webServer/baseURL at the
// real customer-web app once it exists; this config itself is kept, not thrown away.
export default defineConfig({
  testDir: './tests',
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
    command: 'npx ng serve smoke-app --port 4300',
    url: 'http://localhost:4300',
    cwd: '..',
    reuseExistingServer: !process.env.CI,
    timeout: 120_000,
  },
});
