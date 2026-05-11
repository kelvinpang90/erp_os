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
  // ProForm/Ant Form also injects a hidden text input before the real fields
  // (autofill defence), so a naive `form input` query hits the hidden one.
  // `:visible` skips past it. Order is then: email (text), password.
  const visibleInputs = page.locator('form input:visible')
  await visibleInputs.first().waitFor({ state: 'visible', timeout: 15_000 })
  await visibleInputs.nth(0).fill(creds.email)
  await visibleInputs.nth(1).fill(creds.password)

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
