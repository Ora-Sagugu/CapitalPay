/**
 * Capture SOW PPT screenshots from local CapitalPay portals.
 * Requires portals running on :1025 / :1026 / :1027.
 *
 * Usage (from repo root):
 *   node scripts/capture_sow_screenshots.mjs
 */
import { createRequire } from 'module'
import fs from 'fs'
import path from 'path'
import { fileURLToPath } from 'url'

const require = createRequire(import.meta.url)
const { chromium } = require('../frontend/client_portal/node_modules/playwright')

const __dirname = path.dirname(fileURLToPath(import.meta.url))
const outDir = path.join(__dirname, '..', 'docs', 'sow_screenshots')
fs.mkdirSync(outDir, { recursive: true })

const OPS = 'http://localhost:1025'
const AGENT = 'http://localhost:1026'
const CUSTOMER = 'http://localhost:1027'

async function shot(page, name) {
  const file = path.join(outDir, name)
  await page.waitForTimeout(400)
  await page.screenshot({ path: file, fullPage: false })
  console.log('saved', name)
}

async function clearStorage(page) {
  await page.goto('about:blank')
  await page.context().clearCookies()
}

async function ensureEmailMode(page) {
  const emailBtn = page.locator('.el-radio-button__inner', { hasText: 'Email' })
  if (await emailBtn.count()) {
    await emailBtn.click({ force: true })
  }
}

async function portalLogin(page, base, email, password) {
  await page.goto(`${base}/login`)
  await page.evaluate(() => {
    localStorage.clear()
    sessionStorage.clear()
  })
  await page.reload()
  await page.getByRole('tab', { name: 'Sign in' }).click()
  await ensureEmailMode(page)
  await page.getByPlaceholder('NameSurname@gmail.com').fill(email)
  await page.getByPlaceholder('Password').fill(password)
  await page.getByRole('button', { name: 'Sign in' }).click()
  await page.waitForURL((url) => !url.pathname.endsWith('/login'), { timeout: 20000 })
}

async function customerLogin(page, email, password) {
  await portalLogin(page, CUSTOMER, email, password)
}

async function agentLogin(page, email, password) {
  await portalLogin(page, AGENT, email, password)
}

async function opsLogin(page) {
  await page.goto(`${OPS}/login`)
  await page.evaluate(() => {
    localStorage.clear()
    sessionStorage.clear()
  })
  await page.reload()
  await page.getByPlaceholder('Email or username').fill('admin')
  await page.locator('input[type="password"]').fill('123456')
  await page.getByRole('button', { name: 'Sign in' }).click()
  await page.waitForURL((url) => !url.pathname.includes('/login'), { timeout: 20000 })
}

async function main() {
  const browser = await chromium.launch({ headless: true })
  const context = await browser.newContext({
    viewport: { width: 1440, height: 900 },
    deviceScaleFactor: 1,
  })
  const page = await context.newPage()

  // --- Agent auth ---
  await page.goto(`${AGENT}/login`)
  await page.getByRole('tab', { name: 'Sign in' }).click()
  await shot(page, '01_agent_login.png')
  await page.getByRole('tab', { name: 'Register' }).click()
  await page.waitForTimeout(300)
  await shot(page, '02_agent_register.png')

  // --- Customer auth ---
  await context.clearCookies()
  await page.goto(`${CUSTOMER}/login`)
  // Clear any persisted token
  await page.evaluate(() => {
    localStorage.clear()
    sessionStorage.clear()
  })
  await page.reload()
  await page.getByRole('tab', { name: 'Sign in' }).click()
  await shot(page, '03_customer_login.png')
  await page.getByRole('tab', { name: 'Register' }).click()
  await page.waitForTimeout(300)
  await shot(page, '04_customer_register.png')

  // --- Onboarding (pending customer) ---
  await customerLogin(page, 'IbrahimMusa@gmail.com', '123456')
  if (!page.url().includes('onboarding')) {
    await page.goto(`${CUSTOMER}/onboarding`)
  }
  await page.waitForTimeout(800)
  await shot(page, '05_onboarding_kyc.png')

  // --- Customer remittance + status + ledger (approved customer) ---
  await customerLogin(page, 'DanielOchieng@gmail.com', '123456')

  await page.goto(`${CUSTOMER}/remittance`)
  await page.waitForTimeout(1000)
  await shot(page, '08_remittance_apply.png')

  await page.goto(`${CUSTOMER}/orders`)
  await page.waitForTimeout(1000)
  const viewBtn = page.getByRole('button', { name: /view|detail/i }).first()
  const rowClick = page.locator('table tbody tr').first()
  if (await viewBtn.count()) {
    await viewBtn.click()
  } else if (await rowClick.count()) {
    await rowClick.click()
  }
  await page.waitForTimeout(800)
  await shot(page, '11_status_tracking.png')
  await page.keyboard.press('Escape')

  const prnInput = page.getByPlaceholder('Search by PRN')
  if (await prnInput.count()) {
    await prnInput.fill('880001')
    await page.getByRole('button', { name: 'Search' }).click()
    await page.waitForTimeout(1000)
    await shot(page, '14_prn_customer_search.png')
  }

  await page.goto(`${CUSTOMER}/accounts`)
  await page.waitForTimeout(1000)
  const activity = page.getByText('Account activity')
  if (await activity.count()) {
    await activity.click()
    await page.waitForTimeout(500)
  }
  await shot(page, '12_account_ledger.png')

  // --- Agent review ---
  await agentLogin(page, 'GraceNyambura@gmail.com', '123456')
  await page.goto(`${AGENT}/agent/orders`)
  await page.waitForTimeout(1000)
  await shot(page, '09_agent_orders_review.png')

  // --- Ops: fees, orders, payout bank, fund trace ---
  await opsLogin(page)

  await page.goto(`${OPS}/remittance-fees`)
  await page.waitForTimeout(1000)
  await shot(page, '06_remittance_fee.png')

  await page.goto(`${OPS}/agent-fees`)
  await page.waitForTimeout(1000)
  await shot(page, '07_agent_fee.png')

  await page.goto(`${OPS}/orders`)
  await page.waitForTimeout(1200)
  await shot(page, '09b_ops_orders.png')

  // Find PAYDEMOPAYOUT01 — Confirm payment (collection) then Confirm transfer (payout)
  const search = page.locator('input[placeholder*="order" i], input[placeholder*="Search" i], .el-input__inner').first()
  if (await search.count()) {
    await search.fill('PAYDEMOPAYOUT01')
    await page.keyboard.press('Enter')
    await page.waitForTimeout(800)
  }
  const demoRow = page.getByText('PAYDEMOPAYOUT01').first()
  if (await demoRow.count()) {
    const row = page.locator('tr', { hasText: 'PAYDEMOPAYOUT01' }).first()
    const confirmPay = row.getByRole('button', { name: 'Confirm payment' })
    if (await confirmPay.count()) {
      await confirmPay.click()
      await page.waitForSelector('.el-message-box', { timeout: 8000 })
      await page.waitForTimeout(400)
      await shot(page, '10b_confirm_payment.png')
      await page.keyboard.press('Escape')
      await page.waitForTimeout(300)
    }
    const confirmBtn = row.getByRole('button', { name: /Confirm transfer/i })
    if (await confirmBtn.count()) {
      await confirmBtn.click()
    } else {
      // Maybe need View then action
      const view = row.getByRole('button', { name: /View/i })
      if (await view.count()) await view.click()
      await page.waitForTimeout(500)
      const confirm2 = page.getByRole('button', { name: /Confirm transfer/i }).first()
      if (await confirm2.count()) await confirm2.click()
    }
    await page.waitForSelector('text=Select payout bank', { timeout: 10000 })
    await page.waitForTimeout(800)
    await shot(page, '10_select_payout_bank.png')
    await page.keyboard.press('Escape')
  } else {
    console.warn('PAYDEMOPAYOUT01 not found — skipping payout bank shot')
  }

  await page.goto(`${OPS}/fund-trace`)
  await page.waitForTimeout(1000)
  const ftSearch = page.locator('input').first()
  if (await ftSearch.count()) {
    await ftSearch.fill('PAYDEMOPAYOUT01')
    await page.keyboard.press('Enter')
    await page.waitForTimeout(800)
  }
  await shot(page, '13_fund_trace.png')

  await browser.close()
  console.log('Done. Screenshots in', outDir)
}

main().catch((err) => {
  console.error(err)
  process.exit(1)
})
