import { expect, test } from '@playwright/test';

// Must match the fixture user seeded by .github/workflows/integration-validation.yml's
// `backend-frontend-integration` job (or frontend/README.md's local equivalent) via
// RegistrationService -- see that service for why a shell-seeded user is used instead of a
// real registration endpoint (none exists yet, Issue #141).
const FIXTURE_EMAIL = 'e2e-auth@example.com';
const FIXTURE_PASSWORD = 'correct-horse-battery-staple';

test('a user can log in with valid credentials and reach the dashboard', async ({ page }) => {
  await page.goto('/login');

  await page.getByLabel('Email').fill(FIXTURE_EMAIL);
  await page.getByLabel('Password').fill(FIXTURE_PASSWORD);
  await page.getByRole('button', { name: 'Log in' }).click();

  await expect(page).toHaveURL(/\/dashboard$/);
  await expect(page.getByRole('heading', { name: 'Dashboard' })).toBeVisible();
});

test('invalid credentials show the backend error message and do not navigate', async ({ page }) => {
  await page.goto('/login');

  await page.getByLabel('Email').fill(FIXTURE_EMAIL);
  await page.getByLabel('Password').fill('wrong-password');
  await page.getByRole('button', { name: 'Log in' }).click();

  await expect(page.getByRole('alert')).toContainText('Invalid email or password.');
  await expect(page).toHaveURL(/\/login$/);
});

test('logging out actually revokes the session server-side, not just client-side', async ({
  page,
}) => {
  // DashboardPlaceholder.logout() navigates to /login on both success AND error (see its
  // own comment -- there is no "stay logged in" outcome to preserve on a network failure),
  // so the URL alone can't prove the backend call succeeded: asserting the real response
  // status is the only way to catch a server-side failure here. This is the regression
  // test for a real bug (Issue #154) where the refresh_token cookie's Path
  // excluded /auth/logout/, so a real browser withheld it on logout and the backend
  // rejected every real logout with 403, even though logout "worked" from the UI's
  // perspective and django.test.Client-based backend tests never noticed (it ignores
  // cookie Path scoping entirely, unlike a real browser).
  await page.goto('/login');
  await page.getByLabel('Email').fill(FIXTURE_EMAIL);
  await page.getByLabel('Password').fill(FIXTURE_PASSWORD);
  await page.getByRole('button', { name: 'Log in' }).click();
  await expect(page).toHaveURL(/\/dashboard$/);

  const [logoutResponse] = await Promise.all([
    page.waitForResponse((r) => r.url().includes('/api/v1/auth/logout/')),
    page.getByRole('button', { name: 'Log out' }).click(),
  ]);

  expect(logoutResponse.status()).toBe(200);
  await expect(page).toHaveURL(/\/login$/);
});
