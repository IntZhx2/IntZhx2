import { createPinia, setActivePinia } from "pinia";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { useApp } from "../src/stores/app";
import { useChat } from "../src/stores/chat";
vi.mock("element-plus", () => ({
  ElMessage: { success: vi.fn(), error: vi.fn(), warning: vi.fn() },
}));
beforeEach(() => {
  setActivePinia(createPinia());
  useApp().connection = "online";
});
afterEach(() => vi.unstubAllGlobals());
describe("对话完成与中断", () => {
  it("保存协同轨迹、最终回复与会话 ID", async () => {
    const stream =
      'event: tool\ndata: {"agent":"env","tool":"lamp_set","args":{"on":true},"status":"ok"}\n\nevent: delta\ndata: {"text":"正在"}\n\nevent: done\ndata: {"reply":"灯已打开","conversation_id":"one"}\n\n';
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response(stream)));
    const chat = useChat();
    await chat.send("开灯");
    expect(chat.messages[1]?.text).toBe("灯已打开");
    expect(chat.messages[1]?.tools).toHaveLength(1);
    expect(chat.messages[1]?.state).toBe("done");
    expect(chat.conversation).toBe("one");
    expect(chat.pending).toBe(false);
  });
  it("流在 done 前中断时保留部分回复并明确提示", async () => {
    vi.stubGlobal(
      "fetch",
      vi
        .fn()
        .mockResolvedValue(
          new Response('event: delta\ndata: {"text":"部分内容"}\n\n'),
        ),
    );
    const chat = useChat();
    await chat.send("分析");
    expect(chat.messages[1]?.text).toBe("部分内容");
    expect(chat.messages[1]?.state).toBe("error");
    expect(chat.messages[1]?.error).toContain("中断");
    expect(chat.pending).toBe(false);
  });
  it("后端业务错误可见，不冒充已完成", async () => {
    vi.stubGlobal(
      "fetch",
      vi
        .fn()
        .mockResolvedValue(
          new Response('event: error\ndata: {"message":"尚未配置模型"}\n\n'),
        ),
    );
    const chat = useChat();
    await chat.send("帮我分析报错");
    expect(chat.messages[1]?.error).toBe("尚未配置模型");
    expect(chat.messages[1]?.state).toBe("error");
  });
  it("退出时清空对话，防止下个账号看到内容", async () => {
    const app = useApp();
    app.enterPreview();
    const chat = useChat();
    await chat.send("预览内容");
    expect(chat.messages).toHaveLength(2);
    app.logout();
    expect(chat.messages).toHaveLength(0);
    expect(chat.conversation).toBeUndefined();
  });
  it("示例指令修改本地设备并记录轨迹，不请求模型或后端", async () => {
    const fetcher = vi.fn();
    vi.stubGlobal("fetch", fetcher);
    const app = useApp();
    app.enterPreview();
    const chat = useChat();
    await chat.send("空调调到25度");
    expect(app.state?.devices.ac?.temperature).toBe(25);
    expect(chat.messages[1]?.tools[0]).toMatchObject({
      tool: "ac_set",
      status: "ok",
    });
    expect(app.notices[0]?.title).toBe("空调已更新");
    expect(chat.messages[1]?.text).toContain("示例");
    expect(fetcher).not.toHaveBeenCalled();
  });
  it("示例指令拒绝范围外温度", async () => {
    const app = useApp();
    app.enterPreview();
    const chat = useChat();
    await chat.send("空调调到99度");
    expect(app.state?.devices.ac?.temperature).toBe(26);
    expect(chat.messages[1]?.tools).toHaveLength(0);
    expect(chat.messages[1]?.text).toContain("16–30");
  });
  it("示例结束与重新开始使用真实的页面状态", async () => {
    const app = useApp();
    app.enterPreview();
    const chat = useChat();
    await chat.send("结束专注");
    expect(app.state?.focus.state).toBe("idle");
    await chat.send("开始学习");
    expect(app.state?.focus.state).toBe("focusing");
    expect(chat.messages[3]?.text).toContain("电脑启动项不会执行");
  });
  it("代码示例明确标记，保留代码块用于高亮", async () => {
    const app = useApp();
    app.enterPreview();
    const chat = useChat();
    await chat.send("查看代码示例");
    expect(chat.messages[1]?.text).toContain("```python");
    expect(chat.messages[1]?.text).toContain("未调用模型");
    expect(chat.messages[1]?.tools).toHaveLength(0);
  });
});
