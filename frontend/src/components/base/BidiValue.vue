<script setup lang="ts">
defineProps<{ value: string | number }>()
</script>
<template><bdi dir="ltr"><slot>{{ value }}</slot></bdi></template>
