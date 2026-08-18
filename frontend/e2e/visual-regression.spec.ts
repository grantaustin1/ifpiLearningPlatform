import { test, expect } from '@playwright/test'

/**
 * Minimal visual-regression smoke tests.
 *
 * Baseline snapshots live in e2e/__snapshots__.
 * Update baselines:  npx playwright test --update-snapshots
 */

test.describe('Landing page', () => {
  test('matches baseline', async ({ page }) => {
    await page.goto('/')
    await expect(page).toHaveScreenshot('landing-page.png', {
      fullPage: true,
      maxDiffPixels: 100,
    })
  })
})

test.describe('Login page', () => {
  test('matches baseline', async ({ page }) => {
    await page.goto('/login')
    await expect(page).toHaveScreenshot('login-page.png', {
      maxDiffPixels: 100,
    })
  })
})
