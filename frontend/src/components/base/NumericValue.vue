<script setup lang="ts">
import BidiValue from './BidiValue.vue'
defineProps<{ value: string | number }>()
</script>
<template><BidiValue :value="value" /></template>
