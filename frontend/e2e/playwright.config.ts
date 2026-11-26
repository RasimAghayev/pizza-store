import { defineConfig, devices } from '@playwright/test';

// Serves the real customer-web app (Issue #138 replaced the throwaway smoke-app from
// Task #109) and runs a real browser-context assertion against it.
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
    command: 'npx ng serve customer-web --port 4300',
    url: 'http://localhost:4300',
    cwd: '..',
    reuseExistingServer: !process.env.CI,
    timeout: 120_000,
  },
});
