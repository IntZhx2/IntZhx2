import { describe, expect, it } from "vitest";
import { SSEParser } from "../src/lib/sse";
describe("SSE 流解析", () => {
  it("逐字符拼接中文、跨行 CRLF 和结束事件", () => {
    const events: [string, unknown][] = [];
    const parser = new SSEParser((name, data) => events.push([name, data]));
    const source =
      ': keepalive\r\nevent: delta\r\ndata: {"text":"你好，桌伴"}\r\n\r\nevent: done\ndata: {"reply":"完成",\ndata: "conversation_id":"abc"}\n\n';
    for (const char of source) parser.feed(char);
    parser.feed("", true);
    expect(events).toEqual([
      ["delta", { text: "你好，桌伴" }],
      ["done", { reply: "完成", conversation_id: "abc" }],
    ]);
  });
  it("保留末尾没有空行的事件", () => {
    const events: unknown[] = [];
    const parser = new SSEParser((_event, data) => events.push(data));
    parser.feed('event: done\ndata: {"reply":"done"}', true);
    expect(events).toEqual([{ reply: "done" }]);
  });
  it("无效 JSON 会明确报错，避免无声结束", () => {
    expect(() =>
      new SSEParser(() => {}).feed("event: delta\ndata: nope\n\n"),
    ).toThrow("回复格式");
  });
  it("传播服务端业务错误", () => {
    expect(() =>
      new SSEParser(() => {
        throw new Error("模型未配置");
      }).feed("event: error\ndata: {}\n\n"),
    ).toThrow("模型未配置");
  });
});
