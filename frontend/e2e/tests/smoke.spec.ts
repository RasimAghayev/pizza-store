import { expect, test } from '@playwright/test';

test('customer-web renders its app name in the toolbar', async ({ page }) => {
  await page.goto('/');

  await expect(page.getByRole('banner')).toContainText('customer-web');
});
