import { describe, expect, it } from "vitest";
import { markdown } from "../src/lib/markdown";
describe("模型 Markdown 安全渲染", () => {
  it("剔除脚本、事件、危险链接和远程图片", () => {
    const html = markdown(
      '<script>alert(1)</script><img src="https://example.com/track" onerror="alert(1)"><a href="javascript:alert(1)">点击</a><svg onload="alert(1)"></svg>',
    );
    expect(html).not.toMatch(/<script|<img|onerror|onload|javascript:/i);
  });
  it("保留 Markdown 与代码，并对代码中的 HTML 转义", () => {
    const html = markdown('**桌伴**\n\n```python\nprint("<script>")\n```');
    expect(html).toContain("<strong>桌伴</strong>");
    expect(html).toContain("hljs");
    expect(html).not.toContain("<script>");
  });
});
