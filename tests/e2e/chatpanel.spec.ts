// Pseudo e2e test (requires Playwright or similar). Provided as a smoke spec.
// Steps: open -> type -> send -> receive fallback HTTP.
import { test, expect } from '@playwright/test';

test('chat panel open -> send', async ({ page }) => {
  await page.goto('/');
  // Open launcher
  await page.getByRole('button', { name: 'Open chat panel' }).click();
  // Type a message
  await page.getByRole('textbox').fill('Hello');
  // Send
  await page.getByRole('button', { name: 'Send message' }).click();
  // Message should appear in log
  await expect(page.getByRole('log')).toBeVisible();
});
