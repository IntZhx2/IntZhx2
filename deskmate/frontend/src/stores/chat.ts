import { ref } from "vue";
import { defineStore } from "pinia";
import { useApp } from "./app";
import { readSSE } from "../lib/sse";
import type { ToolEvent } from "../types/contracts";
export interface Message {
  id: string;
  role: "user" | "assistant";
  text: string;
  tools: ToolEvent[];
  state: "streaming" | "done" | "error" | "stopped";
  error?: string;
}
export const useChat = defineStore("chat", () => {
  const messages = ref<Message[]>([]),
    pending = ref(false),
    conversation = ref<string>();
  let controller: AbortController | null = null,
    generation = 0;
  function stop() {
    controller?.abort();
  }
  function clear() {
    generation++;
    stop();
    pending.value = false;
    messages.value = [];
    conversation.value = undefined;
  }
  window.addEventListener("deskmate:logout", clear);
  async function send(text: string) {
    const app = useApp();
    if (pending.value || !text.trim() || !app.connected) return;
    const stamp = generation,
      input = text.trim();
    messages.value.push({
      id: crypto.randomUUID(),
      role: "user",
      text: input,
      tools: [],
      state: "done",
    });
    const message: Message = {
      id: crypto.randomUUID(),
      role: "assistant",
      text: "",
      tools: [],
      state: "streaming",
    };
    messages.value.push(message);
    const target = messages.value[messages.value.length - 1]!;
    pending.value = true;
    controller = new AbortController();
    try {
      if (app.preview) {
        const markTool = (
          tool: string,
          args: Record<string, unknown>,
          ok: boolean,
        ) =>
          target.tools.push({
            agent: "env",
            tool,
            args,
            status: ok ? "ok" : "error",
          });
        const temperature = input.match(/空调.*?(\d{2})\s*[度℃]/);
        if (temperature) {
          const value = Number(temperature[1]);
          if (value < 16 || value > 30)
            target.text = "空调设定范围是 16–30℃，请调整温度后再发送。";
          else {
            const ok = await app.command("ac", { temperature: value });
            markTool("ac_set", { temperature: value }, ok);
            target.text = ok
              ? `示例空调已设为 **${value}℃**。这是红外最后指令的推测状态；在线 Demo 不控制真实设备。`
              : "示例设备暂时忙碌，请稍后重试。";
          }
        } else if (/开灯|关灯/.test(input)) {
          const on = !input.includes("关灯");
          const ok = await app.command("lamp", { on });
          markTool("lamp_set", { on }, ok);
          target.text = ok
            ? `示例台灯已${on ? "开启" : "关闭"}。可以回到「我的工位」查看状态。`
            : "示例设备暂时忙碌。";
        } else if (/开空调|关空调/.test(input)) {
          const on = !input.includes("关空调");
          const ok = await app.command("ac", { on });
          markTool("ac_set", { on }, ok);
          target.text = `示例空调${ok ? (on ? "已开启" : "已关闭") : "暂时忙碌"}。`;
        } else if (/结束.*?(专注|学习)|退出专注/.test(input)) {
          const ok = await app.stopFocus();
          target.tools.push({
            agent: "orchestrator",
            tool: "stop_work",
            args: {},
            status: ok ? "ok" : "error",
          });
          target.text = ok
            ? "示例专注已结束，可以选择新的工作台。"
            : "暂时无法结束，请稍后重试。";
        } else if (/开始.*?(专注|学习)|准备工作台/.test(input)) {
          if (app.state?.focus.state !== "idle")
            target.text = `当前已有一段 **${app.state?.focus.workspace_name}** 专注。结束后可以启用其他工作台。`;
          else if (app.workspaces[0]) {
            const profile = app.workspaces[0];
            const ok = await app.startFocus(profile.id, "体验桌伴交互");
            target.tools.push({
              agent: "orchestrator",
              tool: "start_work",
              args: { workspace: profile.name },
              status: ok ? "ok" : "error",
            });
            target.text = ok
              ? `示例工作台 **${profile.name}** 已开始计时，灯光已应用预设。

在线 Demo 未连接 Windows，电脑启动项不会执行。`
              : "暂时无法开始，请稍后重试。";
          } else target.text = "请先在「工作台」创建一项配置。";
        } else if (/代码示例/.test(input)) {
          target.text =
            '以下是用于展示代码高亮的 **Python 示例**，未调用模型，也未写入电脑剪贴板。\n\n```python\ndef focus_summary(minutes: int) -> str:\n    return f"今日专注 {minutes} 分钟"\n\nprint(focus_summary(94))\n```';
        } else {
          target.text =
            "这是前端交互 Demo，未连接模型。可以发送这些指令，查看示例设备变化：\n\n- 开灯 / 关灯\n- 空调调到25度\n- 开始学习 / 结束专注\n- 查看代码示例\n\n工作台编辑、设备控制、演示沙盒和复盘页面也可以直接操作。";
        }
        target.state = "done";
        return;
      }
      const response = await fetch("/api/chat", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${sessionStorage.getItem("deskmate.token") || ""}`,
        },
        body: JSON.stringify({
          message: input,
          ...(conversation.value
            ? { conversation_id: conversation.value }
            : {}),
        }),
        signal: controller.signal,
      });
      if (stamp !== generation) return;
      if (response.status === 401) {
        window.dispatchEvent(new Event("deskmate:unauthorized"));
        throw new Error("登录已过期，请重新登录。");
      }
      if (!response.ok) {
        const data = await response.json().catch(() => ({}));
        throw new Error(
          typeof data.detail === "string"
            ? data.detail
            : `请求失败（${response.status}）。`,
        );
      }
      let done = false;
      await readSSE(response, (event, value) => {
        if (stamp !== generation) return;
        const data = value as Record<string, unknown>;
        if (event === "delta" && typeof data.text === "string")
          target.text += data.text;
        if (event === "tool") target.tools.push(data as unknown as ToolEvent);
        if (event === "error")
          throw new Error(
            typeof data.message === "string"
              ? data.message
              : "桌伴暂时没能完成这次请求。",
          );
        if (event === "done") {
          if (typeof data.reply === "string") target.text = data.reply;
          if (typeof data.conversation_id === "string")
            conversation.value = data.conversation_id;
          done = true;
        }
      });
      if (!done)
        throw new Error(
          "回复在完成前中断，已保留收到的内容。请检查执行结果后再决定是否重试。",
        );
      target.state = "done";
    } catch (err) {
      if (stamp !== generation) return;
      if (err instanceof DOMException && err.name === "AbortError") {
        target.state = "stopped";
        target.error =
          "已停止等待。已下发的设备操作仍可能完成，请查看工位状态。";
      } else {
        target.state = "error";
        target.error =
          err instanceof TypeError
            ? "连接中断，请确认服务状态。"
            : err instanceof Error
              ? err.message
              : "发送失败，请重试。";
      }
    } finally {
      if (stamp === generation) {
        pending.value = false;
        controller = null;
      }
    }
  }
  return { messages, pending, conversation, send, stop, clear };
});
