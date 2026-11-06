<script setup lang="ts">
import { ref } from "vue";
import { useApp } from "../stores/app";
import Icon from "../components/Icon.vue";
const app = useApp(),
  rate = ref(120),
  temperature = ref(26.5),
  voice = ref("我要开始学习");
const emit = defineEmits<{ navigate: [page: string] }>();
async function runStep(number: string) {
  if (number === "01") {
    if (app.state?.focus.state !== "idle") emit("navigate", "dashboard");
    else if (app.workspaces[0])
      await app.startFocus(app.workspaces[0].id, "体验桌伴的一段专注");
  } else if (number === "02") {
    rate.value = 20;
    await app.inject("typing_rate", 20);
  } else emit("navigate", "reports");
}
const steps = [
  {
    number: "01",
    title: "准备工作台",
    copy: "准备灯光、启动项与专注时钟。",
    icon: "desk",
  },
  {
    number: "02",
    title: "改变工作节奏",
    copy: "改变打字速率、室温，观察状态更新。",
    icon: "leaf",
  },
  {
    number: "03",
    title: "查看每日复盘",
    copy: "查看会话统计，让投入留下记录。",
    icon: "chart",
  },
];
</script>
<template>
  <div class="page-enter">
    <div class="page-heading">
      <div>
        <h1>演示沙盒</h1>
        <p>模拟在座、锁屏和环境变化，观察状态更新。</p>
      </div>
      <span class="status-pill"
        ><span class="pulse-dot" />
        {{ app.preview ? "界面示例" : "虚拟设备环境" }}</span
      >
    </div>
    <el-alert
      v-if="!app.user?.is_demo"
      type="warning"
      title="演示控制台只向 demo 账号开放，请退出后使用演示账号登录。"
      :closable="false"
    /><template v-else
      ><div class="demo-steps">
        <article v-for="step in steps" :key="step.number" class="card">
          <div class="card-top">
            <span class="step-number">{{ step.number }}</span
            ><Icon :name="step.icon" :size="27" />
          </div>
          <h2>{{ step.title }}</h2>
          <p>{{ step.copy }}</p>
          <button
            class="text-link step-action"
            :disabled="
              app.busy ||
              !app.connected ||
              (step.number === '01' && !app.workspaces.length)
            "
            @click="runStep(step.number)"
          >
            {{
              step.number === "01"
                ? app.state?.focus.state === "idle"
                  ? "准备工作台"
                  : "查看当前工位"
                : step.number === "02"
                  ? "模拟节奏下降"
                  : "查看每日复盘"
            }}
            <Icon name="arrow" :size="14" />
          </button>
        </article>
      </div>
      <div class="demo-columns">
        <section class="card padded-card">
          <div class="section-kicker"><Icon name="user" /> 在座与锁屏</div>
          <h2>在座与专注状态</h2>
          <p class="muted">
            {{
              app.preview
                ? "本地示例展示暂停与恢复效果。"
                : "事件提交后，以后端规则引擎返回的状态为准。"
            }}
          </p>
          <div class="demo-actions">
            <button
              class="button secondary"
              :disabled="app.busy || !app.connected"
              @click="app.inject('motion')"
            >
              模拟回座</button
            ><button
              class="button secondary"
              :disabled="app.busy || !app.connected"
              @click="app.inject('leave')"
            >
              模拟离座</button
            ><button
              class="button secondary"
              :disabled="app.busy || !app.connected"
              @click="app.inject('lock', true)"
            >
              锁屏</button
            ><button
              class="button secondary"
              :disabled="app.busy || !app.connected"
              @click="app.inject('lock', false)"
            >
              解锁
            </button>
          </div>
          <div class="demo-live-state">
            <span>当前在座</span
            ><strong>{{
              app.state?.presence.present ? "有人在座" : "已离座"
            }}</strong
            ><span>专注时钟</span
            ><strong>{{
              {
                focusing: "专注中",
                idle: "未开始",
                paused: "已暂停",
                short_break: "休息中",
              }[app.state!.focus.state]
            }}</strong>
          </div>
        </section>
        <section class="card padded-card">
          <div class="section-kicker"><Icon name="chart" /> 节奏与环境</div>
          <div class="slider-label">
            <span>每分钟活动率</span><strong>{{ rate }}</strong>
          </div>
          <el-slider
            v-model="rate"
            aria-label="模拟每分钟活动率"
            :min="0"
            :max="240"
            :step="5"
          />
          <div class="device-bottom">
            <span>节奏放慢</span><span>持续投入</span>
          </div>
          <el-button
            :loading="app.busy"
            :disabled="!app.connected"
            @click="app.inject('typing_rate', rate)"
            >提交活动率</el-button
          >
          <div class="slider-label demo-temperature">
            <span>环境温度</span
            ><strong>{{ temperature }}<small>°C</small></strong>
          </div>
          <el-slider
            v-model="temperature"
            aria-label="模拟环境温度"
            :min="16"
            :max="35"
            :step="0.5"
          /><el-button
            :loading="app.busy"
            :disabled="!app.connected"
            @click="app.inject('temperature', temperature)"
            >提交环境温度</el-button
          >
        </section>
      </div>
      <section class="card padded-card voice-demo">
        <div>
          <div class="section-kicker"><Icon name="mic" /> 对小爱说</div>
          <h2>{{ app.preview ? "文本指令演示" : "模拟语音输入" }}</h2>
          <p class="muted">
            {{
              app.preview
                ? "在线 Demo 使用文本指令模拟设备变化，可在助手中查看结果。"
                : "模拟语音桥输入。简单设备口令走快速路径，复杂请求需要模型服务。"
            }}
          </p>
        </div>
        <el-button
          v-if="app.preview"
          type="primary"
          @click="emit('navigate', 'chat')"
          >打开助手</el-button
        >
        <form v-else @submit.prevent="app.inject('voice', voice)">
          <el-input
            v-model="voice"
            aria-label="模拟对小爱说的话"
            maxlength="4000"
            placeholder="例如：空调调到25度"
          /><el-button
            type="primary"
            native-type="submit"
            :loading="app.busy"
            :disabled="!app.connected || !voice.trim()"
            >模拟语音输入</el-button
          >
        </form>
      </section>
      <el-alert
        v-if="!app.healthAvailable"
        class="service-alert"
        title="健康引擎尚未接入：当前可以验证设备、离座和时钟；疲劳升级、心流保护与 AI 日报仍需接入健康模块。"
        type="info"
        :closable="false"
      />
      <p class="page-note">
        {{
          app.preview
            ? "本页为纯前端示例，不操作真实设备，也不运行健康算法。"
            : "演示账号由后端隔离，只操作虚拟设备。离座规则有确认时间，锁屏会立即触发。"
        }}
      </p></template
    >
  </div>
</template>
