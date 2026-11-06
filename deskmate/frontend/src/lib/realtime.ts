import type { Envelope, Snapshot } from "../types/contracts";
interface Handlers {
  state: (patch: Partial<Snapshot>, full: boolean) => void;
  event: (message: Envelope) => void;
  status: (
    status: "connecting" | "online" | "reconnecting" | "offline",
  ) => void;
  expired: () => void;
}
export class Realtime {
  private socket: WebSocket | null = null;
  private retry?: ReturnType<typeof setTimeout>;
  private heartbeat?: ReturnType<typeof setInterval>;
  private flush?: ReturnType<typeof setTimeout>;
  private pending: Partial<Snapshot> = {};
  private attempts = 0;
  private stopped = false;
  private seen = 0;
  constructor(
    private token: string,
    private handlers: Handlers,
  ) {}
  connect() {
    this.stopped = false;
    this.handlers.status(this.attempts ? "reconnecting" : "connecting");
    const socket = new WebSocket(
      `${location.protocol === "https:" ? "wss" : "ws"}://${location.host}/ws/web?token=${encodeURIComponent(this.token)}`,
    );
    this.socket = socket;
    socket.onopen = () => {
      if (this.stopped || socket !== this.socket) return;
      this.attempts = 0;
      this.seen = Date.now();
      this.handlers.status("online");
      this.heartbeat = setInterval(() => {
        if (Date.now() - this.seen >= 60000) {
          socket.close();
          return;
        }
        this.send("", {}, "ping");
      }, 20000);
    };
    socket.onmessage = (event) => {
      if (this.stopped || socket !== this.socket) return;
      this.seen = Date.now();
      let msg: Envelope;
      try {
        msg = JSON.parse(event.data);
      } catch {
        return;
      }
      if (msg.v !== 2 || !msg.payload || typeof msg.payload !== "object")
        return;
      if (msg.type === "ping") {
        this.send("", {}, "pong");
        return;
      }
      if (msg.type !== "event") return;
      if (msg.name === "state.snapshot") {
        clearTimeout(this.flush);
        this.flush = undefined;
        this.pending = {};
        this.handlers.state(msg.payload as Partial<Snapshot>, true);
      } else if (msg.name === "state.patch") {
        Object.assign(this.pending, msg.payload);
        if (!this.flush)
          this.flush = setTimeout(() => {
            this.handlers.state(this.pending, false);
            this.pending = {};
            this.flush = undefined;
          }, 100);
      } else if (["notify", "assist.result", "voice.log"].includes(msg.name))
        this.handlers.event(msg);
    };
    socket.onclose = (event) => {
      if (this.stopped || socket !== this.socket) return;
      clearInterval(this.heartbeat);
      clearTimeout(this.flush);
      this.flush = undefined;
      this.pending = {};
      if (event.code === 4401) {
        this.stop();
        this.handlers.expired();
        return;
      }
      this.handlers.status("reconnecting");
      this.retry = setTimeout(
        () => this.connect(),
        Math.min(30000, 1000 * 2 ** this.attempts++),
      );
    };
    socket.onerror = () => socket.close();
  }
  send(
    name: string,
    payload: Record<string, unknown> = {},
    type: Envelope["type"] = "event",
  ) {
    if (this.socket?.readyState === WebSocket.OPEN) {
      this.socket.send(
        JSON.stringify({
          v: 2,
          type,
          id: crypto.randomUUID(),
          ts: new Date().toISOString(),
          name,
          payload,
        }),
      );
      return true;
    }
    return false;
  }
  stop() {
    this.stopped = true;
    clearTimeout(this.retry);
    clearTimeout(this.flush);
    clearInterval(this.heartbeat);
    this.pending = {};
    this.flush = undefined;
    this.socket?.close();
    this.socket = null;
    this.handlers.status("offline");
  }
}
