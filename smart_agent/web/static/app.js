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

    const loadingId = "loading-" + Date.now();
    appendLoadingMessage(loadingId);
    scrollToBottom();

    try {
      const resp = await fetch("/api/chat", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ message: text }),
      });

      const data = await resp.json();
      removeElement(loadingId);

      if (!resp.ok || data.error) {
        appendAssistantMessage("⚠️ 生成失败: " + (data.error || "大模型请求异常"));
        return;
      }

      appendAgentResponse(data.answer, data.traces);
      scrollToBottom();

      // 刷新归档列表 (如果生成了攻略文件)
      loadItineraries();
    } catch (e) {
      removeElement(loadingId);
      appendAssistantMessage("网络或通信异常: " + e.message);
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

  function appendLoadingMessage(id) {
    const row = document.createElement("div");
    row.className = "chat-message assistant";
    row.id = id;
    row.innerHTML = `
      <div class="msg-avatar"><i class="fa-solid fa-compass"></i></div>
      <div class="msg-bubble">
        <div class="msg-text">
          <p><i class="fa-solid fa-spinner fa-spin"></i> <strong>TravelAgent 正在调用 MCP 气象与交通工具，统筹规划一条龙攻略...</strong></p>
          <span style="font-size: 0.76rem; color: var(--text-muted)">正在向云端大模型发送请求并逆推时间线与接驳换乘...</span>
        </div>
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

  function appendAgentResponse(answer, traces) {
    const row = document.createElement("div");
    row.className = "chat-message assistant";

    let tracesHtml = "";
    if (traces && traces.length > 0) {
      const cards = [];
      traces.forEach((tr) => {
        if (tr.type === "thought" && tr.content) {
          cards.push(`
            <div class="trace-card">
              <div class="trace-header thought">
                <i class="fa-solid fa-brain"></i> <span>智能体思考与时间约束求解</span>
              </div>
              <div class="trace-content">${escapeHtml(tr.content)}</div>
            </div>
          `);
        } else if (tr.type === "tool_call") {
          const tool = tr.details ? tr.details.tool : "";
          const args = tr.details ? JSON.stringify(tr.details.arguments, null, 2) : "";
          cards.push(`
            <div class="trace-card">
              <div class="trace-header tool">
                <i class="fa-solid fa-microchip"></i> <span>调度 MCP 工具: <strong>${escapeHtml(tool)}</strong></span>
              </div>
              <div class="trace-content">${escapeHtml(args)}</div>
            </div>
          `);
        } else if (tr.type === "tool_result") {
          const res = tr.content || "";
          cards.push(`
            <div class="trace-card">
              <div class="trace-header obs">
                <i class="fa-solid fa-circle-check"></i> <span>工具执行反馈 (Observation)</span>
              </div>
              <div class="trace-content">${escapeHtml(res)}</div>
            </div>
          `);
        }
      });
      if (cards.length > 0) {
        tracesHtml = `<div class="trace-container">${cards.join("")}</div>`;
      }
    }

    row.innerHTML = `
      <div class="msg-avatar"><i class="fa-solid fa-compass"></i></div>
      <div class="msg-bubble">
        ${tracesHtml}
        <div class="msg-text">${formatMarkdown(answer)}</div>
        <div class="msg-timestamp">${getCurrentTime()}</div>
      </div>
    `;
    chatStream.appendChild(row);
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

  function formatMarkdown(text) {
    if (!text) return "";
    let html = escapeHtml(text);
    // 粗体
    html = html.replace(/\*\*(.*?)\*\*/g, "<strong>$1</strong>");
    // 标题
    html = html.replace(/^### (.*$)/gim, '<h3 style="margin: 10px 0 6px; font-size: 1rem; color: var(--morandi-blue); font-weight: 600;">$1</h3>');
    html = html.replace(/^## (.*$)/gim, '<h2 style="margin: 12px 0 8px; font-size: 1.1rem; color: var(--morandi-blue); font-weight: 700; border-bottom: 1px dashed var(--border-subtle); padding-bottom: 4px;">$1</h2>');
    html = html.replace(/^# (.*$)/gim, '<h1 style="margin: 14px 0 8px; font-size: 1.2rem; color: var(--text-main); font-weight: 700;">$1</h1>');
    // 单行代码与徽标
    html = html.replace(/`([^`]+)`/g, '<code style="background-color: var(--bg-subtle); color: var(--morandi-blue); padding: 2px 6px; border-radius: 4px; font-size: 0.85em; font-family: monospace;">$1</code>');
    // 换行
    html = html.replace(/\n/g, "<br/>");
    return html;
  }
});
