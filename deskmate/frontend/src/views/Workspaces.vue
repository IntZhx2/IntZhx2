<script setup lang="ts">
import { reactive, ref } from "vue";
import { ElMessage, ElMessageBox } from "element-plus";
import { useApp } from "../stores/app";
import type { Workspace, WorkspaceIn, WorkspaceItem } from "../types/contracts";
import Icon from "../components/Icon.vue";
import WorkspaceItemForm from "../components/WorkspaceItemForm.vue";
const app = useApp(),
  open = ref(false),
  editing = ref<number>(),
  aliases = ref("");
const blank = (): WorkspaceIn => ({
  name: "",
  aliases: [],
  focus_minutes: 45,
  lamp: { brightness: 80, color_temp: 4000 },
  ac: { auto_on: true, temperature: 26 },
  items: [],
  layout: "code_left_browser_right",
  custom_layout: null,
});
const form = reactive<WorkspaceIn>(blank());
function edit(workspace?: Workspace) {
  const value = workspace ? JSON.parse(JSON.stringify(workspace)) : blank();
  delete value.id;
  Object.assign(form, value);
  editing.value = workspace?.id;
  aliases.value = form.aliases.join("，");
  open.value = true;
}
async function save() {
  if (!form.name.trim()) {
    ElMessage.warning("先给工作台起个名字。");
    return;
  }
  if (
    form.items.some(
      (item) =>
        !(
          item.type === "url"
            ? item.url
            : item.type === "app"
              ? item.name
              : item.path
        )?.trim(),
    )
  ) {
    ElMessage.warning("请填写每一个启动项，或移除空白行。");
    return;
  }
  if (
    form.items.some(
      (item) =>
        item.type === "url" && !/^https?:\/\/[^\s]+$/i.test(item.url || ""),
    )
  ) {
    ElMessage.warning("网址需要以 http:// 或 https:// 开头。");
    return;
  }
  const value: WorkspaceIn = JSON.parse(JSON.stringify(form));
  value.name = value.name.trim();
  value.aliases = aliases.value
    .split(/[,，]/)
    .map((s) => s.trim())
    .filter(Boolean);
  if (await app.saveWorkspace(value, editing.value)) open.value = false;
}
async function remove(workspace: Workspace) {
  try {
    await ElMessageBox.confirm(
      `删除「${workspace.name}」后无法恢复。`,
      "删除工作台",
      { confirmButtonText: "删除", cancelButtonText: "保留", type: "warning" },
    );
    await app.deleteWorkspace(workspace.id);
  } catch {
    /* 用户取消 */
  }
}
</script>
<template>
  <div class="page-enter">
    <div class="page-heading">
      <div>
        <h1>工作台</h1>
        <p>保存灯光、应用和窗口布局，开始专注时一起启用。</p>
      </div>
      <button
        class="button primary"
        :disabled="app.busy || !app.connected"
        @click="edit()"
      >
        <Icon name="plus" :size="17" /> 新建工作台
      </button>
    </div>
    <div class="workspace-grid">
      <article
        v-for="(workspace, i) in app.workspaces"
        :key="workspace.id"
        class="card workspace-card"
      >
        <div class="workspace-art" :class="i % 2 ? 'reading' : ''">
          <Icon :name="i % 2 ? 'leaf' : 'code'" :size="44" />
          <span>{{ String(i + 1).padStart(2, "0") }}</span>
        </div>
        <div class="workspace-body">
          <div class="card-top">
            <h2>{{ workspace.name }}</h2>
            <span class="subtle-tag">{{ workspace.focus_minutes }} 分钟</span>
          </div>
          <p>
            {{
              workspace.aliases.length
                ? `也可以叫它「${workspace.aliases.join("、")}」`
                : "配置常用启动项和环境。"
            }}
          </p>
          <div class="workspace-specs">
            <span>
              <Icon name="lamp" :size="15" /> {{ workspace.lamp.brightness }}% ·
              {{ workspace.lamp.color_temp }}K</span
            >
            <span>
              <Icon name="monitor" :size="15" />
              {{ workspace.items.length }} 个启动项</span
            >
          </div>
          <div class="workspace-footer">
            <button
              class="text-link"
              :disabled="
                !app.connected || app.busy || app.state?.focus.state !== 'idle'
              "
              @click="app.startFocus(workspace.id, '')"
            >
              启用工作台 <Icon name="arrow" :size="16" />
            </button>
            <div>
              <button
                class="icon-button"
                :aria-label="`编辑${workspace.name}`"
                :disabled="!app.connected || app.busy"
                @click="edit(workspace)"
              >
                <Icon name="edit" :size="17" />
              </button>
              <button
                class="icon-button"
                :aria-label="`删除${workspace.name}`"
                :disabled="!app.connected || app.busy"
                @click="remove(workspace)"
              >
                <Icon name="trash" :size="17" />
              </button>
            </div>
          </div>
        </div>
      </article>
      <button
        class="workspace-add"
        :disabled="!app.connected || app.busy"
        @click="edit()"
      >
        <Icon name="plus" :size="30" />
        <h3>新建工作台</h3>
        <p>创建你的专属工作台</p>
      </button>
    </div>
    <p v-if="app.state?.focus.state !== 'idle'" class="page-note">
      当前有一段专注正在进行。结束后，可以启用其他工作台。
    </p>
    <el-dialog
      v-model="open"
      :title="editing ? '编辑工作台' : '新建工作台'"
      width="640px"
      :close-on-click-modal="false"
    >
      <el-form label-position="top">
        <div class="form-two">
          <el-form-item label="工作台名称">
            <el-input
              v-model="form.name"
              :maxlength="80"
              placeholder="例如：软件工程项目"
            />
          </el-form-item>
          <el-form-item label="专注时长（分钟）">
            <el-input-number v-model="form.focus_minutes" :min="1" :max="240" />
          </el-form-item>
        </div>
        <el-form-item label="语音别名（逗号分隔）">
          <el-input
            v-model="aliases"
            placeholder="软工，大作业"
            :maxlength="400"
          />
        </el-form-item>
        <div class="form-two">
          <el-form-item :label="`台灯亮度 · ${form.lamp.brightness}%`">
            <el-slider v-model="form.lamp.brightness" :min="1" :max="100" />
          </el-form-item>
          <el-form-item :label="`台灯色温 · ${form.lamp.color_temp}K`">
            <el-slider
              v-model="form.lamp.color_temp"
              :min="2500"
              :max="4800"
              :step="100"
            />
          </el-form-item>
        </div>
        <div class="form-two">
          <el-form-item label="工作时允许自动开空调">
            <el-switch v-model="form.ac.auto_on" />
          </el-form-item>
          <el-form-item label="空调目标温度">
            <el-input-number
              v-model="form.ac.temperature"
              :min="16"
              :max="30"
            />
          </el-form-item>
        </div>
        <el-form-item label="窗口布局">
          <el-select v-model="form.layout">
            <el-option
              label="代码左侧 · 浏览器右侧"
              value="code_left_browser_right"
            />
            <el-option label="左右均分" value="split_half" />
            <el-option label="最大化" value="maximize" />
            <el-option
              v-if="form.custom_layout"
              label="保留已有自定义布局"
              value="custom"
            />
          </el-select>
        </el-form-item>
        <div class="card-top">
          <h3>同时打开</h3>
          <el-button
            :disabled="form.items.length >= 20"
            size="small"
            @click="form.items.push({ type: 'url', url: '' })"
            >添加启动项</el-button
          >
        </div>
        <WorkspaceItemForm
          v-for="(item, index) in form.items"
          :key="index"
          :item="item"
          :index="index"
          @change="(value: WorkspaceItem) => (form.items[index] = value)"
          @remove="form.items.splice(index, 1)"
        />
        <p class="muted">
          路径和应用在现场 Windows 电脑执行；演示账号只操作虚拟环境。
        </p>
      </el-form>
      <template #footer>
        <el-button @click="open = false">取消</el-button>
        <el-button type="primary" :loading="app.busy" @click="save"
          >保存工作台</el-button
        >
      </template>
    </el-dialog>
  </div>
</template>
