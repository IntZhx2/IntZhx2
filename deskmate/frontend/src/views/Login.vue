<script setup lang="ts">
import { ref } from "vue";
import { useApp } from "../stores/app";
import Icon from "../components/Icon.vue";
import DeskScene from "../components/DeskScene.vue";
const app = useApp(),
  username = ref("demo"),
  password = ref(""),
  busy = ref(false),
  error = ref("");
async function submit() {
  if (!username.value.trim() || !password.value) {
    error.value = "请填写账号和密码。";
    return;
  }
  busy.value = true;
  error.value = "";
  try {
    await app.login(username.value.trim(), password.value);
    password.value = "";
  } catch (err) {
    error.value = err instanceof Error ? err.message : "登录失败，请重试。";
  } finally {
    busy.value = false;
  }
}
</script>
<template>
  <div class="login-layout">
    <section class="login-story">
      <a class="brand" href="#"
        ><span class="brand-mark"><Icon name="desk" :size="27" /></span
        ><span>DeskMate<span class="brand-cn">桌伴</span></span></a
      >
      <div class="login-copy">
        <h1>桌伴工作台</h1>
        <p>管理专注、桌面设备与智能体任务。</p>
        <DeskScene />
      </div>
      <div class="privacy-note">
        <Icon name="shield" :size="17" /> 不用摄像头 · 键鼠只计数 ·
        为你的专注留白
      </div>
    </section>
    <section class="login-form-area">
      <div class="login-form">
        <h2>登录桌伴</h2>
        <p class="muted">使用团队管理员提供的账号登录。</p>
        <form @submit.prevent="submit">
          <label for="username">账号</label
          ><el-input
            id="username"
            v-model="username"
            autocomplete="username"
            placeholder="输入你的账号"
            size="large"
            :maxlength="80"
          /><label for="password">密码</label
          ><el-input
            id="password"
            v-model="password"
            type="password"
            autocomplete="current-password"
            placeholder="输入管理员提供的密码"
            show-password
            size="large"
            :maxlength="200"
          />
          <p v-if="error" class="form-error" role="alert">{{ error }}</p>
          <el-button
            class="login-submit"
            type="primary"
            native-type="submit"
            size="large"
            :loading="busy"
            >进入工作台 <Icon name="arrow" :size="17"
          /></el-button>
        </form>
        <div class="login-divider"><span>离线预览</span></div>
        <button class="preview-entry" @click="app.enterPreview()">
          <span><Icon name="flask" /> 打开示例界面</span
          ><Icon name="arrow" :size="17" />
        </button>
        <p class="login-footnote">
          预览使用本地示例数据。登录 demo
          账号可连接后端虚拟设备；密码由团队管理员提供。
        </p>
      </div>
    </section>
  </div>
</template>
