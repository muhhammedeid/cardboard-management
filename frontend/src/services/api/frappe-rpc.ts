import { FrontendError, normalizeApiError } from './errors'

export interface RpcTransport {
  call<T>(method: string, args?: Record<string, unknown>): Promise<T>
}

interface FrappeResponse<T> {
  message?: T
  exc_type?: string
  _server_messages?: string
}

export class FrappeRpcTransport implements RpcTransport {
  private readonly baseUrl: string

  constructor(baseUrl: string) {
    this.baseUrl = baseUrl
  }

  async call<T>(method: string, args: Record<string, unknown> = {}): Promise<T> {
    let response: Response
    try {
      response = await fetch(`${this.baseUrl}/api/method/${method}`, {
        method: 'POST',
        credentials: 'include',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(args),
      })
    } catch {
      throw new FrontendError('network', 'تعذر الاتصال بالخادم.')
    }
    const body = (await response.json().catch(() => ({}))) as FrappeResponse<T>
    if (!response.ok) throw normalizeApiError(response.status, body._server_messages)
    if (body.message === undefined) throw new FrontendError('unexpected', 'استجابة الخادم غير مكتملة.')
    return body.message
  }
}
