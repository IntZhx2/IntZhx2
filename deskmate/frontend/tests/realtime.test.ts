import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { Realtime } from "../src/lib/realtime";
class Socket {
  static OPEN = 1;
  static all: Socket[] = [];
  readyState = 1;
  onopen?: () => void;
  onmessage?: (event: { data: string }) => void;
  onclose?: (event: { code: number }) => void;
  onerror?: () => void;
  send = vi.fn<(data: string) => void>();
  close = vi.fn(() => this.onclose?.({ code: 1000 }));
  constructor(public url: string) {
    Socket.all.push(this);
  }
  message(name: string, payload: unknown, type = "event") {
    this.onmessage?.({ data: JSON.stringify({ v: 2, name, payload, type }) });
  }
}
describe("实时状态同步", () => {
  let client: Realtime;
  const handlers = {
    state: vi.fn(),
    event: vi.fn(),
    status: vi.fn(),
    expired: vi.fn(),
  };
  beforeEach(() => {
    vi.useFakeTimers();
    vi.clearAllMocks();
    Socket.all = [];
    vi.stubGlobal("WebSocket", Socket);
    client = new Realtime("secret", handlers);
    client.connect();
  });
  afterEach(() => {
    client.stop();
    vi.useRealTimers();
    vi.unstubAllGlobals();
  });
  it("收到快照后合并节流增量，顶层对象使用最新完整值", () => {
    const socket = Socket.all[0]!;
    socket.onopen?.();
    socket.message("state.snapshot", { devices: { lamp: { on: false } } });
    expect(handlers.state).toHaveBeenCalledWith(
      { devices: { lamp: { on: false } } },
      true,
    );
    socket.message("state.patch", { devices: { lamp: { on: true } } });
    socket.message("state.patch", { focus: { state: "focusing" } });
    socket.message("state.patch", { devices: { lamp: { on: false } } });
    vi.advanceTimersByTime(100);
    expect(handlers.state).toHaveBeenLastCalledWith(
      { devices: { lamp: { on: false } }, focus: { state: "focusing" } },
      false,
    );
  });
  it("快照清除之前尚未刷出的增量，避免重连后旧状态覆盖", () => {
    const socket = Socket.all[0]!;
    socket.message("state.patch", { focus: { state: "idle" } });
    socket.message("state.snapshot", { focus: { state: "focusing" } });
    vi.advanceTimersByTime(200);
    expect(handlers.state).toHaveBeenCalledTimes(1);
  });
  it("1 秒、2 秒退避重连；停止后不再自动连接", () => {
    Socket.all[0]!.close();
    vi.advanceTimersByTime(999);
    expect(Socket.all).toHaveLength(1);
    vi.advanceTimersByTime(1);
    expect(Socket.all).toHaveLength(2);
    Socket.all[1]!.close();
    vi.advanceTimersByTime(1999);
    expect(Socket.all).toHaveLength(2);
    client.stop();
    vi.advanceTimersByTime(60000);
    expect(Socket.all).toHaveLength(2);
  });
  it("认证失效交回登录，避免无休止重连", () => {
    Socket.all[0]!.onclose?.({ code: 4401 });
    vi.advanceTimersByTime(60000);
    expect(handlers.expired).toHaveBeenCalledOnce();
    expect(Socket.all).toHaveLength(1);
  });
  it("响应心跳，并忽略无效消息和未知事件", () => {
    const socket = Socket.all[0]!;
    socket.onopen?.();
    socket.message("", {}, "ping");
    expect(JSON.parse(socket.send.mock.calls[0]![0] as string).type).toBe(
      "pong",
    );
    socket.onmessage?.({ data: "not-json" });
    socket.message("unknown", {});
    expect(handlers.event).not.toHaveBeenCalled();
    socket.message("notify", { title: "你好" });
    expect(handlers.event).toHaveBeenCalledOnce();
  });
  it("超过 60 秒没有服务端消息，断线并进入恢复", () => {
    Socket.all[0]!.onopen?.();
    vi.advanceTimersByTime(60000);
    expect(Socket.all[0]!.close).toHaveBeenCalled();
    expect(handlers.status).toHaveBeenLastCalledWith("reconnecting");
  });
});
