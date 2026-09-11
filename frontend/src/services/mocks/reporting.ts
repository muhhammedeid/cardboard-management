import type { OperationsSummary, OperationsSummaryRequest, ReportingService } from '@/services/contracts'

export class MockReportingService implements ReportingService {
  async getOperationsSummary(request: OperationsSummaryRequest): Promise<OperationsSummary> {
    return { fromDate: request.fromDate ?? '2026-09-11', toDate: request.toDate ?? '2026-09-11', supplies: { count: 0, quantity: 0, payableWeight: 0, value: 0 }, sales: { count: 0, quantity: 0, value: 0 }, expenses: { count: 0, amount: 0 }, supplierPayments: { count: 0, amount: 0 } }
  }
}
