import { createPinia, setActivePinia } from "pinia";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { useApp } from "../src/stores/app";
import { previewData } from "../src/lib/preview";
import type { WorkspaceIn } from "../src/types/contracts";
vi.mock("element-plus", () => ({
  ElMessage: { success: vi.fn(), error: vi.fn(), warning: vi.fn() },
}));
beforeEach(() => {
  setActivePinia(createPinia());
  sessionStorage.clear();
});
afterEach(() => vi.unstubAllGlobals());
describe("工位操作与预览边界", () => {
  it("预览只改本地示例，不请求服务或设备", async () => {
    const fetcher = vi.fn();
    vi.stubGlobal("fetch", fetcher);
    const app = useApp();
    app.enterPreview();
    await app.command("lamp", { brightness: 62 });
    expect(app.state?.devices.lamp?.brightness).toBe(62);
    await app.stopFocus();
    await app.startFocus(1, "预览目标", 25);
    expect(app.state?.focus.goal).toBe("预览目标");
    expect(app.state?.focus.remaining_seconds).toBe(1500);
    expect(fetcher).not.toHaveBeenCalled();
    expect(sessionStorage.getItem("deskmate.token")).toBeNull();
  });
  it("预览中的工作台可以创建、编辑和删除", async () => {
    const app = useApp();
    app.enterPreview();
    const input = JSON.parse(
      JSON.stringify(app.workspaces[0]),
    ) as WorkspaceIn & { id?: number };
    delete input.id;
    input.name = "自定义工作台";
    await app.saveWorkspace(input);
    const row = app.workspaces.find((w) => w.name === input.name)!;
    input.name = "改名后";
    await app.saveWorkspace(input, row.id);
    expect(app.workspaces.find((w) => w.id === row.id)?.name).toBe("改名后");
    await app.deleteWorkspace(row.id);
    expect(app.workspaces).toHaveLength(2);
  });
  it("服务端拒绝设备操作时保留之前的真实状态", async () => {
    const app = useApp();
    app.state = previewData().state;
    vi.stubGlobal(
      "fetch",
      vi
        .fn()
        .mockResolvedValue(
          new Response('{"detail":"设备离线"}', { status: 503 }),
        ),
    );
    expect(await app.command("lamp", { brightness: 10 })).toBe(false);
    expect(app.state.devices.lamp?.brightness).toBe(80);
  });
  it("退出登录后不接收旧控制请求的状态结果", async () => {
    const app = useApp();
    app.state = previewData().state;
    sessionStorage.setItem("deskmate.token", "old");
    let resolve!: (response: Response) => void;
    vi.stubGlobal(
      "fetch",
      vi.fn(
        () =>
          new Promise<Response>((r) => {
            resolve = r;
          }),
      ),
    );
    const pending = app.command("lamp", { brightness: 10 });
    app.logout();
    resolve(
      new Response(
        '{"state":{"on":true,"brightness":10,"color_temp":4000,"online":true}}',
      ),
    );
    expect(await pending).toBe(false);
    expect(app.state).toBeNull();
    expect(app.busy).toBe(false);
  });
  it("退出预览清理 URL 标记，登录后刷新不会意外回到示例", () => {
    history.replaceState(null, "", "?preview=1#dashboard");
    const app = useApp();
    app.enterPreview();
    expect(location.search).toBe("?preview=1");
    app.logout();
    expect(location.search).toBe("");
  });
});
