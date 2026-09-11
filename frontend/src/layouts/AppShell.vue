<script setup lang="ts">
import { computed } from 'vue'
import { useRoute } from 'vue-router'

import AppNavigation from '@/components/navigation/AppNavigation.vue'

const route = useRoute()
const pageTitle = computed(() => String(route.meta.label ?? 'إدارة الكرتون'))
</script>

<template>
  <div class="app-shell" data-testid="app-shell">
    <AppNavigation />
    <main class="app-shell__content">
      <header class="app-shell__topbar">
        <p class="app-shell__product">إدارة الكرتون</p>
        <p class="app-shell__title">{{ pageTitle }}</p>
      </header>
      <RouterView />
    </main>
  </div>
</template>
