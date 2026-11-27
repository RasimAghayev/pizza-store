import AxeBuilder from '@axe-core/playwright';
import { expect, test } from '@playwright/test';

// Scoped to exactly the WCAG success-criteria levels this repo targets (2.0/2.1/2.2, A+AA) --
// axe-core's "best-practice" tag (which includes the "region" landmark rule) is deliberately
// excluded: the skip link in shared/src/lib/app-shell/app-shell.html is intentionally placed
// outside any landmark, per the standard skip-link pattern, which "region" would flag.
const WCAG_AA_TAGS = ['wcag2a', 'wcag2aa', 'wcag21a', 'wcag21aa', 'wcag22aa'];

test('the login page has no WCAG 2.2 AA violations', async ({ page }) => {
  await page.goto('/login');

  const results = await new AxeBuilder({ page }).withTags(WCAG_AA_TAGS).analyze();

  expect(results.violations).toEqual([]);
});
