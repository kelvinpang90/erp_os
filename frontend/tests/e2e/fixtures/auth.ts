/**
 * UI login helper. Drives the real LoginPage so auth + routing + token
 * persistence all get exercised at least once per spec.
 */

import { expect, type Page } from '@playwright/test'
import { DEMO_CREDENTIALS, type DemoRole } from './api'

export async function loginViaUI(page: Page, role: DemoRole): Promise<void> {
  const creds = DEMO_CREDENTIALS[role]
  await page.goto('/login')

  // ProForm wraps inputs in Form.Item; the `name` prop binds to form state,
  // not the DOM <input> element, so `input[name="email"]` won't match.
  // Login page has exactly two inputs (email + password) — target by order.
  const emailInput = page.locator('form input').nth(0)
  const passwordInput = page.locator('form input').nth(1)
  await emailInput.waitFor({ state: 'visible', timeout: 15_000 })
  await emailInput.fill(creds.email)
  await passwordInput.fill(creds.password)

  // The submit button is the only one on the form.
  await page.locator('button[type="submit"]').click()

  // Successful login navigates away from /login.
  await page.waitForURL((u) => !u.pathname.startsWith('/login'), { timeout: 15_000 })
  await expect(page).toHaveURL(/^(?!.*\/login).*/)
}

/** Restore the access token in a fresh context after API-driven login. */
export async function injectToken(page: Page, token: string): Promise<void> {
  await page.addInitScript(([t]) => {
    window.localStorage.setItem('access_token', t as string)
  }, [token])
}
