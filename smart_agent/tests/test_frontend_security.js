// Run from any directory: node --test smart_agent/tests/test_frontend_security.js
const test = require("node:test");
const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");
const staticDir = path.join(__dirname, "../web/static");
const { render, escapeHtml, safeHref } = require(path.join(staticDir, "safe_markdown.js"));

test("raw HTML and quote characters are escaped in every text context", () => {
  const attack = '<img src=x onerror="alert(1)"> & \'quote\'';
  for (const source of [attack, `# ${attack}`, `> ${attack}`, `- ${attack}`, `| ${attack} |`]) {
    const html = render(source);
    assert.ok(html.includes(escapeHtml(attack)));
    assert.doesNotMatch(html, /<img|<script|<svg/);
  }
});

test("href quotes cannot add attributes or close an anchor", () => {
  const href = 'https://example.com/"onmouseover="alert(1)';
  assert.equal(render(`[visit](${href})`),
    '<p class="md-p"><a href="https://example.com/&quot;onmouseover=&quot;alert(1)" target="_blank" rel="noopener noreferrer" class="md-link">visit</a></p>');
  const html = render('[<svg/onload=alert(1)>](https://example.com/\'onclick=\'x)');
  assert.ok(html.includes('href="https://example.com/&#39;onclick=&#39;x"'));
  assert.ok(html.includes('&lt;svg/onload=alert(1)&gt;'));
  assert.equal((html.match(/<a /g) || []).length, 1);
});

for (const href of [
  "javascript:alert(1)", "JaVaScRiPt:alert(1)", "data:text/html,<svg/onload=alert(1)>",
  "vbscript:msgbox(1)", "file:///etc/passwd", "blob:https://example.com/id",
  "java\tscript:alert(1)", "java\nscript:alert(1)", "\u0000javascript:alert(1)",
  " javascript:alert(1)", "//evil.example/x", "/\\evil.example/x", "https:\\evil.example",
  "javascript&#58;alert(1)", "java&#x73;cript:alert(1)", "%6aavascript:alert(1)",
  "mailto:person@example.com?body=%0aInjected", "https://",
]) {
  test(`blocks unsafe or ambiguous href ${JSON.stringify(href)}`, () => {
    assert.equal(safeHref(href), null);
    assert.doesNotMatch(render(`[visit](${href})`), /<a\b/);
  });
}

test("safe protocols and local download paths keep fixed link attributes", () => {
  for (const href of ["https://example.com/a_(b)?x=1&y=2", "http://example.com/", "HTTPS://example.com/", "mailto:person@example.com", "/api/itinerary/download?filename=hello%20world.md", "#day-1", "?page=2"]) {
    assert.equal(safeHref(href), href);
    assert.equal(render(`[visit](${href})`), `<p class="md-p"><a href="${escapeHtml(href)}" target="_blank" rel="noopener noreferrer" class="md-link">visit</a></p>`);
  }
});

test("URL entities stay literal and cannot be decoded into attributes", () => {
  const href = 'https://example.com/?x=&quot;onfocus=&quot;x';
  assert.ok(render(`[x](${href})`).includes('href="https://example.com/?x=&amp;quot;onfocus=&amp;quot;x"'));
});

test("fenced code is never processed as inline Markdown or HTML", () => {
  const code = '  **bold** *italic* `code` [x](javascript:alert(1))\n<a href="x">text</a>\n%%CODE_BLOCK_0%%';
  assert.equal(render('```html\n' + code + '\n```'), `<pre class="code-block"><code class="lang-html">${escapeHtml(code)}</code></pre>`);
  assert.equal(render('~~~\n' + code + '\n~~~'), `<pre class="code-block"><code>${escapeHtml(code)}</code></pre>`);
  assert.equal(render('```\n' + code), `<pre class="code-block"><code>${escapeHtml(code)}</code></pre>`);
});

test("fence language cannot inject attributes and longer fences protect inner fences", () => {
  assert.equal(render('```js" onmouseover="x\n<script>x</script>\n```'), '<pre class="code-block"><code>&lt;script&gt;x&lt;/script&gt;</code></pre>');
  assert.equal(render('````js\n```\n[x](https://example.com)\n````'), '<pre class="code-block"><code class="lang-js">```\n[x](https://example.com)</code></pre>');
});

test("inline code protects links, emphasis, tags and nested backticks", () => {
  const code = '**bold** [x](https://example.com) <img src=x>';
  assert.equal(render('`' + code + '`'), `<p class="md-p"><code class="md-inline-code">${escapeHtml(code)}</code></p>`);
  assert.equal(render('``a ` b **c**``'), '<p class="md-p"><code class="md-inline-code">a ` b **c**</code></p>');
  assert.equal(render('**before `** [x](https://example.com)` after**'), '<p class="md-p"><strong>before <code class="md-inline-code">** [x](https://example.com)</code> after</strong></p>');
});

test("formatting around links never rewrites URL attributes or creates nested anchors", () => {
  assert.equal(render('**[go](https://example.com/**path**)**'), '<p class="md-p"><strong><a href="https://example.com/**path**" target="_blank" rel="noopener noreferrer" class="md-link">go</a></strong></p>');
  const html = render('[[inner](https://inner.example)](https://outer.example)');
  assert.equal((html.match(/<a /g) || []).length, 1);
});

test("headings, lists, quotes and tables retain styled safe formatting", () => {
  const html = render('# **Day 1**\n- *Park*\n1. `Train`\n> [map](https://example.com)\n\n| Stop | Time |\n| --- | --- |\n| **Park** | 10:00 |');
  for (const fragment of ['<h1 class="md-h1"><strong>Day 1</strong></h1>', '<ul class="md-ul">', '<ol class="md-ol">', '<blockquote class="md-quote">', '<table class="md-table">', '<td><strong>Park</strong></td>']) assert.ok(html.includes(fragment));
  assert.equal(render(null), "");
  assert.equal(render('%%CODE_BLOCK_0%%'), '<p class="md-p">%%CODE_BLOCK_0%%</p>');
});

test("browser export uses the identical pure renderer with no DOM dependency", () => {
  const context = vm.createContext({ URL });
  vm.runInContext(fs.readFileSync(path.join(staticDir, "safe_markdown.js"), "utf8"), context);
  assert.equal(context.SafeMarkdown.render('`<script>`'), render('`<script>`'));
});

// Minimal DOM harness: run actual application event handlers with deterministic
// API responses. No network, real API keys, cookie reads or third party packages.
async function appHarness({ configured = true, verified = false, model = "deepseek-chat", files = [], sessions = [], chatEvents = [] } = {}) {
  class Element {
    constructor() {
      this.listeners = {};
      this.children = [];
      this.style = {};
      this.dataset = {};
      this.attributes = {};
      this.selectors = new Map();
      this.value = "";
      this.textContent = "";
      this.innerHTML = "";
      this.classList = { add() {}, remove() {}, toggle() {}, contains() { return false; } };
    }
    addEventListener(name, callback) { this.listeners[name] = callback; }
    append(...children) { this.children.push(...children); }
    appendChild(child) { this.append(child); }
    replaceChildren(...children) { this.children = children; }
    setAttribute(name, value) { this.attributes[name] = value; }
    querySelectorAll() { return []; }
    querySelector(selector) {
      if (!this.selectors.has(selector)) this.selectors.set(selector, new Element());
      return this.selectors.get(selector);
    }
    focus() {}
  }
  const elements = new Map();
  const el = (id) => {
    if (!elements.has(id)) elements.set(id, new Element());
    return elements.get(id);
  };
  const sessionCards = sessions.map((session) => {
    const card = new Element();
    card.dataset.id = session.session_id;
    return card;
  });
  el("sessions-container").querySelectorAll = () => sessionCards;
  let boot;
  let config = { has_key: configured, verified, model, api_base: "https://api.deepseek.com/v1" };
  let testPasses = true;
  let clearPasses = true;
  const requests = [];
  const alerts = [];
  const pending = [];
  const context = vm.createContext({
    document: {
      getElementById: el,
      addEventListener: (_, cb) => { boot = cb; },
      querySelectorAll: () => [],
      createElement: () => new Element(),
    },
    window: { SafeMarkdown: { render, escapeHtml }, speechEngine: { stopSpeaking() {} } },
    TextDecoder,
    fetch: async (url, options = {}) => {
      requests.push({ url, ...options });
      let data;
      let ok = true;
      if (url === "/api/config" && options.method === "POST") {
        const body = JSON.parse(options.body);
        config = { has_key: true, verified: false, model: body.model, api_base: body.api_base };
        data = { status: "saved", ...config };
      } else if (url === "/api/config") data = { ...config };
      else if (url === "/api/config/test") {
        // A failed request can leave a previous server verification flag intact.
        if (testPasses) config.verified = true;
        ok = testPasses;
        data = { verified: testPasses, error: testPasses ? undefined : "unavailable" };
      } else if (url === "/api/sessions") data = { sessions };
      else if (url.startsWith("/api/session?id=")) data = { turns: [] };
      else if (url === "/api/itineraries") data = { itineraries: files };
      else if (url === "/api/session/new") data = { session_id: "chosen-session" };
      else if (url === "/api/clear") { ok = clearPasses; data = { status: "cleared", error: clearPasses ? undefined : "clear denied" }; }
      else if (url === "/api/chat") {
        let index = 0;
        return { ok: true, body: { getReader: () => ({ read: async () => index < chatEvents.length
          ? { done: false, value: Buffer.from(`data: ${JSON.stringify(chatEvents[index++])}\n\n`) }
          : { done: true } }) } };
      }
      else throw new Error(`Unexpected request ${url}`);
      return { ok, json: async () => data };
    },
    alert: (message) => alerts.push(message), confirm: () => true,
    setTimeout: (callback) => pending.push(callback), console,
  });
  vm.runInContext(fs.readFileSync(path.join(staticDir, "app.js"), "utf8"), context);
  boot();
  const settle = () => new Promise((resolve) => setImmediate(resolve));
  await settle();
  return { el, sessionCards, requests, alerts, settle, setTestResult: (value) => { testPasses = value; }, setClearResult: (value) => { clearPasses = value; } };
}

test("configured status is plain text and becomes online only after verification", async () => {
  const model = '<img src=x onerror="alert(1)">';
  const app = await appHarness({ model });
  assert.equal(app.el("status-label").textContent, `已配置 · 尚未验证 (${model})`);
  assert.equal(app.el("status-label").innerHTML, "");
  assert.equal(app.el("agent-status-pill").className, "status-pill");
  await app.el("btn-test-config").listeners.click();
  assert.equal(app.el("agent-status-pill").className, "status-pill online");
  assert.equal(app.el("status-label").textContent, `模型测试通过 (${model})`);
  const request = app.requests.find((request) => request.url === "/api/config/test");
  assert.equal(request.method, "POST");
  assert.deepEqual(JSON.parse(request.body), {});
  app.setTestResult(false);
  await app.el("btn-test-config").listeners.click();
  assert.equal(app.el("agent-status-pill").className, "status-pill");
  assert.ok(app.el("status-label").textContent.includes("测试未通过"));
  assert.ok(app.alerts.some((message) => message.includes("测试失败")));
});

test("saving configuration resets verification and does not invoke the model test", async () => {
  const app = await appHarness({ verified: true });
  app.el("input-api-key").value = "user-supplied-test-key";
  await app.el("btn-save-config").listeners.click();
  assert.equal(app.el("agent-status-pill").className, "status-pill");
  assert.equal(app.el("input-api-key").value, "");
  assert.ok(app.alerts.some((message) => message.includes("配置已保存")));
  assert.ok(!app.requests.some((request) => request.url === "/api/config/test"));
  assert.equal(app.el("btn-save-config").disabled, false);
  assert.equal(app.el("btn-test-config").disabled, false);
});

test("missing key does not show online and an incomplete save makes no POST", async () => {
  const app = await appHarness({ configured: false, verified: true });
  assert.equal(app.el("agent-status-pill").className, "status-pill offline");
  await app.el("btn-save-config").listeners.click();
  assert.ok(!app.requests.some((request) => request.method === "POST"));
});

test("opening a saved session is read only and selects it locally for scoped clear", async () => {
  const sessionId = "archived-session";
  const app = await appHarness({ sessions: [{ session_id: sessionId, title: "Saved trip", turn_count: 0 }] });
  app.sessionCards[0].listeners.click({ target: { closest: () => null } });
  await app.settle();
  const open = app.requests.find((request) => request.url === `/api/session?id=${sessionId}`);
  assert.ok(open);
  assert.equal(open.method, undefined);
  assert.ok(!app.requests.some((request) => request.method === "POST"));
  await app.el("btn-clear-chat").listeners.click();
  const clear = app.requests.find((request) => request.url === "/api/clear");
  assert.deepEqual(JSON.parse(clear.body), { session_id: sessionId });
});

test("clear only targets the chosen session and respects failure responses", async () => {
  const app = await appHarness();
  await app.el("btn-clear-chat").listeners.click();
  assert.ok(!app.requests.some((request) => request.url === "/api/clear"));
  await app.el("btn-top-new-chat").listeners.click();
  app.setClearResult(false);
  await app.el("btn-clear-chat").listeners.click();
  assert.equal(app.requests.filter((request) => request.url === "/api/session/new").length, 1);
  assert.ok(app.alerts.some((message) => message.includes("clear denied")));
  app.setClearResult(true);
  await app.el("btn-clear-chat").listeners.click();
  const clear = app.requests.filter((request) => request.url === "/api/clear");
  assert.equal(clear.length, 2);
  for (const request of clear) {
    assert.equal(request.method, "POST");
    assert.deepEqual(JSON.parse(request.body), { session_id: "chosen-session" });
    assert.equal(request.headers["Content-Type"], "application/json");
  }
});

test("saved itinerary downloads use encoded same origin GET links and text labels", async () => {
  const filename = '广州 & "<img src=x>.md';
  const app = await appHarness({ files: [{ filename, size: "2 KB" }] });
  const link = app.el("itineraries-container").children[0];
  assert.equal(link.href, `/api/itinerary/download?filename=${encodeURIComponent(filename)}`);
  assert.equal(link.attributes.download, "");
  assert.equal(link.children[0].textContent, filename);
  assert.equal(link.children[0].innerHTML, "");
  for (const request of app.requests) {
    assert.ok(request.url.startsWith("/api/"));
    assert.equal(request.credentials, undefined); // browser default: same-origin cookies
    assert.ok(!request.headers?.Authorization);
  }
});

for (const [name, chatEvents] of [
  ["early session event without done", [{ type: "session", session_id: "retry-session" }]],
  ["session followed by tool and error without an ID", [
    { type: "session", session_id: "retry-session" },
    { type: "tool_call", details: { tool: "weather", arguments: {}, call_id: "call-1" } },
    { type: "error", error: "model unavailable" },
  ]],
  ["error carrying the session ID", [{ type: "error", session_id: "retry-session", error: "model unavailable" }]],
  ["existing done event", [{ type: "done", session_id: "retry-session" }]],
]) {
  test(`chat retry retains the server session ID from ${name}`, async () => {
    const app = await appHarness({ chatEvents });
    app.el("chat-textarea").value = "Plan a trip";
    await app.el("btn-send").listeners.click();
    assert.equal(app.el("btn-send").disabled, false);
    app.el("chat-textarea").value = "Retry planning";
    await app.el("btn-send").listeners.click();
    const chats = app.requests.filter((request) => request.url === "/api/chat");
    assert.equal(chats.length, 2);
    assert.equal(JSON.parse(chats[0].body).session_id, null);
    assert.equal(JSON.parse(chats[1].body).session_id, "retry-session");
  });
}
