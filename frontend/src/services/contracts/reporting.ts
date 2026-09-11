export interface OperationsSummaryRequest { fromDate?: string; toDate?: string; cardboardItem?: string }
export interface OperationsSummary { fromDate: string; toDate: string; supplies: { count: number; quantity: number; payableWeight: number; value: number }; sales: { count: number; quantity: number; value: number }; expenses: { count: number; amount: number }; supplierPayments: { count: number; amount: number } }

export interface ReportingService {
  getOperationsSummary(request: OperationsSummaryRequest): Promise<OperationsSummary>
}
