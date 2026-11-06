<script setup lang="ts">
withDefaults(defineProps<{ name: string; size?: number }>(), { size: 20 });
const paths: Record<string, string> = {
  grid: "M3 3h7v7H3zM14 3h7v7h-7zM3 14h7v7H3zM14 14h7v7h-7z",
  desk: "M3 13h18M5 13v8m14-8v8M9 13V5h9m-5 0 4-3 4 3M8 17h8",
  chat: "M21 11a8 8 0 0 1-8 8H6l-4 3V11a9 9 0 0 1 19 0ZM7 9h10M7 13h6",
  chart: "M4 3v17h17M8 15v-4m5 4V6m5 9v-7",
  flask: "M9 3h6m-5 0v7L4 20c-.4.6 0 1 1 1h14c1 0 1.4-.4 1-1l-6-10V3M7 15h10",
  settings:
    "M12 8a4 4 0 1 0 0 8 4 4 0 0 0 0-8ZM9 3h6l1 3 3 1 2 4-2 3v4l-4 3-3-1-3 1-4-3v-4l-2-3 2-4 3-1Z",
  arrow: "M5 12h14m-5-5 5 5-5 5",
  plus: "M12 5v14M5 12h14",
  play: "m9 5 11 7-11 7Z",
  stop: "M6 6h12v12H6z",
  leaf: "M20 3C7 2 2 8 5 15s15 5 15-12ZM5 20 15 9",
  bell: "M18 8a6 6 0 0 0-12 0c0 8-3 8-3 9h18c0-1-3-1-3-9M10 21h4",
  sun: "M12 8a4 4 0 1 0 0 8 4 4 0 0 0 0-8ZM12 2v2m0 16v2M2 12h2m16 0h2M5 5l1.5 1.5m11 11L19 19M5 19l1.5-1.5m11-11L19 5",
  lamp: "M9 13h10l-3-8H9l-3 8Zm3 0v8M7 21h10M9 5l-4 5v11",
  snow: "M12 2v20M3.3 7l17.4 10M3.3 17 20.7 7M9 4l3 3 3-3M9 20l3-3 3 3",
  plug: "M8 2v5m8-5v5M6 7h12v5a6 6 0 0 1-12 0ZM12 18v4",
  temp: "M9 14V5a3 3 0 0 1 6 0v9a5 5 0 1 1-6 0ZM12 8v10m6-11h3m-3 4h3",
  drop: "M12 2S4 11 4 15a8 8 0 0 0 16 0c0-4-8-13-8-13ZM8 15a4 4 0 0 0 4 4",
  clock: "M12 3a9 9 0 1 0 0 18 9 9 0 0 0 0-18ZM12 7v5l3 2",
  check: "m5 12 4 4L19 6",
  close: "m6 6 12 12M6 18 18 6",
  mic: "M9 5a3 3 0 0 1 6 0v7a3 3 0 0 1-6 0ZM5 10v2a7 7 0 0 0 14 0v-2M12 19v3m-4 0h8",
  send: "m3 3 19 9-19 9 3-9Zm3 9h16",
  edit: "m16 3 5 5-12 12-6 1 1-6ZM13 6l5 5",
  trash: "M3 6h18M9 6V3h6v3M6 6l1 15h10l1-15M10 10v7m4-7v7",
  download: "M12 3v12m-5-5 5 5 5-5M4 16v5h16v-5",
  logout: "M9 4H4v16h5M13 8l4 4-4 4m-5-4h13",
  user: "M12 3a4 4 0 1 0 0 8 4 4 0 0 0 0-8ZM4 21v-2a8 8 0 0 1 16 0v2",
  shield: "m12 2 8 4v6c0 6-8 10-8 10S4 18 4 12V6Zm-4 10 3 3 5-6",
  code: "m8 6-6 6 6 6m8-12 6 6-6 6M14 3l-4 18",
  monitor: "M3 3h18v13H3zM12 16v5m-5 0h10",
  chevron: "m9 5 7 7-7 7",
  info: "M12 3a9 9 0 1 0 0 18 9 9 0 0 0 0-18ZM12 11v6m0-10v1",
  refresh:
    "M20 7v5h-5M4 17v-5h5M5 7a8 8 0 0 1 14-2l1 7M4 12l1 7a8 8 0 0 0 14-2",
};
</script>
<template>
  <svg
    :width="size"
    :height="size"
    viewBox="0 0 24 24"
    fill="none"
    stroke="currentColor"
    stroke-width="1.65"
    stroke-linecap="round"
    stroke-linejoin="round"
    aria-hidden="true"
  >
    <path :d="paths[name] || paths.grid" />
  </svg>
</template>
