import type { FrontendConfig } from '@/app/bootstrap/config'
import type {
  InventoryOverview,
  InventoryOverviewRequest,
  InventoryService,
  OperationsSummary,
  OperationsSummaryRequest,
  ReportingService,
} from './contracts'
import { FrappeRpcTransport, type RpcTransport } from './api/frappe-rpc'
import { MockInventoryService } from './mocks/inventory'
import { MockReportingService } from './mocks/reporting'

interface RawInventoryOverview {
  state: InventoryOverview['state']
  selected_date: string
  is_today: boolean
  currency: string
  warehouse_name: string
  rows?: Array<{ item_code: string; item_name: string; stock_uom: string; quantity: number; stock_value: number }>
  summary?: { quantity: number | null; uom: string | null; stock_value: number }
}

function mapInventoryOverview(raw: RawInventoryOverview): InventoryOverview {
  return {
    state: raw.state,
    selectedDate: raw.selected_date,
    isToday: raw.is_today,
    currency: raw.currency,
    warehouseName: raw.warehouse_name,
    rows: (raw.rows ?? []).map((row) => ({
      itemCode: row.item_code,
      itemName: row.item_name,
      stockUom: row.stock_uom,
      quantity: row.quantity,
      stockValue: row.stock_value,
    })),
    summary: {
      quantity: raw.summary?.quantity ?? null,
      uom: raw.summary?.uom ?? null,
      stockValue: raw.summary?.stock_value ?? 0,
    },
  }
}

interface RawOperationsSummary {
  from_date: string
  to_date: string
  supplies: { count: number; quantity: number; payable_weight: number; value: number }
  sales: { count: number; quantity: number; value: number }
  expenses: { count: number; amount: number }
  supplier_payments: { count: number; amount: number }
}

function mapOperationsSummary(raw: RawOperationsSummary): OperationsSummary {
  return {
    fromDate: raw.from_date,
    toDate: raw.to_date,
    supplies: {
      count: raw.supplies.count,
      quantity: raw.supplies.quantity,
      payableWeight: raw.supplies.payable_weight,
      value: raw.supplies.value,
    },
    sales: raw.sales,
    expenses: raw.expenses,
    supplierPayments: raw.supplier_payments,
  }
}

class RealInventoryService implements InventoryService {
  private readonly transport: RpcTransport

  constructor(transport: RpcTransport) {
    this.transport = transport
  }

  async getOverview(request: InventoryOverviewRequest): Promise<InventoryOverview> {
    const raw = await this.transport.call<RawInventoryOverview>(
      'cardboard_management.inventory.get_inventory_overview',
      { item_code: request.itemCode, selected_date: request.selectedDate },
    )
    return mapInventoryOverview(raw)
  }
}

class RealReportingService implements ReportingService {
  private readonly transport: RpcTransport

  constructor(transport: RpcTransport) {
    this.transport = transport
  }

  async getOperationsSummary(request: OperationsSummaryRequest): Promise<OperationsSummary> {
    const raw = await this.transport.call<RawOperationsSummary>(
      'cardboard_management.reporting.get_operations_summary',
      {
        from_date: request.fromDate,
        to_date: request.toDate,
        cardboard_item: request.cardboardItem,
      },
    )
    return mapOperationsSummary(raw)
  }
}

export interface FrontendServices {
  inventory: InventoryService
  reporting: ReportingService
}

export function createServices(
  config: Pick<FrontendConfig, 'apiMode' | 'apiBaseUrl'>,
): FrontendServices {
  if (config.apiMode === 'mock') {
    return { inventory: new MockInventoryService(), reporting: new MockReportingService() }
  }
  const transport = new FrappeRpcTransport(config.apiBaseUrl)
  return { inventory: new RealInventoryService(transport), reporting: new RealReportingService(transport) }
}
