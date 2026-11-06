import { computed, ref } from "vue";
import { defineStore } from "pinia";
import { ElMessage } from "element-plus";
import { ApiError, post, request, today } from "../lib/api";
import { Realtime } from "../lib/realtime";
import { previewData } from "../lib/preview";
import type {
  AssistResult,
  Envelope,
  Notice,
  Settings,
  Snapshot,
  Timeline,
  User,
  VoiceLog,
  Workspace,
  WorkspaceIn,
} from "../types/contracts";

export const useApp = defineStore("app", () => {
  const user = ref<User | null>(null),
    preview = ref(false),
    state = ref<Snapshot | null>(null);
  const workspaces = ref<Workspace[]>([]),
    settings = ref<Settings | null>(null),
    timeline = ref<Timeline | null>(null);
  const connection = ref<"connecting" | "online" | "reconnecting" | "offline">(
    "offline",
  );
  const healthAvailable = ref<boolean | null>(null),
    notices = ref<(Notice & { at: string; id: string })[]>([]);
  const assistance = ref<AssistResult | null>(null),
    logs = ref<VoiceLog[]>([]),
    restOverlay = ref(false);
  const loading = ref(false),
    busy = ref(false),
    error = ref("");
  let realtime: Realtime | null = null,
    generation = 0;
  const connected = computed(
    () => preview.value || connection.value === "online",
  );
  function addNotice(notice: Notice) {
    notices.value.unshift({
      ...notice,
      at: new Date().toISOString(),
      id: crypto.randomUUID(),
    });
    notices.value = notices.value.slice(0, 30);
    if (notice.action === "rest_overlay") restOverlay.value = true;
    if (notice.level !== "info")
      ElMessage({
        type: notice.level === "warn" ? "warning" : "error",
        message: notice.text,
      });
  }
  function receive(message: Envelope) {
    if (message.name === "notify")
      addNotice(message.payload as unknown as Notice);
    if (message.name === "assist.result")
      assistance.value = message.payload as unknown as AssistResult;
    if (message.name === "voice.log")
      logs.value.unshift(message.payload as unknown as VoiceLog);
  }
  function recordInput() {
    const stat = state.value?.current_input_stats;
    if (!stat) return;
    if (!timeline.value)
      timeline.value = {
        date: today(),
        inputs: [],
        env: [],
        fatigue_events: [],
        focus_spans: [],
      };
    const rows = timeline.value.inputs;
    const value = {
      minute: stat.minute,
      activity_rate: stat.activity_rate,
      top_category: stat.front_title_category,
    };
    const existing = rows.findIndex((row) => row.minute === stat.minute);
    if (existing >= 0) rows[existing] = value;
    else rows.push(value);
    timeline.value.inputs = rows.slice(-1440);
  }
  async function load() {
    const stamp = generation;
    loading.value = true;
    error.value = "";
    try {
      const [snapshot, profiles, config] = await Promise.all([
        request<Snapshot>("/api/state"),
        request<Workspace[]>("/api/workspaces"),
        request<Settings>("/api/settings"),
      ]);
      if (stamp !== generation) return;
      state.value = snapshot;
      workspaces.value = profiles;
      settings.value = config;
      realtime?.stop();
      realtime = new Realtime(sessionStorage.getItem("deskmate.token") || "", {
        state: (patch, full) => {
          if (full) state.value = patch as Snapshot;
          else if (state.value) Object.assign(state.value, patch);
          recordInput();
        },
        event: receive,
        status: (value) => {
          connection.value = value;
        },
        expired: () => {
          logout();
          ElMessage.warning("登录已过期，请重新登录。");
        },
      });
      realtime.connect();
      void request<Timeline>(`/api/timeline?date=${today()}`)
        .then((value) => {
          if (stamp === generation) {
            timeline.value = value;
            healthAvailable.value = true;
          }
        })
        .catch((err) => {
          if (
            stamp === generation &&
            err instanceof ApiError &&
            err.status === 503
          )
            healthAvailable.value = false;
        });
      void request<VoiceLog[]>("/api/logs/voice?limit=20")
        .then((value) => {
          if (stamp === generation) logs.value = value;
        })
        .catch(() => {});
    } catch (err) {
      if (stamp === generation)
        error.value = err instanceof Error ? err.message : "加载失败，请重试。";
    } finally {
      if (stamp === generation) loading.value = false;
    }
  }
  async function login(username: string, password: string) {
    const result = await post<{ token: string; user: User }>(
      "/api/auth/login",
      { username, password },
    );
    logout();
    user.value = result.user;
    sessionStorage.setItem("deskmate.token", result.token);
    sessionStorage.setItem("deskmate.user", JSON.stringify(result.user));
    await load();
  }
  function logout(preservePreviewUrl = false) {
    if (
      !preservePreviewUrl &&
      new URLSearchParams(location.search).has("preview")
    ) {
      const url = new URL(location.href);
      url.searchParams.delete("preview");
      history.replaceState(null, "", url.pathname + url.search + url.hash);
    }
    generation++;
    realtime?.stop();
    realtime = null;
    window.dispatchEvent(new Event("deskmate:logout"));
    sessionStorage.removeItem("deskmate.token");
    sessionStorage.removeItem("deskmate.user");
    user.value = null;
    preview.value = false;
    state.value = null;
    workspaces.value = [];
    settings.value = null;
    timeline.value = null;
    notices.value = [];
    logs.value = [];
    assistance.value = null;
    restOverlay.value = false;
    healthAvailable.value = null;
    loading.value = false;
    busy.value = false;
    error.value = "";
  }
  function enterPreview() {
    logout(true);
    preview.value = true;
    user.value = { id: 0, username: "体验者", is_demo: true };
    const data = previewData();
    state.value = data.state;
    workspaces.value = data.workspaces;
    settings.value = data.settings;
    timeline.value = data.timeline;
    healthAvailable.value = true;
  }
  async function restore() {
    if (!sessionStorage.getItem("deskmate.token")) return;
    try {
      user.value = JSON.parse(
        sessionStorage.getItem("deskmate.user") || "null",
      );
      if (!user.value) {
        logout();
        return;
      }
      await load();
    } catch {
      logout();
    }
  }
  async function action(run: () => Promise<unknown>, success?: string) {
    if (busy.value) return false;
    busy.value = true;
    const stamp = generation;
    try {
      await run();
      if (stamp !== generation) return false;
      if (success)
        ElMessage.success(preview.value ? `界面预览：${success}` : success);
      return true;
    } catch (err) {
      if (
        stamp === generation &&
        !(err instanceof DOMException && err.name === "AbortError")
      )
        ElMessage.error(
          err instanceof Error ? err.message : "操作失败，请重试。",
        );
      return false;
    } finally {
      if (stamp === generation) busy.value = false;
    }
  }
  function recordDeviceCommand(device: "lamp" | "ac" | "plug") {
    const devices = state.value?.devices;
    if (!devices) return;
    const names = { lamp: "台灯", ac: "空调", plug: "桌面插座" };
    let text = "";
    if (device === "lamp" && devices.lamp)
      text = devices.lamp.on
        ? `亮度 ${devices.lamp.brightness}%，色温 ${devices.lamp.color_temp}K`
        : "已关闭";
    if (device === "ac" && devices.ac)
      text = `${devices.ac.on ? "已开启" : "已关闭"} · 设定 ${devices.ac.temperature}℃（推测状态）`;
    if (device === "plug" && devices.plug)
      text = devices.plug.on ? "已开启" : "已关闭";
    addNotice({
      level: "info",
      title: `${names[device]}已更新`,
      text: (preview.value ? "示例状态：" : "") + text,
      action: "none",
    });
  }
  async function command(
    device: "lamp" | "ac" | "plug",
    args: Record<string, unknown>,
  ) {
    return action(async () => {
      if (preview.value) {
        Object.assign(state.value!.devices[device]!, args);
        recordDeviceCommand(device);
        return;
      }
      const result = await post<{ state: Snapshot["devices"][typeof device] }>(
        `/api/devices/${device}/command`,
        args,
      );
      if (state.value)
        Object.assign(state.value.devices, { [device]: result.state });
      recordDeviceCommand(device);
    });
  }
  async function startFocus(
    workspace_id: number,
    goal: string,
    minutes?: number,
  ) {
    return action(async () => {
      if (preview.value) {
        const profile = workspaces.value.find((w) => w.id === workspace_id)!;
        const duration = (minutes || profile.focus_minutes) * 60;
        Object.assign(state.value!.focus, {
          state: "focusing",
          workspace_name: profile.name,
          goal,
          remaining_seconds: duration,
          phase_started_at: new Date().toISOString(),
          phase_ends_at: new Date(Date.now() + duration * 1000).toISOString(),
        });
        Object.assign(state.value!.devices.lamp!, profile.lamp, { on: true });
        addNotice({
          level: "info",
          title: "专注已开始",
          text: `示例会话：${profile.name}，${Math.round(duration / 60)} 分钟`,
          action: "none",
        });
        return;
      }
      state.value!.focus = await post("/api/focus/start", {
        workspace_id,
        goal,
        ...(minutes ? { minutes } : {}),
      });
      addNotice({
        level: "info",
        title: "专注已开始",
        text: state.value!.focus.workspace_name,
        action: "none",
      });
    }, "工作台已就绪，开始专注。");
  }
  async function stopFocus() {
    return action(async () => {
      if (preview.value) {
        state.value!.focus.state = "idle";
        state.value!.focus.remaining_seconds = 0;
        addNotice({
          level: "info",
          title: "专注已结束",
          text: "示例会话已结束，可选择工作台重新开始。",
          action: "none",
        });
        return;
      }
      await post("/api/focus/stop");
      state.value = await request("/api/state");
      addNotice({
        level: "info",
        title: "专注已结束",
        text: "会话已保存。",
        action: "none",
      });
    }, "本次专注已结束。");
  }
  async function saveWorkspace(value: WorkspaceIn, id?: number) {
    return action(async () => {
      if (preview.value) {
        const index = workspaces.value.findIndex((w) => w.id === id);
        const row = {
          ...JSON.parse(JSON.stringify(value)),
          id: id ?? Date.now(),
        };
        if (index >= 0) workspaces.value[index] = row;
        else workspaces.value.push(row);
        return;
      }
      await request(`/api/workspaces${id ? `/${id}` : ""}`, {
        method: id ? "PUT" : "POST",
        body: JSON.stringify(value),
      });
      workspaces.value = await request("/api/workspaces");
    }, "工作台已保存。");
  }
  async function deleteWorkspace(id: number) {
    return action(async () => {
      if (!preview.value)
        await request(`/api/workspaces/${id}`, { method: "DELETE" });
      workspaces.value = workspaces.value.filter((w) => w.id !== id);
    }, "工作台已删除。");
  }
  async function inject(kind: string, value: unknown = null) {
    return action(async () => {
      if (!preview.value) {
        await post("/api/demo/inject", { kind, value });
        return;
      }
      if (kind === "temperature")
        state.value!.devices.climate!.temperature = Number(value);
      if (["motion", "leave", "lock"].includes(kind)) {
        const present = kind === "motion" || (kind === "lock" && !value);
        state.value!.presence.present = present;
        state.value!.presence.sources.screen_locked =
          kind === "lock" && Boolean(value);
        if (!present && state.value!.focus.state === "focusing") {
          state.value!.focus.remaining_seconds = Math.max(
            0,
            Math.round(
              (Date.parse(state.value!.focus.phase_ends_at!) - Date.now()) /
                1000,
            ),
          );
          state.value!.focus.state = "paused";
        } else if (present && state.value!.focus.state === "paused") {
          state.value!.focus.state = "focusing";
          state.value!.focus.phase_ends_at = new Date(
            Date.now() + state.value!.focus.remaining_seconds * 1000,
          ).toISOString();
        }
      }
      if (kind === "typing_rate") {
        timeline.value!.inputs.push({
          minute: new Date().toISOString(),
          activity_rate: Number(value),
          top_category: "study",
        });
      }
      if (kind === "voice")
        addNotice({
          level: "info",
          title: "示例语音输入",
          text: String(value),
          action: "none",
        });
    }, "模拟事件已提交。");
  }
  async function saveSettings(patch: Partial<Settings>) {
    return action(async () => {
      if (preview.value) Object.assign(settings.value!, patch);
      else
        settings.value = await request("/api/settings", {
          method: "PUT",
          body: JSON.stringify(patch),
        });
    }, "设置已保存。");
  }
  function skipRest() {
    if (preview.value || realtime?.send("rest.skip")) restOverlay.value = false;
    else ElMessage.warning("连接恢复后可跳过休息。");
  }
  return {
    user,
    preview,
    state,
    workspaces,
    settings,
    timeline,
    connection,
    connected,
    healthAvailable,
    notices,
    assistance,
    logs,
    restOverlay,
    loading,
    busy,
    error,
    login,
    logout,
    enterPreview,
    restore,
    load,
    command,
    startFocus,
    stopFocus,
    saveWorkspace,
    deleteWorkspace,
    inject,
    saveSettings,
    skipRest,
  };
});
