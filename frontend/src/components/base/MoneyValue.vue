<script setup lang="ts">
import BidiValue from './BidiValue.vue'
defineProps<{ value: string }>()
</script>
<template><BidiValue :value="value" /></template>
