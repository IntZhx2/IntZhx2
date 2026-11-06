<script setup lang="ts">
import { computed, onBeforeUnmount, ref, watch } from "vue";
import { ElMessage } from "element-plus";
import { ElDatePicker } from "element-plus/es/components/date-picker/index";
import "element-plus/es/components/date-picker/style/css";
import { useApp } from "../stores/app";
import { ApiError, download, post, request, today } from "../lib/api";
import type { DailyReport, FocusSession, Timeline } from "../types/contracts";
import Chart from "../components/Chart.vue";
import Icon from "../components/Icon.vue";
import Markdown from "../components/Markdown.vue";
const app = useApp(),
  date = ref(today()),
  sessions = ref<FocusSession[]>([]),
  timeline = ref<Timeline | null>(null),
  report = ref<DailyReport | null>(null),
  loading = ref(false),
  generating = ref(false),
  error = ref(""),
  unavailable = ref(false);
let controller: AbortController | undefined,
  generation = 0;
async function load() {
  const stamp = ++generation;
  controller?.abort();
  controller = new AbortController();
  loading.value = true;
  error.value = "";
  unavailable.value = false;
  report.value = null;
  timeline.value = null;
  sessions.value = [];
  if (app.preview) {
    if (date.value === today()) {
      timeline.value = JSON.parse(JSON.stringify(app.timeline));
      sessions.value = [
        {
          id: 1,
          started_at: new Date(Date.now() - 106 * 60000).toISOString(),
          ended_at: new Date(Date.now() - 61 * 60000).toISOString(),
          focus_seconds: 2700,
          pomodoros_done: 1,
          flow_extensions: 0,
          goal: "需求梳理",
          pause_count: 0,
        },
        {
          id: 2,
          started_at: new Date(Date.now() - 60 * 60000).toISOString(),
          ended_at: new Date(Date.now() - 11 * 60000).toISOString(),
          focus_seconds: 2940,
          pomodoros_done: 1,
          flow_extensions: 1,
          goal: "原型设计",
          pause_count: 1,
        },
      ];
      report.value = {
        stats: {},
        ai_comment:
          "示例点评：今天的两段投入都有收获。给高效时段留出完整空间，也允许自己在疲惫时放慢节奏。\n\n- 明天开始前，先写下一个具体的小目标。\n- 每完成一段专注，起身活动、喝一口水。",
      };
    }
    loading.value = false;
    return;
  }
  const results = await Promise.allSettled([
    request<FocusSession[]>(
      `/api/focus/sessions?from=${date.value}&to=${date.value}`,
      { signal: controller.signal },
    ),
    request<Timeline>(`/api/timeline?date=${date.value}`, {
      signal: controller.signal,
    }),
    request<DailyReport>(`/api/reports/daily?date=${date.value}`, {
      signal: controller.signal,
    }),
  ]);
  if (stamp !== generation) return;
  const [sessionResult, timelineResult, reportResult] = results;
  if (sessionResult.status === "fulfilled")
    sessions.value = sessionResult.value;
  if (timelineResult.status === "fulfilled")
    timeline.value = timelineResult.value;
  if (reportResult.status === "fulfilled") report.value = reportResult.value;
  for (const result of results)
    if (result.status === "rejected") {
      if (result.reason instanceof ApiError && result.reason.status === 503)
        unavailable.value = true;
      else if (result.reason?.name !== "AbortError")
        error.value =
          result.reason instanceof Error
            ? result.reason.message
            : "数据加载失败。";
    }
  loading.value = false;
}
watch(
  date,
  () => {
    if (date.value) void load();
  },
  { immediate: true },
);
onBeforeUnmount(() => {
  generation++;
  controller?.abort();
});
const total = computed(() =>
  sessions.value.reduce((sum, session) => sum + session.focus_seconds, 0),
);
const pomodoros = computed(() =>
  sessions.value.reduce((sum, session) => sum + session.pomodoros_done, 0),
);
const flows = computed(() =>
  sessions.value.reduce((sum, session) => sum + session.flow_extensions, 0),
);
const timeLabel = (value: string) =>
  new Date(value).toLocaleTimeString("zh-CN", {
    hour: "2-digit",
    minute: "2-digit",
    timeZone: "Asia/Shanghai",
  });
const base = {
  tooltip: { trigger: "axis" },
  grid: { left: 42, right: 20, top: 18, bottom: 30 },
  yAxis: {
    type: "value",
    splitLine: { lineStyle: { color: "#eef0ea" } },
    axisLabel: { color: "#68746a" },
  },
};
const focusChart = computed(() => ({
  ...base,
  color: ["#6a8e69"],
  xAxis: {
    type: "category",
    data: sessions.value.map((s) => timeLabel(s.started_at)),
    axisLine: { show: false },
    axisTick: { show: false },
  },
  series: [
    {
      name: "专注分钟",
      type: "bar",
      barMaxWidth: 36,
      data: sessions.value.map((s) => Math.round(s.focus_seconds / 60)),
      itemStyle: { borderRadius: [5, 5, 0, 0] },
    },
  ],
}));
const fatigueChart = computed(() => ({
  tooltip: { trigger: "item" },
  color: ["#c3d3a7", "#eacb8b", "#d99b7e"],
  series: [
    {
      type: "pie",
      radius: ["50%", "73%"],
      center: ["50%", "50%"],
      label: { formatter: "{b}: {c}" },
      data: [1, 2, 3].map((level) => ({
        name: `L${level}`,
        value:
          timeline.value?.fatigue_events.filter(
            (event) => event.level === level,
          ).length || 0,
      })),
    },
  ],
}));
const envChart = computed(() => ({
  ...base,
  color: ["#bc9567", "#7ba1a9"],
  legend: { bottom: 0 },
  grid: { left: 35, right: 35, top: 20, bottom: 60 },
  xAxis: {
    type: "category",
    data: timeline.value?.env.map((row) => timeLabel(row.at)) || [],
    axisLabel: { hideOverlap: true },
    axisLine: { show: false },
    axisTick: { show: false },
  },
  yAxis: [
    {
      type: "value",
      name: "°C",
      scale: true,
      splitLine: { lineStyle: { color: "#eef0ea" } },
    },
    { type: "value", name: "%", scale: true, splitLine: { show: false } },
  ],
  series: [
    {
      name: "温度",
      type: "line",
      smooth: true,
      data: timeline.value?.env.map((row) => row.temperature) || [],
    },
    {
      name: "湿度",
      type: "line",
      smooth: true,
      yAxisIndex: 1,
      data: timeline.value?.env.map((row) => row.humidity) || [],
    },
  ],
}));
async function generate() {
  generating.value = true;
  try {
    if (!app.preview)
      await post("/api/reports/daily/generate", { date: date.value });
    await load();
    ElMessage.success(app.preview ? "示例报告已刷新。" : "报告已重新生成。");
  } catch (err) {
    ElMessage.error(err instanceof Error ? err.message : "生成失败。");
  } finally {
    generating.value = false;
  }
}
function exportReport() {
  download(
    `桌伴复盘-${date.value}.md`,
    `# 桌伴每日复盘 · ${date.value}\n\n${app.preview ? "> 界面预览，以下为示例数据。\n\n" : ""}专注：${Math.round(total.value / 60)} 分钟\n番茄：${pomodoros.value} 段\n心流顺延：${flows.value} 次\n\n${report.value?.ai_comment || "AI 日报服务尚不可用。"}\n\n统计口径：按北京时间的会话开始日期归集。`,
  );
}
</script>
<template>
  <div class="page-enter">
    <div class="page-heading">
      <div>
        <h1>每日复盘</h1>
        <p>按日期查看专注统计、疲劳记录与环境变化。</p>
      </div>
      <div class="inline-actions">
        <el-date-picker
          v-model="date"
          aria-label="选择复盘日期"
          type="date"
          value-format="YYYY-MM-DD"
          :clearable="false"
          :editable="false"
        /><button
          class="icon-button"
          aria-label="导出每日复盘"
          :disabled="loading || (!sessions.length && !report)"
          @click="exportReport"
        >
          <Icon name="download" />
        </button>
      </div>
    </div>
    <el-alert v-if="error" :title="error" type="error" :closable="false" />
    <div v-if="error" class="inline-actions retry-row">
      <el-button @click="load">重新加载</el-button>
    </div>
    <el-alert
      v-if="unavailable"
      title="健康报告服务尚未接入。下方保留专注会话的真实统计，AI 点评与健康时序等待服务就绪。"
      type="info"
      :closable="false"
    />
    <div v-loading="loading" class="report-content">
      <div class="report-metrics">
        <section class="card">
          <Icon name="clock" /><span>累计专注</span
          ><strong>{{ Math.round(total / 60) }}<small>分钟</small></strong>
        </section>
        <section class="card">
          <Icon name="check" /><span>完成番茄</span
          ><strong>{{ pomodoros }}<small>段</small></strong>
        </section>
        <section class="card">
          <Icon name="leaf" /><span>心流顺延</span
          ><strong>{{ flows }}<small>次</small></strong>
        </section>
        <section class="card">
          <Icon name="desk" /><span>专注会话</span
          ><strong>{{ sessions.length }}<small>次</small></strong>
        </section>
      </div>
      <section class="card report-comment">
        <span class="assistant-orb small"><Icon name="leaf" :size="23" /></span>
        <div>
          <h2>复盘建议</h2>
          <Markdown v-if="report?.ai_comment" :text="report.ai_comment" />
          <p v-else class="muted">
            {{
              unavailable
                ? "等健康服务接入后，这里会生成基于真实统计的点评与建议。"
                : "这一天还没有点评。积累一些专注记录，再生成报告吧。"
            }}
          </p>
        </div>
        <el-button
          :disabled="unavailable || loading || !sessions.length"
          :loading="generating"
          @click="generate"
          >重新生成</el-button
        >
      </section>
      <div class="report-charts">
        <section class="card">
          <h3>专注时长</h3>
          <p class="muted">每次会话的专注分钟数</p>
          <Chart
            v-if="sessions.length"
            :option="focusChart"
            label="各专注会话的累计时长"
            :height="220"
          />
          <div v-else class="empty-chart">这一天，还没有专注记录。</div>
        </section>
        <section class="card">
          <h3>疲劳提醒</h3>
          <p class="muted">不同等级的疲劳事件</p>
          <Chart
            v-if="timeline?.fatigue_events.length"
            :option="fatigueChart"
            label="疲劳等级事件分布"
            :height="220"
          />
          <div v-else class="empty-chart">
            {{
              unavailable
                ? "等待健康引擎提供疲劳记录。"
                : "这一天没有疲劳提醒记录。"
            }}
          </div>
        </section>
        <section class="card">
          <h3>环境变化</h3>
          <p class="muted">工位温度与湿度变化</p>
          <Chart
            v-if="timeline?.env.length"
            :option="envChart"
            label="工位温湿度变化趋势"
            :height="220"
          />
          <div v-else class="empty-chart">等待温湿度历史记录。</div>
        </section>
      </div>
    </div>
    <p class="page-note">
      {{
        app.preview ? "预览使用示例数据。" : ""
      }}统计按北京时间的会话开始日期归集，跨日会话的分日口径需由后端报告服务统一。
    </p>
  </div>
</template>
