import { createPinia, type Pinia } from 'pinia'

export function createTestingPinia(): Pinia {
  return createPinia()
}
