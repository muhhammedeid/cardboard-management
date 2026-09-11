<script setup lang="ts">
const items = [
  { label: 'الرئيسية', to: '/' },
  { label: 'التوريدات', to: '/supplies' },
  { label: 'المبيعات', to: '/sales' },
  { label: 'الموردون', to: '/suppliers' },
  { label: 'المدفوعات', to: '/payments' },
  { label: 'المصروفات', to: '/expenses' },
  { label: 'المخزون', to: '/inventory' },
  { label: 'التقارير', to: '/reports' },
  { label: 'الإعدادات', to: '/settings' },
]
</script>

<template>
  <nav class="app-navigation" aria-label="التنقل الرئيسي">
    <RouterLink v-for="item in items" :key="item.to" :to="item.to">{{ item.label }}</RouterLink>
  </nav>
</template>
