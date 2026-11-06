<script setup lang="ts">
import {
  computed,
  defineAsyncComponent,
  onBeforeUnmount,
  onMounted,
  ref,
} from "vue";
import { ElMessage } from "element-plus";
import zhCn from "element-plus/es/locale/lang/zh-cn";
import { useApp } from "./stores/app";
import Login from "./views/Login.vue";
import Icon from "./components/Icon.vue";
const Markdown = defineAsyncComponent(
  () => import("./components/Markdown.vue"),
);
const app = useApp(),
  notifications = ref(false),
  mobileMenu = ref(false);
const demoOnly = import.meta.env.VITE_DEMO_ONLY === "true";
function leaveOrReset() {
  if (demoOnly) app.enterPreview();
  else app.logout();
}
const nav = [
  { key: "dashboard", label: "我的工位", icon: "grid" },
  { key: "workspaces", label: "工作台", icon: "desk" },
  { key: "chat", label: "桌伴助手", icon: "chat" },
  { key: "reports", label: "每日复盘", icon: "chart" },
  { key: "demo", label: "演示沙盒", icon: "flask" },
  { key: "settings", label: "偏好设置", icon: "settings" },
];
const views = {
  dashboard: defineAsyncComponent(() => import("./views/Dashboard.vue")),
  workspaces: defineAsyncComponent(() => import("./views/Workspaces.vue")),
  chat: defineAsyncComponent(() => import("./views/Chat.vue")),
  reports: defineAsyncComponent(() => import("./views/Reports.vue")),
  demo: defineAsyncComponent(() => import("./views/Demo.vue")),
  settings: defineAsyncComponent(() => import("./views/Settings.vue")),
};
type Page = keyof typeof views;
const page = ref<Page>("dashboard");
function hashChanged() {
  const hash = location.hash.slice(1);
  page.value = nav.some((item) => item.key === hash)
    ? (hash as Page)
    : "dashboard";
}
function navigate(key: string) {
  location.hash = key;
  window.scrollTo({ top: 0, behavior: "smooth" });
}
const dateLabel = new Intl.DateTimeFormat("zh-CN", {
  timeZone: "Asia/Shanghai",
  month: "long",
  day: "numeric",
  weekday: "long",
}).format(new Date());
const connectionLabel = computed(() =>
  app.preview
    ? "界面预览"
    : {
        connecting: "连接中",
        online: "实时同步中",
        reconnecting: "正在重新连接",
        offline: "连接已断开",
      }[app.connection],
);
function expired() {
  if (app.user) {
    app.logout();
    ElMessage.warning("登录已过期，请重新登录。");
  }
}
onMounted(() => {
  hashChanged();
  window.addEventListener("hashchange", hashChanged);
  window.addEventListener("deskmate:unauthorized", expired);
  if (demoOnly || new URLSearchParams(location.search).get("preview") === "1")
    app.enterPreview();
  else void app.restore();
});
onBeforeUnmount(() => {
  window.removeEventListener("hashchange", hashChanged);
  window.removeEventListener("deskmate:unauthorized", expired);
});
</script>
<template>
  <el-config-provider :locale="zhCn">
    <Login v-if="!app.user" />
    <div v-else class="app-layout">
      <aside class="sidebar">
        <a class="brand" href="#dashboard"
          ><span class="brand-mark"><Icon name="desk" :size="26" /></span
          ><span class="brand-wordmark"
            >DeskMate<span class="brand-cn">桌伴</span></span
          ></a
        >
        <div class="sidebar-section-label">工作空间</div>
        <nav aria-label="主导航">
          <a
            v-for="item in nav"
            :key="item.key"
            :href="`#${item.key}`"
            :class="{ active: page === item.key }"
            :aria-current="page === item.key ? 'page' : undefined"
            :title="item.label"
            ><Icon :name="item.icon" :size="19" /><span>{{
              item.label
            }}</span></a
          >
        </nav>
        <div class="sidebar-bottom">
          <div class="sidebar-privacy">
            <Icon name="shield" :size="18" />
            <div>
              <strong>隐私保护</strong>
              <p>不使用摄像头<br />键鼠仅统计次数</p>
            </div>
          </div>
          <button
            class="account"
            @click="leaveOrReset"
            :title="demoOnly ? '重置演示' : '退出登录'"
          >
            <span class="avatar">{{
              app.user.username.slice(0, 1).toUpperCase()
            }}</span
            ><span
              ><strong>{{
                app.preview ? "预览体验者" : app.user.username
              }}</strong
              ><small>{{
                app.preview
                  ? "示例数据"
                  : app.user.is_demo
                    ? "演示账号"
                    : "我的账号"
              }}</small></span
            ><Icon name="logout" :size="17" />
          </button>
        </div>
      </aside>
      <div class="main-column">
        <header class="topbar">
          <div class="breadcrumb">
            我的空间 <Icon name="chevron" :size="13" /><strong>{{
              nav.find((item) => item.key === page)?.label
            }}</strong>
          </div>
          <div class="topbar-right">
            <span class="date-label">{{ dateLabel }}</span
            ><span class="connection" :class="{ online: app.connected }"
              ><span class="pulse-dot" />{{ connectionLabel }}</span
            ><button
              class="icon-button notification-trigger"
              aria-label="查看通知"
              @click="notifications = true"
            >
              <Icon name="bell" :size="20" /><i v-if="app.notices.length" />
            </button>
            <button
              class="icon-button mobile-logout"
              :aria-label="demoOnly ? '重置演示' : '退出登录'"
              @click="leaveOrReset"
            >
              <Icon name="logout" :size="17" />
            </button>
          </div>
        </header>
        <div v-if="app.preview" class="mode-banner">
          <Icon name="flask" :size="15" /><span>{{
            demoOnly
              ? "在线 Demo · 示例数据，不连接真实设备或模型"
              : "示例环境 · 操作仅在本页模拟"
          }}</span
          ><button @click="leaveOrReset">
            {{ demoOnly ? "重置演示" : "连接服务" }}
            <Icon name="arrow" :size="14" />
          </button>
        </div>
        <div
          v-else-if="!app.connected && app.state"
          class="mode-banner warning"
          role="status"
        >
          <Icon name="info" :size="15" /><span
            >连接正在恢复，显示上次收到的状态。设备控制暂不可用。</span
          >
        </div>
        <div v-else-if="app.state?.demo_mode" class="mode-banner">
          <Icon name="flask" :size="15" /><span
            >虚拟设备环境 · 当前操作由后端模拟，现场硬件不受影响。</span
          >
        </div>
        <main id="main-content" class="main-content">
          <div v-if="app.loading" class="loading-page" role="status">
            <Icon name="refresh" :size="28" />
            <h2>正在为你准备工位…</h2>
          </div>
          <div v-else-if="app.error" class="card load-error" role="alert">
            <Icon name="info" :size="35" />
            <h2>工位暂时还没连上</h2>
            <p>{{ app.error }}</p>
            <el-button type="primary" @click="app.load">重新连接</el-button
            ><el-button @click="app.logout()">返回登录</el-button>
          </div>
          <component
            :is="views[page]"
            v-else-if="app.state"
            @navigate="navigate"
          />
        </main>
        <footer class="app-footer">
          <span>DeskMate 桌伴</span
          ><span><Icon name="shield" :size="12" /> 无摄像头 · 隐私优先</span>
        </footer>
      </div>
      <nav class="mobile-nav" aria-label="手机导航">
        <a
          v-for="item in nav.slice(0, 4)"
          :key="item.key"
          :href="`#${item.key}`"
          :class="{ active: page === item.key }"
          :aria-current="page === item.key ? 'page' : undefined"
          ><Icon :name="item.icon" :size="20" /><span>{{
            item.key === "dashboard"
              ? "工位"
              : item.key === "workspaces"
                ? "工作台"
                : item.key === "chat"
                  ? "助手"
                  : "复盘"
          }}</span></a
        ><button
          :class="{ active: ['demo', 'settings'].includes(page) }"
          @click="mobileMenu = true"
        >
          <Icon name="grid" :size="20" /><span>更多</span>
        </button>
      </nav>
      <el-drawer
        v-model="mobileMenu"
        title="更多功能"
        direction="btt"
        size="auto"
        ><div class="mobile-menu-items">
          <button
            v-for="item in nav.slice(4)"
            :key="item.key"
            @click="
              navigate(item.key);
              mobileMenu = false;
            "
          >
            <Icon :name="item.icon" :size="20" />{{ item.label
            }}<Icon name="chevron" :size="16" /></button
          ><button
            @click="
              leaveOrReset();
              mobileMenu = false;
            "
          >
            <Icon :name="demoOnly ? 'refresh' : 'logout'" :size="20" />{{
              demoOnly ? "重置演示数据" : "退出登录"
            }}
          </button>
        </div></el-drawer
      >
      <el-drawer v-model="notifications" title="桌伴的消息" size="380px"
        ><div v-if="!app.notices.length" class="empty-chart">
          暂无通知。设备执行和关怀提醒会显示在这里。
        </div>
        <div
          v-for="notice in app.notices"
          :key="notice.id"
          class="notification-item"
        >
          <span class="subtle-tag">{{
            notice.level === "info"
              ? "消息"
              : notice.level === "warn"
                ? "提醒"
                : "建议休息"
          }}</span>
          <h3>{{ notice.title }}</h3>
          <p>{{ notice.text }}</p>
          <small>{{ new Date(notice.at).toLocaleString("zh-CN") }}</small>
        </div></el-drawer
      >
      <el-drawer
        :model-value="Boolean(app.assistance)"
        :title="app.assistance?.title || '助手结果'"
        size="min(580px, 100vw)"
        @close="app.assistance = null"
        ><Markdown :text="app.assistance?.markdown || ''"
      /></el-drawer>
      <el-dialog
        v-model="app.restOverlay"
        title="先照顾一下自己吧"
        width="440px"
        :show-close="false"
        :close-on-click-modal="false"
        :close-on-press-escape="false"
        ><div class="rest-content">
          <span class="assistant-orb"><Icon name="leaf" :size="36" /></span>
          <h2>休息提醒</h2>
          <p>建议暂时离开屏幕，起身活动。</p>
          <p v-if="app.state?.focus.state === 'short_break'" class="muted">
            当前正在休息阶段，时钟状态可在首页查看。
          </p>
        </div>
        <template #footer
          ><el-button @click="app.restOverlay = false">好的，休息一会</el-button
          ><el-button :disabled="!app.connected" @click="app.skipRest"
            >这次跳过</el-button
          ></template
        ></el-dialog
      >
    </div>
  </el-config-provider>
</template>
