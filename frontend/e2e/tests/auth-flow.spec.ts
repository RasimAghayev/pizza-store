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
