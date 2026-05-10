/**
 * UI login helper. Drives the real LoginPage so auth + routing + token
 * persistence all get exercised at least once per spec.
 */

import { expect, type Page } from '@playwright/test'
import { DEMO_CREDENTIALS, type DemoRole } from './api'

export async function loginViaUI(page: Page, role: DemoRole): Promise<void> {
  const creds = DEMO_CREDENTIALS[role]
  await page.goto('/login')

  // ProForm's LoginForm renders inputs with name="email" / name="password"
  // (the `placeholder` text is i18n-driven and brittle).
  await page.fill('input[name="email"]', creds.email)
  await page.fill('input[name="password"]', creds.password)

  // The login button is the only submit button on the page.
  await page.locator('button[type="submit"]').click()

  // Successful login navigates away from /login and the dashboard renders.
  await page.waitForURL((u) => !u.pathname.startsWith('/login'), { timeout: 15_000 })
  await expect(page).toHaveURL(/^(?!.*\/login).*/)
}

/** Restore the access token in a fresh context after API-driven login. */
export async function injectToken(page: Page, token: string): Promise<void> {
  await page.addInitScript(([t]) => {
    window.localStorage.setItem('access_token', t as string)
  }, [token])
}
