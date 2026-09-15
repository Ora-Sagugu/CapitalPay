/**
 * Capture debit / adjustment / refund / wallet screenshots for Main Process PPT.
 * Usage: node scripts/capture_extra_flow_screenshots.mjs
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
const CUSTOMER = 'http://localhost:1027'

async function shot(page, name) {
  const file = path.join(outDir, name)
  await page.waitForTimeout(500)
  await page.screenshot({ path: file, fullPage: false })
  console.log('saved', name)
}

async function customerLogin(page) {
  await page.goto(`${CUSTOMER}/login`)
  await page.evaluate(() => {
    localStorage.clear()
    sessionStorage.clear()
  })
  await page.reload()
  await page.getByRole('tab', { name: 'Sign in' }).click()
  const emailBtn = page.locator('.el-radio-button__inner', { hasText: 'Email' })
  if (await emailBtn.count()) await emailBtn.click({ force: true })
  await page.getByPlaceholder('NameSurname@gmail.com').fill('DanielOchieng@gmail.com')
  await page.getByPlaceholder('Password').fill('123456')
  await page.getByRole('button', { name: 'Sign in' }).click()
  await page.waitForURL((u) => !u.pathname.endsWith('/login'), { timeout: 20000 })
}

async function opsLogin(page) {
  await page.goto(`${OPS}/login`)
  await page.evaluate(() => {
    localStorage.clear()
    sessionStorage.clear()
  })
  await page.reload()
  await page.getByPlaceholder('Email or username').fill('admin')
  await page.locator('input[type=password]').fill('123456')
  await page.getByRole('button', { name: 'Sign in' }).click()
  await page.waitForURL((u) => !u.pathname.includes('/login'), { timeout: 20000 })
}

const browser = await chromium.launch({ headless: true })
const page = await browser.newPage({ viewport: { width: 1440, height: 900 } })

// --- Customer: Account debit rows + Wallet ---
await customerLogin(page)

await page.goto(`${CUSTOMER}/accounts`)
await page.waitForTimeout(1200)
const activity = page.getByText('Account activity')
if (await activity.count()) {
  await activity.click()
  await page.waitForTimeout(400)
}
// Prefer cropping later; full page first
await shot(page, '16_account_debit.png')

await page.goto(`${CUSTOMER}/wallet`)
await page.waitForTimeout(1200)
await shot(page, '19_wallet.png')

// --- Ops: Adjustments (ledger correction) + Refunds ---
await opsLogin(page)

await page.goto(`${OPS}/adjustments`)
await page.waitForTimeout(1200)
const createAdj = page.getByRole('button', { name: /Create ledger adjustment/i })
if (await createAdj.count()) {
  await createAdj.click()
  await page.waitForTimeout(400)
}
await shot(page, '17_ledger_adjustment.png')
await page.keyboard.press('Escape')

await page.goto(`${OPS}/refunds`)
await page.waitForTimeout(1200)
await shot(page, '18_refunds.png')

await browser.close()
console.log('done')
