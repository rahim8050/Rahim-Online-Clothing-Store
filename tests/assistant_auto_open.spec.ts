// Minimal Playwright test to ensure assistant panel does not auto-open
// Run with: npx playwright test tests/assistant_auto_open.spec.ts

import { test, expect } from '@playwright/test'

test('assistant stays closed on page load', async ({ page }) => {
  await page.goto('http://localhost:8000/')

  // Bubble is visible
  const bubble = page.locator('#rahim-assistant-mount')
  await expect(bubble).toBeVisible()

  // Vue panel (ChatPanel) should not be visible when closed
  // We only assert that no element with role-badge is present (from header) or panel is hidden
  const panelHeader = page.locator('.panel .header')
  await expect(panelHeader).toHaveCount(0)

  // Legacy DOM assistant panel remains hidden by default if present
  const legacyPanel = page.locator('#assistant-panel')
  if (await legacyPanel.count()) {
    await expect(legacyPanel).toHaveClass(/hidden/)
  }
})

