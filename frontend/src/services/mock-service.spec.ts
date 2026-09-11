import { describe, expect, it } from 'vitest'

import { createServices } from '@/services'

describe('mock service boundary', () => {
  it('returns an authoritative-shaped inventory overview through the service contract', async () => {
    const services = createServices({ apiMode: 'mock', apiBaseUrl: '' })

    const overview = await services.inventory.getOverview({ selectedDate: '2026-09-11' })

    expect(overview.state).toBe('ok')
    expect(overview.rows[0]?.itemCode).toBeTruthy()
    expect(overview.summary.stockValue).toBeTypeOf('number')
  })
})
