<script setup lang="ts">
import { computed } from 'vue'
import { useRoute } from 'vue-router'

const route = useRoute()
const title = computed(() => String(route.meta.label ?? 'إدارة الكرتون'))
</script>

<template>
  <section class="placeholder-page" :aria-label="title">
    <h1>{{ title }}</h1>
    <p>هذه شاشة تمهيدية ضمن تأسيس الواجهة المستقلة.</p>
  </section>
</template>
