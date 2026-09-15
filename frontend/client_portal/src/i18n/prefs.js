export const DEFAULT_COLOR = '#f08040'

const STALE_KEYS = ['ui.locale', 'ui.primaryColor']

function hexToRgb(hex) {
  const h = (hex || DEFAULT_COLOR).replace('#', '')
  const full = h.length === 3 ? h.split('').map((c) => c + c).join('') : h
  return {
    r: parseInt(full.slice(0, 2), 16),
    g: parseInt(full.slice(2, 4), 16),
    b: parseInt(full.slice(4, 6), 16)
  }
}

function mix(hex, ratioToWhite) {
  const { r, g, b } = hexToRgb(hex)
  const m = (c) => Math.round(c + (255 - c) * ratioToWhite)
  const to = (n) => n.toString(16).padStart(2, '0')
  return `#${to(m(r))}${to(m(g))}${to(m(b))}`
}

function darken(hex, ratio) {
  const { r, g, b } = hexToRgb(hex)
  const d = (c) => Math.round(c * (1 - ratio))
  const to = (n) => n.toString(16).padStart(2, '0')
  return `#${to(d(r))}${to(d(g))}${to(d(b))}`
}

export function applyTheme(hex = DEFAULT_COLOR) {
  const color = hex || DEFAULT_COLOR
  const root = document.documentElement
  root.style.setProperty('--tech-orange', color)
  root.style.setProperty('--tech-orange-dark', darken(color, 0.12))
  root.style.setProperty('--tech-orange-deep', darken(color, 0.22))
  root.style.setProperty('--tech-peach', mix(color, 0.92))
  root.style.setProperty('--el-color-primary', color)
  root.style.setProperty('--el-color-primary-light-3', mix(color, 0.3))
  root.style.setProperty('--el-color-primary-light-5', mix(color, 0.5))
  root.style.setProperty('--el-color-primary-light-7', mix(color, 0.7))
  root.style.setProperty('--el-color-primary-light-8', mix(color, 0.8))
  root.style.setProperty('--el-color-primary-light-9', mix(color, 0.9))
  root.style.setProperty('--el-color-primary-dark-2', darken(color, 0.16))
  root.style.setProperty('--tech-aside-from', darken(color, 0.12))
  root.style.setProperty('--tech-aside-mid', mix(color, 0.18))
  root.style.setProperty('--tech-aside-to', mix(color, 0.32))
}

export function clearStaleAppearancePrefs() {
  STALE_KEYS.forEach((key) => localStorage.removeItem(key))
}
