import type { InventoryOverview, InventoryOverviewRequest, InventoryService } from '@/services/contracts'

export class MockInventoryService implements InventoryService {
  async getOverview(request: InventoryOverviewRequest): Promise<InventoryOverview> {
    return {
      state: 'ok', selectedDate: request.selectedDate ?? '2026-09-11', isToday: false, currency: 'EGP', warehouseName: 'المخزن الرئيسي',
      rows: [{ itemCode: request.itemCode ?? 'CARDBOARD-A', itemName: 'كرتون مضغوط', stockUom: 'Kg', quantity: 900, stockValue: 5200 }],
      summary: { quantity: 900, uom: 'Kg', stockValue: 5200 },
    }
  }
}
