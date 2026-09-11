export type FrontendErrorKind =
  | 'network'
  | 'authentication'
  | 'permission'
  | 'validation'
  | 'not_found'
  | 'unexpected'

export class FrontendError extends Error {
  readonly kind: FrontendErrorKind
  readonly status: number | undefined

  constructor(kind: FrontendErrorKind, message: string, status?: number) {
    super(message)
    this.kind = kind
    this.status = status
  }
}

export function normalizeApiError(status: number, message?: string): FrontendError {
  const fallback = 'تعذر إتمام الطلب. حاول مرة أخرى.'
  if (status === 401) return new FrontendError('authentication', message ?? 'انتهت جلسة الدخول.', status)
  if (status === 403) return new FrontendError('permission', message ?? 'ليس لديك صلاحية لتنفيذ هذا الإجراء.', status)
  if (status === 404) return new FrontendError('not_found', message ?? 'العنصر المطلوب غير موجود.', status)
  if (status >= 400 && status < 500) return new FrontendError('validation', message ?? fallback, status)
  return new FrontendError('unexpected', message ?? fallback, status)
}
