<script setup lang="ts">
import { computed, onBeforeUnmount, ref, watch } from "vue";
import { ElMessageBox } from "element-plus";
import { useApp } from "../stores/app";
import Chart from "../components/Chart.vue";
import Icon from "../components/Icon.vue";
const app = useApp(),
  now = ref(Date.now()),
  startOpen = ref(false),
  selected = ref<number>(),
  goal = ref(""),
  minutes = ref(45);
const tick = setInterval(() => {
  now.value = Date.now();
}, 1000);
onBeforeUnmount(() => clearInterval(tick));
const focus = computed(() => app.state!.focus);
watch(
  () => focus.value.phase_ends_at,
  () => {
    now.value = Date.now();
  },
);
const remaining = computed(() => {
  if (focus.value.state === "idle") return 0;
  if (focus.value.state === "paused") return focus.value.remaining_seconds;
  return focus.value.phase_ends_at
    ? Math.max(
        0,
        Math.ceil((Date.parse(focus.value.phase_ends_at) - now.value) / 1000),
      )
    : focus.value.remaining_seconds;
});
const clock = computed(() =>
  focus.value.state === "idle"
    ? "准备好了吗"
    : `${String(Math.floor(remaining.value / 60)).padStart(2, "0")}:${String(remaining.value % 60).padStart(2, "0")}`,
);
const status = computed(
  () =>
    ({
      idle: "未开始",
      focusing: "正在专注",
      paused: "离座暂停",
      short_break: "休息时间",
    })[focus.value.state],
);
const ratio = computed(() => {
  const duration =
    focus.value.phase_ends_at && focus.value.phase_started_at
      ? (Date.parse(focus.value.phase_ends_at) -
          Date.parse(focus.value.phase_started_at)) /
        1000
      : 2700;
  return Math.min(1, Math.max(0, remaining.value / Math.max(1, duration)));
});
const onlineCount = computed(
  () =>
    Object.values(app.state!.devices).filter((value) => value?.online).length,
);
const activity = computed(() => app.timeline?.inputs || []);
const chartOption = computed(() => ({
  color: ["#4a7d60"],
  tooltip: {
    trigger: "axis",
    backgroundColor: "#fff",
    borderColor: "#e6e9e0",
    textStyle: { color: "#354339" },
  },
  grid: { left: 40, right: 14, top: 20, bottom: 28 },
  xAxis: {
    type: "category",
    data: activity.value.map((row) =>
      new Date(row.minute).toLocaleTimeString("zh-CN", {
        hour: "2-digit",
        minute: "2-digit",
        timeZone: "Asia/Shanghai",
      }),
    ),
    boundaryGap: false,
    axisLine: { show: false },
    axisTick: { show: false },
    axisLabel: { color: "#68746a", fontSize: 12, hideOverlap: true },
  },
  yAxis: {
    type: "value",
    axisLabel: { color: "#68746a", fontSize: 12 },
    splitLine: { lineStyle: { color: "#eef0ea", type: "dashed" } },
  },
  series: [
    {
      type: "line",
      smooth: 0.32,
      symbol: "none",
      data: activity.value.map((row) => row.activity_rate),
      lineStyle: { width: 2.5 },
      areaStyle: {
        color: {
          type: "linear",
          x: 0,
          y: 0,
          x2: 0,
          y2: 1,
          colorStops: [
            { offset: 0, color: "#c3d7bc88" },
            { offset: 1, color: "#eaf1e300" },
          ],
        },
      },
    },
  ],
}));
const reasons: Record<string, string> = {
  long_presence: "连续在座较久",
  typing_rate_drop: "工作节奏下降",
  idle_presence: "在座但较少活动",
  hot_room: "环境偏热",
  late_night: "夜间工作",
};
function openStart() {
  selected.value = app.workspaces[0]?.id;
  minutes.value = app.workspaces[0]?.focus_minutes || 45;
  startOpen.value = true;
}
async function start() {
  if (
    selected.value &&
    (await app.startFocus(selected.value, goal.value, minutes.value))
  )
    startOpen.value = false;
}
async function stop() {
  try {
    await ElMessageBox.confirm(
      "结束后，本次专注会保存到会话记录。",
      "结束这段专注？",
      {
        confirmButtonText: "结束并保存",
        cancelButtonText: "继续专注",
        type: "info",
      },
    );
    await app.stopFocus();
  } catch {
    /* 用户取消 */
  }
}

const disabled = computed(() => !app.connected || app.busy);
const workspaceTitle = computed(() =>
  focus.value.state === "idle"
    ? "选择工作台，开始专注"
    : focus.value.workspace_name || "专注会话",
);
const lastSync = computed(
  () =>
    app.state?.current_input_stats?.minute ||
    app.state?.devices.climate?.updated_at,
);
</script>
<template>
  <div v-if="app.state" class="dashboard">
    <div class="page-heading">
      <div>
        <h1>我的工位</h1>
        <p>管理当前任务、专注计时与桌面设备。</p>
      </div>
      <button class="button secondary" @click="$emit('navigate', 'workspaces')">
        <Icon name="desk" :size="18" /> 管理工作台
      </button>
    </div>
    <div class="workspace-overview">
      <section class="card focus-panel" aria-label="当前专注会话">
        <div class="card-top">
          <span class="field-label">当前工作台</span
          ><span class="state-label" :class="focus.state"
            ><i />{{ status }}</span
          >
        </div>
        <h2>{{ workspaceTitle }}</h2>
        <p class="focus-goal">
          {{
            focus.state === "idle"
              ? "灯光与启动项将按工作台配置准备。"
              : focus.goal || "尚未填写本次目标"
          }}
        </p>
        <div class="session-row">
          <div class="session-time">
            <span class="field-label">{{
              focus.state === "idle"
                ? "默认专注时长"
                : focus.state === "paused"
                  ? "暂停时剩余"
                  : "剩余时间"
            }}</span
            ><strong>{{
              focus.state === "idle"
                ? `${app.workspaces[0]?.focus_minutes || 45}:00`
                : clock
            }}</strong>
          </div>
          <div class="session-facts">
            <span
              >今日专注<strong
                >{{ Math.floor(focus.focus_seconds_today / 60)
                }}<small>分钟</small></strong
              ></span
            ><span
              >当前段数<strong>{{
                focus.state === "idle"
                  ? "—"
                  : String(focus.pomodoro_index).padStart(2, "0")
              }}</strong></span
            >
          </div>
        </div>
        <div
          class="session-progress"
          role="progressbar"
          :aria-valuenow="
            Math.round((focus.state === 'idle' ? 0 : 1 - ratio) * 100)
          "
          aria-valuemin="0"
          aria-valuemax="100"
          aria-label="本阶段专注进度"
        >
          <span
            :style="{
              width: `${(focus.state === 'idle' ? 0 : 1 - ratio) * 100}%`,
            }"
          />
        </div>
        <div class="session-footer">
          <span v-if="focus.state === 'paused'" class="session-note"
            >回座后由系统恢复计时</span
          ><span v-else-if="app.state.fatigue.in_flow" class="session-note"
            >心流保护中 · 已顺延 {{ focus.flow_extensions }} 次</span
          ><span v-else class="session-note">{{
            app.preview
              ? "示例会话 · 可调整设备和模拟离座"
              : "计时以服务端状态为准"
          }}</span>
          <div class="session-actions">
            <button
              v-if="focus.state === 'idle'"
              class="button primary"
              :disabled="disabled || !app.workspaces.length"
              @click="openStart"
            >
              <Icon name="play" :size="16" /> 开始专注</button
            ><button
              v-else
              class="button primary"
              :disabled="disabled"
              @click="stop"
            >
              <Icon name="stop" :size="16" /> 结束专注</button
            ><button
              class="button secondary"
              @click="$emit('navigate', 'chat')"
            >
              <Icon name="chat" :size="17" /> 打开助手
            </button>
          </div>
        </div>
      </section>
      <aside class="card execution-panel">
        <div class="card-top">
          <h2>最近执行</h2>
          <span class="subtle-tag">{{
            app.preview ? "示例环境" : "已确认结果"
          }}</span>
        </div>
        <ol v-if="app.notices.length" class="execution-list">
          <li v-for="notice in app.notices.slice(0, 3)" :key="notice.id">
            <span class="execution-dot" :class="notice.level" />
            <div>
              <strong>{{ notice.title }}</strong>
              <p>{{ notice.text }}</p>
              <time>{{
                new Date(notice.at).toLocaleTimeString("zh-CN", {
                  hour: "2-digit",
                  minute: "2-digit",
                  timeZone: "Asia/Shanghai",
                })
              }}</time>
            </div>
          </li>
        </ol>
        <div v-else class="execution-empty">
          <Icon name="check" :size="26" />
          <h3>暂无执行记录</h3>
          <p>调整设备或开始专注后，这里会显示确认结果。</p>
        </div>
        <div class="execution-foot">
          <span
            class="presence-dot"
            :class="{ absent: !app.state.presence.present }"
          />{{ app.state.presence.present ? "有人在座" : "已离座"
          }}<span class="execution-separator">·</span>{{ onlineCount }} / 6
          台设备在线
        </div>
      </aside>
    </div>
    <div class="mobile-quick-controls">
      <button
        class="quick-lamp"
        :disabled="disabled || !app.state.devices.lamp?.online"
        @click="app.command('lamp', { on: !app.state.devices.lamp?.on })"
      >
        <Icon name="lamp" :size="20" /><span
          >台灯<strong>{{
            app.state.devices.lamp?.on ? "已开启" : "已关闭"
          }}</strong></span
        ><span
          class="quick-switch"
          :class="{ on: app.state.devices.lamp?.on }"
        />
      </button>
      <div class="quick-ac">
        <Icon name="snow" :size="18" /><button
          aria-label="快捷空调降低一度"
          :disabled="
            disabled ||
            !app.state.devices.ac?.online ||
            app.state.devices.ac.temperature <= 16
          "
          @click="
            app.command('ac', {
              temperature: app.state.devices.ac!.temperature - 1,
            })
          "
        >
          −</button
        ><strong
          >{{ app.state.devices.ac?.temperature ?? "—" }}°<small
            >推测</small
          ></strong
        ><button
          aria-label="快捷空调升高一度"
          :disabled="
            disabled ||
            !app.state.devices.ac?.online ||
            app.state.devices.ac.temperature >= 30
          "
          @click="
            app.command('ac', {
              temperature: app.state.devices.ac!.temperature + 1,
            })
          "
        >
          +
        </button>
      </div>
    </div>
    <div v-if="app.notices[0]" class="mobile-last-action" role="status">
      <Icon name="check" :size="15" /><strong>{{ app.notices[0].title }}</strong
      ><span>{{ app.notices[0].text }}</span>
    </div>
    <section class="care-strip">
      <span class="care-icon"><Icon name="leaf" :size="20" /></span>
      <div>
        <strong>专注关怀</strong
        ><span v-if="app.healthAvailable"
          >{{ app.preview ? "示例疲劳指数" : "疲劳指数" }}
          {{ Math.round(app.state.fatigue.score) }} / 100<span
            v-if="app.state.fatigue.reasons.length"
          >
            ·
            {{
              app.state.fatigue.reasons
                .map((reason) => reasons[reason] || reason)
                .join("、")
            }}</span
          ></span
        ><span v-else>健康服务准备中，暂不提供疲劳与心流判断。</span>
      </div>
      <button class="text-link" @click="$emit('navigate', 'reports')">
        查看复盘 <Icon name="arrow" :size="16" />
      </button>
    </section>
    <div class="section-title">
      <h2>设备控制</h2>
      <span>{{
        app.preview
          ? "本地示例状态"
          : app.state.demo_mode
            ? "后端虚拟设备状态"
            : "现场设备状态"
      }}</span>
    </div>
    <div class="device-grid">
      <section class="card device-card">
        <div class="device-head">
          <span class="device-icon"><Icon name="lamp" :size="23" /></span>
          <div>
            <h3>专注台灯</h3>
            <p>
              {{
                app.state.devices.lamp?.online
                  ? app.state.devices.lamp.on
                    ? "已开启"
                    : "已关闭"
                  : "离线"
              }}
            </p>
          </div>
          <el-switch
            aria-label="台灯开关"
            :model-value="app.state.devices.lamp?.on || false"
            :disabled="disabled || !app.state.devices.lamp?.online"
            @change="(value: unknown) => app.command('lamp', { on: value })"
          />
        </div>
        <div class="slider-label">
          <span>亮度</span
          ><strong
            >{{ app.state.devices.lamp?.brightness ?? "—"
            }}<small>%</small></strong
          >
        </div>
        <el-slider
          aria-label="台灯亮度"
          :min="1"
          :max="100"
          :model-value="app.state.devices.lamp?.brightness || 1"
          :disabled="disabled || !app.state.devices.lamp?.online"
          @change="
            (value: unknown) => app.command('lamp', { brightness: value })
          "
        />
        <div class="slider-label">
          <span>色温</span
          ><strong
            >{{ app.state.devices.lamp?.color_temp ?? "—"
            }}<small>K</small></strong
          >
        </div>
        <el-slider
          class="warm-slider"
          aria-label="台灯色温"
          :min="2500"
          :max="4800"
          :step="100"
          :model-value="app.state.devices.lamp?.color_temp || 2500"
          :disabled="disabled || !app.state.devices.lamp?.online"
          @change="
            (value: unknown) => app.command('lamp', { color_temp: value })
          "
        />
        <div class="device-bottom">
          <span>暖光 2500K</span><span>冷光 4800K</span>
        </div>
      </section>
      <section class="card device-card">
        <div class="device-head">
          <span class="device-icon"><Icon name="snow" :size="23" /></span>
          <div>
            <h3>空调</h3>
            <p>红外控制 · 推测状态</p>
          </div>
          <el-switch
            aria-label="空调开关"
            :model-value="app.state.devices.ac?.on || false"
            :disabled="disabled || !app.state.devices.ac?.online"
            @change="(value: unknown) => app.command('ac', { on: value })"
          />
        </div>
        <div class="temperature-control">
          <button
            aria-label="空调降低一度"
            :disabled="
              disabled ||
              !app.state.devices.ac?.online ||
              app.state.devices.ac.temperature <= 16
            "
            @click="
              app.command('ac', {
                temperature: app.state.devices.ac!.temperature - 1,
              })
            "
          >
            −</button
          ><strong
            >{{ app.state.devices.ac?.temperature ?? "—"
            }}<small>°C</small></strong
          ><button
            aria-label="空调升高一度"
            :disabled="
              disabled ||
              !app.state.devices.ac?.online ||
              app.state.devices.ac.temperature >= 30
            "
            @click="
              app.command('ac', {
                temperature: app.state.devices.ac!.temperature + 1,
              })
            "
          >
            +
          </button>
        </div>
        <el-select
          aria-label="空调模式"
          :model-value="app.state.devices.ac?.mode"
          :disabled="disabled || !app.state.devices.ac?.online"
          @change="(value: unknown) => app.command('ac', { mode: value })"
          ><el-option label="制冷" value="cool" /><el-option
            label="制热"
            value="heat" /><el-option label="送风" value="fan" /><el-option
            label="除湿"
            value="dry"
        /></el-select>
        <p class="device-hint">显示最后一次指令，非设备回读。</p>
      </section>
      <section class="card environment-card">
        <div class="device-head">
          <span class="device-icon"><Icon name="temp" :size="23" /></span>
          <div>
            <h3>环境与插座</h3>
            <p>
              {{
                app.state.devices.climate?.online
                  ? "温湿度计在线"
                  : "传感器离线"
              }}
            </p>
          </div>
        </div>
        <div class="environment-values">
          <div>
            <span>室温</span
            ><strong
              >{{ app.state.devices.climate?.temperature ?? "—"
              }}<small>°C</small></strong
            >
          </div>
          <div>
            <span>湿度</span
            ><strong
              >{{ app.state.devices.climate?.humidity ?? "—"
              }}<small>%</small></strong
            >
          </div>
        </div>
        <div class="plug-row">
          <Icon name="plug" :size="20" /><span
            >桌面插座<small
              >{{ app.state.devices.plug?.power_w ?? "—" }} W</small
            ></span
          ><el-switch
            aria-label="桌面插座开关"
            :model-value="app.state.devices.plug?.on || false"
            :disabled="disabled || !app.state.devices.plug?.online"
            @change="(value: unknown) => app.command('plug', { on: value })"
          />
        </div>
      </section>
    </div>
    <section class="card activity-card">
      <div class="card-top">
        <div>
          <h2>工作节奏</h2>
          <p class="muted">
            每分钟键鼠活动率 · {{ app.preview ? "示例曲线" : "设备上报" }}
          </p>
        </div>
        <span class="chart-legend"><i />活动率</span>
      </div>
      <Chart
        v-if="activity.length"
        :option="chartOption"
        label="每分钟工作活动率曲线"
        :height="220"
      />
      <div v-else class="empty-chart">
        尚未收到活动数据。连接后，设备每分钟上报一次。
      </div>
      <div class="chart-footnote">
        <span>个人基线暂不可用</span
        ><span v-if="lastSync"
          >最近数据
          {{
            new Date(lastSync).toLocaleTimeString("zh-CN", {
              hour: "2-digit",
              minute: "2-digit",
              timeZone: "Asia/Shanghai",
            })
          }}</span
        >
      </div>
    </section>
    <el-dialog v-model="startOpen" title="开始专注" width="460px"
      ><el-form label-position="top" @submit.prevent="start"
        ><el-form-item label="工作台"
          ><el-select
            v-model="selected"
            aria-label="选择工作台"
            @change="
              (value: unknown) =>
                (minutes =
                  app.workspaces.find((w) => w.id === value)?.focus_minutes ||
                  45)
            "
            ><el-option
              v-for="workspace in app.workspaces"
              :key="workspace.id"
              :label="workspace.name"
              :value="workspace.id" /></el-select></el-form-item
        ><el-form-item label="本次目标"
          ><el-input
            v-model="goal"
            placeholder="例如：完成需求分析"
            :maxlength="500" /></el-form-item
        ><el-form-item label="专注时长（分钟）"
          ><el-input-number
            v-model="minutes"
            :min="1"
            :max="240" /></el-form-item
      ></el-form>
      <p class="muted">按工作台配置准备灯光和启动项。</p>
      <template #footer
        ><el-button @click="startOpen = false">取消</el-button
        ><el-button
          type="primary"
          :loading="app.busy"
          :disabled="!selected"
          @click="start"
          >开始专注</el-button
        ></template
      ></el-dialog
    >
  </div>
</template>
