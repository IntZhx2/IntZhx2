// 保留跨网络分块的行与事件，兼容 LF / CRLF、多行 data 和末尾无空行。
export class SSEParser {
  private buffer = "";
  private event = "message";
  private data: string[] = [];
  constructor(private emit: (event: string, data: unknown) => void) {}
  feed(chunk: string, final = false) {
    this.buffer += chunk;
    let index: number;
    while ((index = this.buffer.indexOf("\n")) >= 0) {
      this.line(this.buffer.slice(0, index).replace(/\r$/, ""));
      this.buffer = this.buffer.slice(index + 1);
    }
    if (final) {
      if (this.buffer) this.line(this.buffer.replace(/\r$/, ""));
      this.buffer = "";
      this.line("");
    }
  }
  private line(line: string) {
    if (line === "") {
      if (this.data.length) {
        const raw = this.data.join("\n");
        try {
          this.emit(this.event, JSON.parse(raw));
        } catch (error) {
          if (!(error instanceof SyntaxError)) throw error;
          throw new Error("收到的回复格式有误，请重新发送。");
        }
      }
      this.data = [];
      this.event = "message";
      return;
    }
    if (line.startsWith(":")) return;
    const split = line.indexOf(":");
    const field = split < 0 ? line : line.slice(0, split);
    let value = split < 0 ? "" : line.slice(split + 1);
    if (value.startsWith(" ")) value = value.slice(1);
    if (field === "event") this.event = value;
    if (field === "data") this.data.push(value);
  }
}
export async function readSSE(
  response: Response,
  emit: (event: string, data: unknown) => void,
) {
  if (!response.body) throw new Error("浏览器无法读取流式回复。");
  const reader = response.body.getReader(),
    decoder = new TextDecoder(),
    parser = new SSEParser(emit);
  try {
    while (true) {
      const { done, value } = await reader.read();
      if (done) {
        parser.feed(decoder.decode(), true);
        break;
      }
      parser.feed(decoder.decode(value, { stream: true }));
    }
  } finally {
    await reader.cancel().catch(() => {});
    reader.releaseLock();
  }
}
