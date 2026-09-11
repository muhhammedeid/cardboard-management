import { createRouter, createMemoryHistory, createWebHistory, type RouteRecordRaw } from 'vue-router'

import PlaceholderPage from '@/features/shared/PlaceholderPage.vue'

export const routes: RouteRecordRaw[] = [
  { path: '/', name: 'home', component: PlaceholderPage, meta: { label: 'الرئيسية', area: 'home' } },
  { path: '/supplies', name: 'supplies', component: PlaceholderPage, meta: { label: 'التوريدات', area: 'supplies' } },
  { path: '/supplies/new', name: 'supply-new', component: PlaceholderPage, meta: { label: 'توريدة جديدة', area: 'supplies' } },
  { path: '/supplies/:id', name: 'supply-detail', component: PlaceholderPage, meta: { label: 'تفاصيل توريدة', area: 'supplies' } },
  { path: '/sales', name: 'sales', component: PlaceholderPage, meta: { label: 'المبيعات', area: 'sales' } },
  { path: '/sales/new', name: 'sale-new', component: PlaceholderPage, meta: { label: 'بيع جديد', area: 'sales' } },
  { path: '/sales/:id', name: 'sale-detail', component: PlaceholderPage, meta: { label: 'تفاصيل بيع', area: 'sales' } },
  { path: '/suppliers', name: 'suppliers', component: PlaceholderPage, meta: { label: 'الموردون', area: 'suppliers' } },
  { path: '/suppliers/new', name: 'supplier-new', component: PlaceholderPage, meta: { label: 'مورد جديد', area: 'suppliers' } },
  { path: '/suppliers/:id', name: 'supplier-detail', component: PlaceholderPage, meta: { label: 'ملف المورد', area: 'suppliers' } },
  { path: '/payments', name: 'payments', component: PlaceholderPage, meta: { label: 'المدفوعات', area: 'payments' } },
  { path: '/payments/new', name: 'payment-new', component: PlaceholderPage, meta: { label: 'دفعة مورد جديدة', area: 'payments' } },
  { path: '/payments/:id', name: 'payment-detail', component: PlaceholderPage, meta: { label: 'تفاصيل دفعة', area: 'payments' } },
  { path: '/expenses', name: 'expenses', component: PlaceholderPage, meta: { label: 'المصروفات', area: 'expenses' } },
  { path: '/expenses/new', name: 'expense-new', component: PlaceholderPage, meta: { label: 'مصروف جديد', area: 'expenses' } },
  { path: '/expenses/:id', name: 'expense-detail', component: PlaceholderPage, meta: { label: 'تفاصيل مصروف', area: 'expenses' } },
  { path: '/inventory', name: 'inventory', component: PlaceholderPage, meta: { label: 'المخزون', area: 'inventory' } },
  { path: '/inventory/history', name: 'inventory-history', component: PlaceholderPage, meta: { label: 'الرصيد التاريخي', area: 'inventory' } },
  { path: '/inventory/movement', name: 'inventory-movement', component: PlaceholderPage, meta: { label: 'حركة المخزون', area: 'inventory' } },
  { path: '/reports', name: 'reports', component: PlaceholderPage, meta: { label: 'التقارير', area: 'reports' } },
  { path: '/reports/:reportKey', name: 'report-detail', component: PlaceholderPage, meta: { label: 'تقرير', area: 'reports' } },
  { path: '/settings', name: 'settings', component: PlaceholderPage, meta: { label: 'الإعدادات', area: 'settings' } },
]

export const router = createRouter({
  history: import.meta.env.MODE === 'test' ? createMemoryHistory() : createWebHistory(import.meta.env.BASE_URL),
  routes,
})
