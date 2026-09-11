export type ApiMode = 'mock' | 'real'

export interface FrontendConfig {
  apiBaseUrl: string
  apiMode: ApiMode
}

export function getFrontendConfig(environment = import.meta.env): FrontendConfig {
  const apiMode = environment.VITE_API_MODE ?? 'mock'
  if (apiMode !== 'mock' && apiMode !== 'real') {
    throw new Error('VITE_API_MODE must be mock or real')
  }

  return { apiMode, apiBaseUrl: (environment.VITE_API_BASE_URL ?? '').replace(/\/$/, '') }
}
