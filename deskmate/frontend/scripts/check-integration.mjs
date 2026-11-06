// 仅连接本地 demo 账号。凭据来自调用者指定的本地 JSON 文件，不记录令牌或密码。
import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
const base = process.argv[3] || "http://127.0.0.1:5173";
assert(
  ["127.0.0.1", "localhost"].includes(new URL(base).hostname),
  "联调脚本只允许本机服务",
);
assert(process.argv[2], "请提供本地演示凭据 JSON 文件路径");
const credentials = JSON.parse(await readFile(process.argv[2], "utf8"));
let token = "",
  socket,
  workspaceId;
const checks = [],
  messages = [],
  listeners = new Set();
async function api(path, method = "GET", body) {
  const response = await fetch(base + path, {
    method,
    headers: {
      "Content-Type": "application/json",
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
    },
    ...(body ? { body: JSON.stringify(body) } : {}),
  });
  assert(response.ok, `${method} ${path}: ${response.status}`);
  return response.json();
}
function waitFor(name, predicate = () => true, from = 0) {
  const existing = messages
    .slice(from)
    .find((m) => m.name === name && predicate(m.payload));
  if (existing) return Promise.resolve(existing.payload);
  return new Promise((resolve, reject) => {
    const timer = setTimeout(() => {
      listeners.delete(check);
      reject(new Error(`等待 ${name} 超时`));
    }, 6000);
    const check = (m) => {
      if (m.name === name && predicate(m.payload)) {
        clearTimeout(timer);
        listeners.delete(check);
        resolve(m.payload);
      }
    };
    listeners.add(check);
  });
}
try {
  const auth = await api("/api/auth/login", "POST", credentials);
  assert(auth.user.is_demo, "仅允许隔离的 demo 账号");
  token = auth.token;
  checks.push("demo 登录");
  socket = new WebSocket(
    base.replace(/^http/, "ws") + "/ws/web?token=" + encodeURIComponent(token),
  );
  socket.onmessage = (event) => {
    const msg = JSON.parse(event.data);
    if (msg.type === "ping")
      socket.send(
        JSON.stringify({
          v: 2,
          type: "pong",
          id: crypto.randomUUID(),
          ts: new Date().toISOString(),
          name: "",
          payload: {},
        }),
      );
    messages.push(msg);
    for (const check of listeners) check(msg);
  };
  const snapshot = await waitFor("state.snapshot");
  assert(snapshot.demo_mode);
  checks.push("WebSocket 首次快照");
  const workspace = await api("/api/workspaces", "POST", {
    name: "前端联调专用工作台",
    aliases: [],
    focus_minutes: 1,
    lamp: { brightness: 75, color_temp: 4000 },
    ac: { auto_on: true, temperature: 26 },
    items: [],
    layout: "maximize",
    custom_layout: null,
  });
  workspaceId = workspace.id;
  await api(`/api/workspaces/${workspaceId}`, "PUT", {
    ...Object.fromEntries(
      Object.entries(workspace).filter(([k]) => k !== "id"),
    ),
    name: "前端联调工作台已编辑",
  });
  checks.push("工作台创建与编辑");
  let mark = messages.length;
  await api("/api/devices/lamp/command", "POST", { brightness: 65 });
  await waitFor("state.patch", (p) => p.devices?.lamp?.brightness === 65, mark);
  checks.push("灯光控制与实时增量");
  const focus = await api("/api/focus/start", "POST", {
    workspace_id: workspaceId,
    minutes: 1,
    goal: "验证前端链路",
  });
  assert.equal(focus.state, "focusing");
  mark = messages.length;
  await api("/api/demo/inject", "POST", { kind: "lock", value: true });
  await waitFor("state.patch", (p) => p.focus?.state === "paused", mark);
  mark = messages.length;
  await api("/api/demo/inject", "POST", { kind: "lock", value: false });
  await waitFor("state.patch", (p) => p.focus?.state === "focusing", mark);
  checks.push("专注开始、锁屏暂停与解锁恢复");
  const chat = await fetch(base + "/api/chat", {
    method: "POST",
    headers: {
      Authorization: `Bearer ${token}`,
      "Content-Type": "application/json",
    },
    body: JSON.stringify({ message: "空调调到25度" }),
  });
  assert(chat.ok);
  const stream = await chat.text();
  assert.match(stream, /event: done/);
  assert.equal((await api("/api/state")).devices.ac.temperature, 25);
  checks.push("SSE 快速口令与设备结果");
  await api("/api/settings", "PUT", { ac: { trigger_on_temp: 28 } });
  assert.equal((await api("/api/settings")).ac.trigger_on_temp, 28);
  checks.push("设置保存与回读");
  const daily = await fetch(base + "/api/reports/daily?date=2026-11-06", {
    headers: { Authorization: `Bearer ${token}` },
  });
  assert.equal(daily.status, 503);
  checks.push("健康模块未接入明确返回 503");
  await api("/api/focus/stop", "POST");
  await api(`/api/workspaces/${workspaceId}`, "DELETE");
  workspaceId = undefined;
  checks.push("专注结束与联调工作台清理");
  console.log(JSON.stringify({ ok: true, base_url: base, checks }, null, 2));
} finally {
  socket?.close();
  if (workspaceId && token) {
    await api("/api/focus/stop", "POST").catch(() => {});
    await api(`/api/workspaces/${workspaceId}`, "DELETE").catch(() => {});
  }
}
