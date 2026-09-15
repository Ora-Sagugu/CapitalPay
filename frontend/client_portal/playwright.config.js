import { defineConfig } from '@playwright/test'
import path from 'node:path'
import { fileURLToPath } from 'node:url'

const clientDir = path.dirname(fileURLToPath(import.meta.url))
const repoRoot = path.resolve(clientDir, '..', '..')
const customerDir = path.resolve(repoRoot, 'frontend', 'customer_portal')
const python = process.env.E2E_PYTHON || path.resolve(
  repoRoot,
  '.venv',
  process.platform === 'win32' ? 'Scripts/python.exe' : 'bin/python'
)

export default defineConfig({
  testDir: './e2e',
  fullyParallel: false,
  timeout: 60_000,
  expect: { timeout: 10_000 },
  use: {
    baseURL: 'http://127.0.0.1:1029',
    trace: 'retain-on-failure',
    screenshot: 'only-on-failure'
  },
  webServer: [
    {
      command: `"${python}" "${path.resolve(repoRoot, 'scripts', 'e2e_backend.py')}"`,
      cwd: repoRoot,
      url: 'http://127.0.0.1:1028/api/docs/',
      reuseExistingServer: false,
      timeout: 120_000
    },
    {
      command: 'npm run dev -- --host 127.0.0.1 --port 1029 --strictPort',
      cwd: clientDir,
      url: 'http://127.0.0.1:1029/login',
      env: { VITE_API_TARGET: 'http://127.0.0.1:1028' },
      reuseExistingServer: false,
      timeout: 60_000
    },
    {
      command: 'npm run dev -- --host 127.0.0.1 --port 1030 --strictPort',
      cwd: customerDir,
      url: 'http://127.0.0.1:1030/login',
      env: { VITE_API_TARGET: 'http://127.0.0.1:1028' },
      reuseExistingServer: false,
      timeout: 60_000
    }
  ]
})
