function envValue(key) {
  return import.meta.env[key] || ''
}

export function getPortalMode() {
  return envValue('VITE_PORTAL_MODE') === 'agent' ? 'agent' : 'customer'
}

export function isAgentApp() {
  return getPortalMode() === 'agent'
}

export function otherPortalUrl() {
  return envValue('VITE_OTHER_PORTAL_URL')
}

export function defaultHomePath() {
  return isAgentApp() ? '/agent' : '/accounts'
}

export function defaultLoginRouteName() {
  return 'login'
}
