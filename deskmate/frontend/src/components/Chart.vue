<script setup lang="ts">
import { onMounted, onBeforeUnmount, ref, watch } from "vue";
import {
  use,
  init,
  type EChartsCoreOption,
  type EChartsType,
} from "echarts/core";
import { LineChart, BarChart, PieChart } from "echarts/charts";
import {
  GridComponent,
  TooltipComponent,
  LegendComponent,
  MarkLineComponent,
} from "echarts/components";
import { CanvasRenderer } from "echarts/renderers";
use([
  LineChart,
  BarChart,
  PieChart,
  GridComponent,
  TooltipComponent,
  LegendComponent,
  MarkLineComponent,
  CanvasRenderer,
]);
const props = withDefaults(
  defineProps<{ option: EChartsCoreOption; label: string; height?: number }>(),
  { height: 240 },
);
const host = ref<HTMLDivElement>();
let chart: EChartsType | undefined, observer: ResizeObserver | undefined;
onMounted(() => {
  chart = init(host.value!);
  chart.setOption(props.option);
  observer = new ResizeObserver(() => chart?.resize());
  observer.observe(host.value!);
});
watch(
  () => props.option,
  (option) => chart?.setOption(option, { notMerge: true }),
  { deep: true },
);
onBeforeUnmount(() => {
  observer?.disconnect();
  chart?.dispose();
});
</script>
<template>
  <div
    ref="host"
    class="chart"
    :style="{ height: `${height}px` }"
    role="img"
    :aria-label="label"
  />
</template>
