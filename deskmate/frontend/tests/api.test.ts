import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { request } from "../src/lib/api";
describe("API 登录隔离与错误", () => {
  beforeEach(() => {
    sessionStorage.clear();
    sessionStorage.setItem("deskmate.token", "first");
  });
  afterEach(() => vi.unstubAllGlobals());
  it("携带当前登录令牌", async () => {
    const fetcher = vi.fn().mockResolvedValue(
      new Response('{"ok":true}', {
        headers: { "Content-Type": "application/json" },
      }),
    );
    vi.stubGlobal("fetch", fetcher);
    expect(await request("/api/state")).toEqual({ ok: true });
    expect(
      new Headers(fetcher.mock.calls[0]![1].headers).get("Authorization"),
    ).toBe("Bearer first");
  });
  it("退出或切换账号后丢弃旧请求，避免串入新账号", async () => {
    let resolve!: (value: Response) => void;
    vi.stubGlobal(
      "fetch",
      vi.fn(
        () =>
          new Promise<Response>((r) => {
            resolve = r;
          }),
      ),
    );
    const promise = request("/api/state");
    sessionStorage.setItem("deskmate.token", "second");
    resolve(new Response("{}"));
    await expect(promise).rejects.toMatchObject({ name: "AbortError" });
  });
  it("认证过期触发登录恢复，并保留服务端说明", async () => {
    const expired = vi.fn();
    window.addEventListener("deskmate:unauthorized", expired);
    vi.stubGlobal(
      "fetch",
      vi
        .fn()
        .mockResolvedValue(
          new Response('{"detail":"登录已过期"}', { status: 401 }),
        ),
    );
    await expect(request("/api/state")).rejects.toMatchObject({
      status: 401,
      message: "登录已过期",
    });
    expect(expired).toHaveBeenCalledOnce();
    window.removeEventListener("deskmate:unauthorized", expired);
  });
  it("旧账号的 401 不会把新账号踢出登录", async () => {
    let resolve!: (value: Response) => void;
    const expired = vi.fn();
    window.addEventListener("deskmate:unauthorized", expired);
    vi.stubGlobal(
      "fetch",
      vi.fn(
        () =>
          new Promise<Response>((r) => {
            resolve = r;
          }),
      ),
    );
    const pending = request("/api/state");
    sessionStorage.setItem("deskmate.token", "new-user");
    resolve(new Response("{}", { status: 401 }));
    await expect(pending).rejects.toMatchObject({ name: "AbortError" });
    expect(expired).not.toHaveBeenCalled();
    window.removeEventListener("deskmate:unauthorized", expired);
  });
});
