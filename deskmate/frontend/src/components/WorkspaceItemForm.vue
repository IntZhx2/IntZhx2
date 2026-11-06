<script setup lang="ts">
import { computed } from "vue";
import type { WorkspaceItem } from "../types/contracts";
import Icon from "./Icon.vue";
const props = defineProps<{ item: WorkspaceItem; index: number }>();
const emit = defineEmits<{ change: [item: WorkspaceItem]; remove: [] }>();
const field = computed(() =>
  props.item.type === "url"
    ? "url"
    : props.item.type === "app"
      ? "name"
      : "path",
);
const placeholder = computed(() =>
  props.item.type === "url"
    ? "https://…"
    : props.item.type === "app"
      ? "白名单应用名称"
      : "Windows 电脑上的完整路径",
);
function changeType(value: unknown) {
  if (!["url", "app", "folder", "vscode"].includes(String(value))) return;
  const type = value as WorkspaceItem["type"];
  emit("change", {
    type,
    [type === "url" ? "url" : type === "app" ? "name" : "path"]: "",
  });
}
function changeValue(value: string) {
  emit("change", { ...props.item, [field.value]: value });
}
</script>
<template>
  <div class="workspace-item-form">
    <el-select
      :model-value="item.type"
      :aria-label="`启动项${index + 1}类型`"
      @change="changeType"
    >
      <el-option label="网页" value="url" /><el-option
        label="VS Code"
        value="vscode"
      /><el-option label="文件夹" value="folder" /><el-option
        label="应用"
        value="app"
      />
    </el-select>
    <el-input
      :model-value="item[field]"
      :placeholder="placeholder"
      :maxlength="item.type === 'url' ? 2048 : item.type === 'app' ? 100 : 1024"
      :aria-label="`启动项${index + 1}地址或名称`"
      @update:model-value="changeValue"
    />
    <button
      class="icon-button"
      :aria-label="`移除启动项${index + 1}`"
      @click="emit('remove')"
    >
      <Icon name="close" :size="16" />
    </button>
  </div>
</template>
