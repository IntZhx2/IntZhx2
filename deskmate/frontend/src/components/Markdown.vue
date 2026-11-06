<script setup lang="ts">
import { computed } from "vue";
import { markdown } from "../lib/markdown";
const props = defineProps<{ text: string }>();
const html = computed(() => markdown(props.text));
</script>
<template><div class="markdown" v-html="html" /></template>
