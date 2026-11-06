<script setup lang="ts">
import { nextTick, onBeforeUnmount, ref, watch } from "vue";
import { ElMessage } from "element-plus";
import { useApp } from "../stores/app";
import { useChat } from "../stores/chat";
import { download } from "../lib/api";
import Icon from "../components/Icon.vue";
import Markdown from "../components/Markdown.vue";
const app = useApp(),
  chat = useChat(),
  input = ref(""),
  scroll = ref<HTMLElement>(),
  listening = ref(false);
const suggestions = [
  { icon: "desk", label: "开始专注", text: "我要开始学习" },
  {
    icon: "code",
    label: "查看代码示例",
    text: "查看代码示例",
  },
  { icon: "snow", label: "空调调到25度", text: "空调调到25度" },
];
async function submit(text = input.value) {
  if (!text.trim() || chat.pending) return;
  input.value = "";
  await chat.send(text);
}
watch(
  () => JSON.stringify(chat.messages),
  async () => {
    await nextTick();
    scroll.value?.scrollTo({
      top: scroll.value.scrollHeight,
      behavior: "smooth",
    });
  },
);
function exportChat() {
  download(
    "桌伴对话.md",
    chat.messages
      .map(
        (message) =>
          `## ${message.role === "user" ? "我" : "桌伴"}\n\n${message.text}${message.error ? `\n\n> ${message.error}` : ""}`,
      )
      .join("\n\n"),
  );
}
type Recognition = {
  lang: string;
  interimResults: boolean;
  onresult:
    ((event: { results: { 0: { 0: { transcript: string } } } }) => void) | null;
  onerror: (() => void) | null;
  onend: (() => void) | null;
  start: () => void;
  stop: () => void;
};
const RecognitionApi =
  (
    window as unknown as {
      SpeechRecognition?: new () => Recognition;
      webkitSpeechRecognition?: new () => Recognition;
    }
  ).SpeechRecognition ||
  (window as unknown as { webkitSpeechRecognition?: new () => Recognition })
    .webkitSpeechRecognition;
let recognition: Recognition | undefined;
function speak() {
  if (listening.value) {
    recognition?.stop();
    return;
  }
  if (!RecognitionApi) return;
  recognition = new RecognitionApi();
  recognition.lang = "zh-CN";
  recognition.interimResults = false;
  recognition.onresult = (event) => {
    input.value = event.results[0][0].transcript;
  };
  recognition.onerror = () => {
    listening.value = false;
    ElMessage.warning("语音输入不可用，请检查麦克风权限，或直接输入文字。");
  };
  recognition.onend = () => {
    listening.value = false;
  };
  try {
    recognition.start();
    listening.value = true;
  } catch {
    listening.value = false;
    ElMessage.warning("无法启动麦克风，请直接输入文字。");
  }
}
onBeforeUnmount(() => recognition?.stop());
const agents: Record<string, string> = {
  orchestrator: "协调者",
  pc: "电脑智能体",
  env: "环境智能体",
  computer: "电脑智能体",
  environment: "环境智能体",
};
</script>
<template>
  <div class="chat-page page-enter">
    <div class="page-heading">
      <div>
        <h1>桌伴助手</h1>
        <p>发送指令，查看智能体的执行过程和结果。</p>
      </div>
      <div class="inline-actions">
        <button
          class="icon-button"
          aria-label="导出当前对话"
          :disabled="!chat.messages.length"
          @click="exportChat"
        >
          <Icon name="download" /></button
        ><button
          class="button secondary"
          :disabled="chat.pending"
          @click="chat.clear()"
        >
          <Icon name="plus" :size="16" /> 新对话
        </button>
      </div>
    </div>
    <section class="card chat-shell">
      <div ref="scroll" class="chat-scroll">
        <div v-if="!chat.messages.length" class="chat-welcome">
          <span class="assistant-orb"><Icon name="desk" :size="35" /></span>
          <h2>发送一条指令</h2>
          <p>可以调整设备、开始专注，或请求智能体协助。</p>
          <div class="suggestions">
            <button
              v-for="item in suggestions"
              :key="item.label"
              :disabled="!app.connected"
              @click="submit(item.text)"
            >
              <Icon :name="item.icon" /><span>{{ item.label }}</span
              ><Icon name="arrow" :size="15" />
            </button>
          </div>
        </div>
        <article
          v-for="message in chat.messages"
          :key="message.id"
          class="chat-message"
          :class="message.role"
        >
          <span class="message-avatar"
            ><Icon :name="message.role === 'user' ? 'user' : 'desk'" :size="19"
          /></span>
          <div class="message-body">
            <div class="message-author">
              {{ message.role === "user" ? "我" : "桌伴"
              }}<small v-if="message.state === 'streaming'" class="stream-label"
                >正在处理 <span>···</span></small
              >
            </div>
            <details v-if="message.tools.length" class="trace">
              <summary>
                <Icon name="flask" :size="15" /> 智能体协作轨迹 ·
                {{ message.tools.length }} 条事件
              </summary>
              <div
                v-for="(tool, index) in message.tools"
                :key="index"
                class="trace-step"
              >
                <span class="trace-dot" :class="tool.status" />
                <div>
                  <strong
                    >{{ agents[tool.agent] || tool.agent }} →
                    {{ tool.tool }}</strong
                  ><span class="subtle-tag">{{
                    { running: "执行中", ok: "已完成", error: "未完成" }[
                      tool.status
                    ]
                  }}</span>
                  <pre>{{ JSON.stringify(tool.args, null, 2) }}</pre>
                </div>
              </div>
            </details>
            <Markdown
              v-if="message.role === 'assistant'"
              :text="message.text"
            />
            <p v-else class="user-text">{{ message.text }}</p>
            <p v-if="message.error" class="chat-error" role="alert">
              <Icon name="info" :size="16" />{{ message.error }}
            </p>
            <span
              v-if="!message.text && message.state === 'streaming'"
              class="typing-dots"
              >● ● ●</span
            >
          </div>
        </article>
      </div>
      <form class="chat-composer" @submit.prevent="submit()">
        <textarea
          v-model="input"
          aria-label="对桌伴说"
          placeholder="输入指令，例如：空调调到25度"
          rows="2"
          maxlength="4000"
          :disabled="!app.connected"
          @keydown.enter.exact="
            (event) => {
              if (!event.isComposing) {
                event.preventDefault();
                submit();
              }
            }
          "
        />
        <div class="composer-bottom">
          <span
            ><Icon name="shield" :size="13" />
            {{
              listening
                ? "正在听，结束后可编辑再发送"
                : "Enter 发送 · Shift + Enter 换行"
            }}</span
          >
          <div>
            <button
              v-if="RecognitionApi"
              type="button"
              class="icon-button"
              :class="{ listening }"
              :aria-label="listening ? '停止录音' : '语音输入'"
              :disabled="!app.connected || chat.pending"
              @click="speak"
            >
              <Icon name="mic" :size="19" /></button
            ><button
              v-if="chat.pending"
              type="button"
              class="send-button"
              aria-label="停止等待回复"
              @click="chat.stop()"
            >
              <Icon name="stop" :size="17" /></button
            ><button
              v-else
              type="submit"
              class="send-button"
              aria-label="发送消息"
              :disabled="!input.trim() || !app.connected"
            >
              <Icon name="arrow" :size="20" />
            </button>
          </div>
        </div>
      </form>
    </section>
    <p class="page-note">
      {{
        app.preview
          ? "示例环境仅模拟设备指令和代码展示，不调用模型或操作真实电脑。"
          : "简单设备口令无需模型；查资料与复杂任务需要后端配置模型服务。"
      }}
    </p>
  </div>
</template>
