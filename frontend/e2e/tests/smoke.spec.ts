import { expect, test } from '@playwright/test';

test('smoke-app renders the status element', async ({ page }) => {
  await page.goto('/');

  await expect(page.locator('#status')).toHaveText('ok');
});
