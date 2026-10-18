/**
 * TravelAgent 旅游规划前端主交互引擎
 * 专注于地点、交通方式、特定时间点约束的一条龙旅游攻略定制，强制接入真实大模型。
 */

document.addEventListener("DOMContentLoaded", () => {
  // DOM 核心元素
  const chatStream = document.getElementById("chat-stream");
  const chatTextarea = document.getElementById("chat-textarea");
  const btnSend = document.getElementById("btn-send");
  const btnMic = document.getElementById("btn-mic");
  const btnClearChat = document.getElementById("btn-clear-chat");
  const recordingBanner = document.getElementById("recording-banner");
  const itinerariesContainer = document.getElementById("itineraries-container");
  const btnRefreshItineraries = document.getElementById("btn-refresh-itineraries");
  const agentStatusPill = document.getElementById("agent-status-pill");
  const statusLabel = document.getElementById("status-label");

  // 侧边栏出行组合表单
  const guideCity = document.getElementById("guide-city");
  const guideDays = document.getElementById("guide-days");
  const guideTransit = document.getElementById("guide-transit");
  const guideConstraint = document.getElementById("guide-constraint");
  const guidePref = document.getElementById("guide-pref");
  const btnQuickGenerate = document.getElementById("btn-quick-generate");

  // 模态弹窗配置元素
  const btnOpenConfig = document.getElementById("btn-open-config");
  const btnCloseModal = document.getElementById("btn-close-modal");
  const configModal = document.getElementById("config-modal");
  const inputApiBase = document.getElementById("input-api-base");
  const inputApiKey = document.getElementById("input-api-key");
  const inputModel = document.getElementById("input-model");
  const btnSaveConfig = document.getElementById("btn-save-config");

  let hasValidApiKey = false;

  // 常用模型提供商预设
  const PRESETS = {
    cpa: {
      base: "http://127.0.0.1:8317/v1",
      model: "gemini-3.5-flash-lite",
      key: "123456",
    },
    bailian: {
      base: "https://dashscope.aliyuncs.com/compatible-mode/v1",
      model: "qwen-plus",
      key: "",
    },
    deepseek: {
      base: "https://api.deepseek.com/v1",
      model: "deepseek-chat",
      key: "",
    },
    zhipu: {
      base: "https://open.bigmodel.cn/api/paas/v4",
      model: "glm-4-flash",
      key: "",
    },
    silicon: {
      base: "https://api.siliconflow.cn/v1",
      model: "Qwen/Qwen2.5-7B-Instruct",
      key: "",
    },
    openai: {
      base: "https://api.openai.com/v1",
      model: "gpt-4o-mini",
      key: "",
    },
  };

  // 1. 初始化检查配置与归档
  checkConfig();
  loadItineraries();

  // 2. 弹窗交互绑定
  btnOpenConfig.addEventListener("click", () => {
    configModal.classList.add("active");
    inputApiKey.focus();
  });

  btnCloseModal.addEventListener("click", () => {
    configModal.classList.remove("active");
  });

  configModal.addEventListener("click", (e) => {
    if (e.target === configModal) configModal.classList.remove("active");
  });

  // 3. 厂商预设切换
  document.querySelectorAll(".preset-pill").forEach((pill) => {
    pill.addEventListener("click", () => {
      document.querySelectorAll(".preset-pill").forEach((p) => p.classList.remove("active"));
      pill.classList.add("active");
      const key = pill.dataset.preset;
      if (PRESETS[key]) {
        inputApiBase.value = PRESETS[key].base;
        inputModel.value = PRESETS[key].model;
        if (PRESETS[key].key) {
          inputApiKey.value = PRESETS[key].key;
        }
      }
    });
  });

  // 4. 保存 API 配置
  btnSaveConfig.addEventListener("click", async () => {
    const key = inputApiKey.value.trim();
    const base = inputApiBase.value.trim();
    const model = inputModel.value.trim();

    if (!key) {
      alert("请输入有效的 API Key！系统已关闭伪离线模式，必须配置真实大模型才能进行智能规划。");
      return;
    }

    btnSaveConfig.disabled = true;
    btnSaveConfig.innerHTML = '<i class="fa-solid fa-spinner fa-spin"></i> 正在连接大模型...';

    try {
      const resp = await fetch("/api/config", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ api_key: key, api_base: base, model: model }),
      });
      const data = await resp.json();
      if (!resp.ok) throw new Error(data.error || "配置失败");

      alert("🎉 " + data.message);
      configModal.classList.remove("active");
      checkConfig();
    } catch (e) {
      alert("保存失败: " + e.message);
    } finally {
      btnSaveConfig.disabled = false;
      btnSaveConfig.innerHTML = '<i class="fa-solid fa-check"></i> 保存并启用真实大模型';
    }
  });

  // 5. 灵感提示词点击直接填入
  document.querySelectorAll(".prompt-chip").forEach((chip) => {
    chip.addEventListener("click", () => {
      chatTextarea.value = chip.dataset.text;
      chatTextarea.focus();
      triggerSend();
    });
  });

  // 6. 快捷生成一条龙攻略按钮
  btnQuickGenerate.addEventListener("click", () => {
    const city = guideCity.value.trim() || "广州";
    const days = guideDays.value;
    const transit = guideTransit.value;
    const constraint = guideConstraint.value.trim();
    const pref = guidePref.value.trim();

    let prompt = `我想去【${city}】进行【${days}】旅游。\n- 交通偏好：${transit}；`;
    if (constraint) prompt += `\n- 关键时间点约束：${constraint}；`;
    if (pref) prompt += `\n- 美食与喜好：${pref}；`;
    prompt += `\n请通过 MCP 工具为我查询最新气象与交通路线，自动生成包含景点门票预约、交通换乘指引和地道美食的一条龙深度定制攻略。`;

    chatTextarea.value = prompt;
    triggerSend();
  });

  // 7. 输入框回车触发发送
  chatTextarea.addEventListener("keydown", (e) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      triggerSend();
    }
  });

  btnSend.addEventListener("click", triggerSend);

  // 8. 麦克风语音输入 (STT)
  btnMic.addEventListener("click", () => {
    window.speechEngine.startListening(
      (text, isFinal) => {
        chatTextarea.value = text;
        if (isFinal) {
          setTimeout(() => triggerSend(), 400);
        }
      },
      (listening) => {
        if (listening) {
          btnMic.classList.add("recording");
          recordingBanner.classList.add("active");
        } else {
          btnMic.classList.remove("recording");
          recordingBanner.classList.remove("active");
        }
      }
    );
  });

  // 9. 清空会话
  btnClearChat.addEventListener("click", async () => {
    if (!confirm("确定要清空当前的出行规划与对话记忆吗？")) return;
    try {
      await fetch("/api/clear", { method: "POST" });
      chatStream.innerHTML = `
        <div class="chat-message assistant">
          <div class="msg-avatar"><i class="fa-solid fa-compass"></i></div>
          <div class="msg-bubble">
            <div class="msg-text">
              <p>🧹 上下文记忆已重置。您可以开启全新的旅游目的地规划！</p>
            </div>
          </div>
        </div>
      `;
    } catch (e) {
      alert("清空失败: " + e.message);
    }
  });

  // 刷新历史归档
  btnRefreshItineraries.addEventListener("click", loadItineraries);

  /**
   * 触发行程需求发送与大模型交互
   */
  async function triggerSend() {
    const text = chatTextarea.value.trim();
    if (!text) return;

    if (!hasValidApiKey) {
      alert("⚠️ 请先配置大模型 API Key！\n系统已完全关闭本地伪离线模式，必须连接真实大语言模型才能为您进行智能规划。");
      configModal.classList.add("active");
      inputApiKey.focus();
      return;
    }

    appendUserMessage(text);
    chatTextarea.value = "";
    chatTextarea.style.height = "auto";
    btnSend.disabled = true;

    // 创建即时流式卡片 (所调即所显，实时展示思考与工具调用)
    const liveMsg = createLiveAssistantMessage();
    scrollToBottom();

    try {
      const resp = await fetch("/api/chat", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ message: text, stream: true }),
      });

      if (!resp.ok) {
        const errData = await resp.json().catch(() => ({}));
        throw new Error(errData.error || `请求失败 (HTTP ${resp.status})`);
      }

      const reader = resp.body.getReader();
      const decoder = new TextDecoder();
      let buffer = "";

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        buffer += decoder.decode(value, { stream: true });
        const blocks = buffer.split("\n\n");
        buffer = blocks.pop();

        for (const block of blocks) {
          for (const line of block.split("\n")) {
            if (line.startsWith("data: ")) {
              try {
                const data = JSON.parse(line.slice(6));
                handleStreamEvent(liveMsg, data);
              } catch (e) {
                console.warn("解析 SSE 帧失败:", e, line);
              }
            }
          }
        }
      }

      // 消费残余数据
      if (buffer.startsWith("data: ")) {
        try {
          const data = JSON.parse(buffer.slice(6));
          handleStreamEvent(liveMsg, data);
        } catch (e) {}
      }

      loadItineraries();
    } catch (e) {
      liveMsg.showError(e.message);
    } finally {
      btnSend.disabled = false;
      liveMsg.finish();
      scrollToBottom();
    }
  }

  function appendUserMessage(text) {
    const row = document.createElement("div");
    row.className = "chat-message user";
    row.innerHTML = `
      <div class="msg-avatar"><i class="fa-solid fa-user"></i></div>
      <div class="msg-bubble">
        <div class="msg-text">${escapeHtml(text)}</div>
        <div class="msg-timestamp">${getCurrentTime()}</div>
      </div>
    `;
    chatStream.appendChild(row);
  }

  function appendAssistantMessage(text) {
    const row = document.createElement("div");
    row.className = "chat-message assistant";
    row.innerHTML = `
      <div class="msg-avatar"><i class="fa-solid fa-compass"></i></div>
      <div class="msg-bubble">
        <div class="msg-text">${formatMarkdown(text)}</div>
        <div class="msg-timestamp">${getCurrentTime()}</div>
      </div>
    `;
    chatStream.appendChild(row);
  }

  function createLiveAssistantMessage() {
    const row = document.createElement("div");
    row.className = "chat-message assistant";

    row.innerHTML = `
      <div class="msg-avatar"><i class="fa-solid fa-compass"></i></div>
      <div class="msg-bubble">
        <div class="live-trace-box"></div>
        <div class="live-status-bar">
          <i class="fa-solid fa-spinner fa-spin"></i>
          <span class="live-status-text">TravelAgent 正在梳理出行约束并规划行程...</span>
        </div>
        <div class="msg-text final-answer" style="display: none;"></div>
        <div class="msg-timestamp">${getCurrentTime()}</div>
      </div>
    `;
    chatStream.appendChild(row);

    const traceBox = row.querySelector(".live-trace-box");
    const statusBar = row.querySelector(".live-status-bar");
    const statusText = row.querySelector(".live-status-text");
    const answerBox = row.querySelector(".final-answer");

    return {
      element: row,
      addThought(content) {
        const step = document.createElement("div");
        step.className = "live-trace-step thought";
        step.innerHTML = `
          <div class="live-step-header">
            <span><i class="fa-solid fa-brain"></i> <strong>智能体思考规划</strong></span>
          </div>
          <div class="live-step-body">${formatMarkdown(content)}</div>
        `;
        traceBox.appendChild(step);
        statusText.innerText = "正在分析硬性时间约束与游玩要素...";
        scrollToBottom();
      },
      addToolCall(tool, args, callId) {
        const step = document.createElement("div");
        step.className = "live-trace-step running";
        step.id = `tool-step-${callId}`;
        const argsStr = typeof args === "object" ? JSON.stringify(args, null, 2) : args;
        step.innerHTML = `
          <div class="live-step-header">
            <span><i class="fa-solid fa-spinner fa-spin"></i> <strong>正在调用工具:</strong> ${escapeHtml(tool)}</span>
            <span class="tool-tag">${escapeHtml(tool)}</span>
          </div>
          <div class="live-step-body">
            <div><small style="color: var(--text-muted)">传入参数:</small> <code class="md-inline-code">${escapeHtml(argsStr)}</code></div>
            <div class="tool-result-area" style="display: none; margin-top: 6px; padding-top: 6px; border-top: 1px dashed var(--border-subtle);"></div>
          </div>
        `;
        traceBox.appendChild(step);
        statusText.innerText = `正在执行 MCP 工具: ${tool}...`;
        scrollToBottom();
      },
      addToolResult(tool, isError, content, callId) {
        let step = traceBox.querySelector(`#tool-step-${callId}`);
        if (!step) {
          step = document.createElement("div");
          step.className = "live-trace-step";
          traceBox.appendChild(step);
        }
        step.classList.remove("running");
        step.classList.add(isError ? "error" : "success");

        const header = step.querySelector(".live-step-header");
        if (header) {
          if (isError) {
            header.innerHTML = `
              <span><i class="fa-solid fa-circle-exclamation" style="color: var(--morandi-rose)"></i> <strong>工具执行反馈:</strong> ${escapeHtml(tool)}</span>
              <span class="tool-tag" style="background-color: var(--morandi-rose-light); color: var(--morandi-rose)">真实反馈</span>
            `;
          } else {
            header.innerHTML = `
              <span><i class="fa-solid fa-circle-check" style="color: var(--morandi-sage)"></i> <strong>工具执行成功:</strong> ${escapeHtml(tool)}</span>
              <span class="tool-tag" style="background-color: var(--morandi-sage-light); color: var(--morandi-sage)">已完成</span>
            `;
          }
        }

        const resArea = step.querySelector(".tool-result-area");
        if (resArea) {
          resArea.style.display = "block";
          resArea.innerHTML = `<small style="color: var(--text-muted)">工具返回结果:</small><div>${formatMarkdown(content)}</div>`;
        }

        statusText.innerText = `已获取 ${tool} 数据，正在进行下一步统筹规划...`;
        scrollToBottom();
      },
      setAnswer(answer) {
        answerBox.style.display = "block";
        answerBox.innerHTML = formatMarkdown(answer);
        statusBar.style.display = "none";
        scrollToBottom();
      },
      showError(err) {
        statusBar.className = "live-status-bar error";
        statusBar.innerHTML = `<i class="fa-solid fa-circle-xmark"></i> <span>请求异常: ${escapeHtml(err)}</span>`;
      },
      finish() {
        if (statusBar && statusBar.style.display !== "none" && answerBox.style.display !== "none") {
          statusBar.style.display = "none";
        }
      },
    };
  }

  function handleStreamEvent(liveMsg, data) {
    if (data.type === "thought" && data.content) {
      liveMsg.addThought(data.content);
    } else if (data.type === "tool_call") {
      const tool = data.details ? data.details.tool : (data.content || "");
      const args = data.details ? data.details.arguments : {};
      const callId = data.details ? data.details.call_id : "call_" + Math.random().toString(36).slice(2, 7);
      liveMsg.addToolCall(tool, args, callId);
    } else if (data.type === "tool_result") {
      const tool = data.details ? data.details.tool : "";
      const isError = data.details ? data.details.is_error : false;
      const callId = data.details ? data.details.call_id : "";
      liveMsg.addToolResult(tool, isError, data.content, callId);
    } else if (data.type === "answer" && data.content) {
      liveMsg.setAnswer(data.content);
    } else if (data.type === "done") {
      if (data.result && data.result.answer) {
        liveMsg.setAnswer(data.result.answer);
      }
      liveMsg.finish();
    } else if (data.type === "error") {
      liveMsg.showError(data.error);
    }
  }

  /**
   * 检查系统 API 配置状态
   */
  async function checkConfig() {
    try {
      const resp = await fetch("/api/config");
      const data = await resp.json();
      hasValidApiKey = data.has_key;

      if (hasValidApiKey) {
        agentStatusPill.className = "status-pill online";
        statusLabel.innerHTML = `在线大模型 (${data.model})`;
      } else {
        agentStatusPill.className = "status-pill offline";
        statusLabel.innerHTML = "未配置 API Key (请点击配置)";
        // 初次加载若无 Key，轻柔提示用户打开弹窗
        setTimeout(() => {
          configModal.classList.add("active");
        }, 600);
      }
    } catch (e) {
      console.warn("检查配置异常", e);
    }
  }

  /**
   * 加载归档攻略列表
   */
  async function loadItineraries() {
    try {
      const resp = await fetch("/api/itineraries");
      const data = await resp.json();
      const files = data.itineraries || [];
      if (files.length === 0) {
        itinerariesContainer.innerHTML = '<div class="empty-state">暂未归档旅游攻略，对智能体说“保存此行程”即可归档至本地工作空间</div>';
        return;
      }

      itinerariesContainer.innerHTML = files
        .map(
          (f) => `
        <div class="itinerary-card" onclick="alert('该攻略已保存在本地工作区 data/workspace/${escapeHtml(f.filename)}')">
          <div class="itinerary-card-title">📄 ${escapeHtml(f.filename)}</div>
          <div class="itinerary-card-meta">${escapeHtml(f.size)}</div>
        </div>
      `
        )
        .join("");
    } catch (e) {
      itinerariesContainer.innerHTML = '<div class="empty-state">加载归档文件异常</div>';
    }
  }

  function scrollToBottom() {
    chatStream.scrollTop = chatStream.scrollHeight;
  }

  function removeElement(id) {
    const el = document.getElementById(id);
    if (el) el.remove();
  }

  function getCurrentTime() {
    const now = new Date();
    return `${now.getHours().toString().padStart(2, "0")}:${now.getMinutes().toString().padStart(2, "0")}`;
  }

  function escapeHtml(str) {
    if (!str) return "";
    return str
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;")
      .replace(/'/g, "&#039;");
  }

  function formatMarkdown(raw) {
    if (!raw) return "";

    // 1. 保护并抽取代码块
    const codeBlocks = [];
    let text = raw.replace(/```([\w-]*)\n([\s\S]*?)```/g, (match, lang, code) => {
      const idx = codeBlocks.length;
      codeBlocks.push(
        `<pre class="code-block"><code class="lang-${escapeHtml(lang)}">${escapeHtml(code.trim())}</code></pre>`
      );
      return `\n%%CODE_BLOCK_${idx}%%\n`;
    });

    // 2. 基础 HTML 实体转义
    text = text.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");

    // 恢复 blockquote 标记 (> 开头)
    text = text.replace(/^(&gt;|>)\s?(.*)$/gm, "> $2");

    // 3. 逐行解析
    const lines = text.split("\n");
    const output = [];
    let inList = null; // 'ul' | 'ol' | null
    let tableRows = [];

    function closeList() {
      if (inList) {
        output.push(`</${inList}>`);
        inList = null;
      }
    }

    function flushTable() {
      if (tableRows.length === 0) return;
      let html = '<div class="table-container"><table class="md-table">';
      let isHeader = true;
      for (let i = 0; i < tableRows.length; i++) {
        const row = tableRows[i];
        if (i === 1 && row.every((cell) => /^:?-+:?$/.test(cell.trim()))) {
          continue;
        }
        if (isHeader) {
          html += '<thead><tr>' + row.map((c) => `<th>${c}</th>`).join("") + '</tr></thead><tbody>';
          isHeader = false;
        } else {
          html += '<tr>' + row.map((c) => `<td>${c}</td>`).join("") + '</tr>';
        }
      }
      if (!isHeader) html += '</tbody>';
      html += '</table></div>';
      output.push(html);
      tableRows = [];
    }

    for (let i = 0; i < lines.length; i++) {
      let line = lines[i];

      // 检查代码块
      if (/^%%CODE_BLOCK_(\d+)%%$/.test(line.trim())) {
        closeList();
        flushTable();
        const blockIdx = parseInt(RegExp.$1, 10);
        output.push(codeBlocks[blockIdx]);
        continue;
      }

      // 检查 Markdown 表格
      if (line.trim().startsWith("|") && line.trim().endsWith("|")) {
        closeList();
        const cells = line.trim().slice(1, -1).split("|").map((c) => c.trim());
        tableRows.push(cells);
        continue;
      } else {
        flushTable();
      }

      // 检查水平分割线
      if (/^(\-{3,}|\*{3,}|_{3,})$/.test(line.trim())) {
        closeList();
        output.push('<hr class="md-hr" />');
        continue;
      }

      // 检查各级标题 (h1 到 h6，尤其彻底支持 #### 与 #####)
      const headingMatch = line.match(/^(#{1,6})\s+(.*)$/);
      if (headingMatch) {
        closeList();
        const level = headingMatch[1].length;
        const hText = headingMatch[2];
        output.push(`<h${level} class="md-h${level}">${hText}</h${level}>`);
        continue;
      }

      // 检查引用块
      if (line.startsWith("> ")) {
        closeList();
        const quoteText = line.slice(2);
        output.push(`<blockquote class="md-quote">${quoteText}</blockquote>`);
        continue;
      }

      // 检查无序列表
      const ulMatch = line.match(/^[\s]*[-*+•]\s+(.*)$/);
      if (ulMatch) {
        if (inList !== "ul") {
          closeList();
          output.push('<ul class="md-ul">');
          inList = "ul";
        }
        output.push(`<li>${ulMatch[1]}</li>`);
        continue;
      }

      // 检查有序列表
      const olMatch = line.match(/^[\s]*(\d+)\.\s+(.*)$/);
      if (olMatch) {
        if (inList !== "ol") {
          closeList();
          output.push('<ol class="md-ol">');
          inList = "ol";
        }
        output.push(`<li>${olMatch[2]}</li>`);
        continue;
      }

      // 普通空行
      if (!line.trim()) {
        closeList();
        continue;
      }

      // 普通段落
      closeList();
      output.push(`<p class="md-p">${line}</p>`);
    }

    closeList();
    flushTable();

    let resultHtml = output.join("\n");

    // 4. 行内语法处理
    // 粗体
    resultHtml = resultHtml.replace(/\*\*([^*]+)\*\*/g, "<strong>$1</strong>");
    // 斜体
    resultHtml = resultHtml.replace(/(?<!\*)\*([^*]+)\*(?!\*)/g, "<em>$1</em>");
    // 行内代码
    resultHtml = resultHtml.replace(/`([^`]+)`/g, '<code class="md-inline-code">$1</code>');
    // 链接
    resultHtml = resultHtml.replace(/\[(.*?)\]\((.*?)\)/g, '<a href="$2" target="_blank" rel="noopener" class="md-link">$1</a>');

    return resultHtml;
  }
});
