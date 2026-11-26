import { expect, test } from '@playwright/test';

test('customer-web renders the app-name placeholder', async ({ page }) => {
  await page.goto('/');

  await expect(page.locator('#app-name')).toHaveText('customer-web');
});
