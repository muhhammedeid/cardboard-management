# Cardboard Management Frontend

Independent Vue 3 operator frontend for Cardboard Management. It is deliberately isolated from Frappe Desk assets and does not modify Frappe/ERPNext core.

## Commands

```bash
npm run dev
npm run typecheck
npm run lint
npm test
npm run build
```

## Environment

Copy `.env.example` to `.env.local`. `VITE_API_MODE=mock` uses deterministic adapters. `VITE_API_MODE=real` uses Frappe RPC through the service boundary. `VITE_API_BASE_URL` is empty for same-origin deployment and may point to a development backend only when its CORS/session configuration is explicitly approved. Never place credentials, cookies, or secrets in frontend environment files.

## Architecture

`src/features` owns product areas; `src/components` owns reusable presentation; `src/services/contracts` owns typed backend DTOs; `src/services/api` owns transport; `src/services/mocks` owns mock adapters. Vue components never call Frappe directly.

**Do not implement business calculations in the frontend.** Stock, financial totals, supplier outstanding, valuation, permissions, and document lifecycle authority always come from the backend. UI mappers may only make deterministic presentation transformations.

## Authentication and deployment

The real adapter uses Frappe session cookies with `credentials: 'include'`; it does not create a custom JWT system or duplicate users. Production should serve this SPA behind the same deployment boundary as Frappe (for example `/cardboard`) so session reuse and CSRF policy remain native. During development Vite runs separately; cross-origin operation requires a separately approved, minimal Frappe CORS/CSRF arrangement and is not configured by FE00.
