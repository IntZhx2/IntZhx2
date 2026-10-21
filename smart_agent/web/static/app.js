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
  const sessionsContainer = document.getElementById("sessions-container") || document.getElementById("itineraries-container");
  const btnRefreshSessions = document.getElementById("btn-refresh-sessions") || document.getElementById("btn-refresh-itineraries");
  const btnTopNewChat = document.getElementById("btn-top-new-chat");
  const btnSidebarNewChat = document.getElementById("btn-sidebar-new-chat");
  const btnSidebarNewChatTop = document.getElementById("btn-sidebar-new-chat-top");
  const btnDownloadActiveChat = document.getElementById("btn-download-active-chat");
  const agentStatusPill = document.getElementById("agent-status-pill");
  const statusLabel = document.getElementById("status-label");

  let currentSessionId = null;

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

  // 1. 初始化检查配置与会话历史
  checkConfig();
  loadSessions();

  // 会话操作按钮绑定
  if (btnTopNewChat) btnTopNewChat.addEventListener("click", () => startNewSession());
  if (btnSidebarNewChat) btnSidebarNewChat.addEventListener("click", () => startNewSession());
  if (btnSidebarNewChatTop) btnSidebarNewChatTop.addEventListener("click", () => startNewSession());
  if (btnRefreshSessions) btnRefreshSessions.addEventListener("click", () => loadSessions());
  if (btnDownloadActiveChat) btnDownloadActiveChat.addEventListener("click", () => downloadSession(currentSessionId));
  if (btnClearChat) btnClearChat.addEventListener("click", () => startNewSession());

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

  // 会话由 loadSessions() 与 triggerSend() 统一管理驱动

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
        body: JSON.stringify({ message: text, stream: true, session_id: currentSessionId }),
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

      loadSessions();
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
      if (data.session_id) {
        currentSessionId = data.session_id;
      }
      if (data.result && data.result.answer) {
        liveMsg.setAnswer(data.result.answer);
      }
      liveMsg.finish();
      loadSessions();
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
   * 加载历史会话列表 (支持多轮接续与导出下载)
   */
  async function loadSessions() {
    if (!sessionsContainer) return;
    try {
      const resp = await fetch("/api/sessions");
      const data = await resp.json();
      const sessions = data.sessions || [];
      console.log("[TravelAgent] 加载历史对话列表成功:", sessions);

      if (sessions.length === 0) {
        sessionsContainer.innerHTML = '<div class="empty-state">暂无历史对话，开启规划后将自动保存在此，随时可接续</div>';
        return;
      }

      sessionsContainer.innerHTML = sessions
        .map(
          (s) => `
        <div class="session-item ${s.session_id === currentSessionId ? 'active' : ''}" data-id="${escapeHtml(s.session_id)}" title="点击接续此对话: ${escapeHtml(s.title)}">
          <div class="session-item-top">
            <div class="session-item-title">💬 ${escapeHtml(s.title)}</div>
            <div class="session-item-actions">
              <button class="session-act-btn" title="导出下载此对话 (.md)" data-action="download" data-id="${escapeHtml(s.session_id)}">
                <i class="fa-solid fa-download"></i>
              </button>
              <button class="session-act-btn delete" title="删除此记录" data-action="delete" data-id="${escapeHtml(s.session_id)}">
                <i class="fa-solid fa-trash-can"></i>
              </button>
            </div>
          </div>
          <div class="session-item-meta">
            <span>${escapeHtml(s.updated_at ? s.updated_at.slice(5, 16) : '')}</span>
            <span class="session-badge">${s.turn_count || 1} 轮对话</span>
          </div>
        </div>
      `
        )
        .join("");

      // 绑定每个卡片的点击事件
      sessionsContainer.querySelectorAll(".session-item").forEach((card) => {
        card.addEventListener("click", (e) => {
          const btn = e.target.closest("button");
          if (btn) {
            const act = btn.dataset.action;
            const sid = btn.dataset.id;
            if (act === "download") {
              downloadSession(sid);
            } else if (act === "delete") {
              deleteSession(sid);
            }
            return;
          }
          const sid = card.dataset.id;
          if (sid) openSession(sid);
        });
      });
    } catch (e) {
      sessionsContainer.innerHTML = '<div class="empty-state">加载历史会话异常</div>';
    }
  }

  /**
   * 打开并接续历史会话
   */
  async function openSession(sessionId) {
    if (!sessionId) return;
    try {
      const resp = await fetch(`/api/session?id=${encodeURIComponent(sessionId)}`);
      const data = await resp.json();
      if (!resp.ok) throw new Error(data.error || "加载会话失败");

      currentSessionId = sessionId;

      // 清空聊天舞台并重新渲染此会话的所有轮次
      chatStream.innerHTML = "";

      const turns = data.turns || [];
      if (turns.length === 0) {
        startNewSession(false);
        return;
      }

      for (const turn of turns) {
        appendUserMessage(turn.user_prompt, turn.timestamp ? turn.timestamp.slice(11, 19) : null);
        appendArchivedAssistantTurn(turn);
      }

      // 高亮当前会话卡片
      sessionsContainer.querySelectorAll(".session-item").forEach((c) => {
        c.classList.toggle("active", c.dataset.id === sessionId);
      });

      scrollToBottom();
      chatTextarea.focus();
    } catch (e) {
      alert("打开历史会话失败: " + e.message);
    }
  }

  /**
   * 渲染已归档的历史助手消息（含工具卡片与排版）
   */
  function appendArchivedAssistantTurn(turn) {
    const row = document.createElement("div");
    row.className = "chat-message assistant";

    let toolsHtml = "";
    if (turn.step_traces && turn.step_traces.length > 0) {
      toolsHtml = '<div class="live-trace-box" style="margin-bottom:8px;">';
      turn.step_traces.forEach((st) => {
        const toolName = st.action || "mcp_tool";
        const isErr = st.is_error || false;
        const icon = isErr ? "fa-triangle-exclamation" : "fa-circle-check";
        const colorClass = isErr ? "error" : "success";
        const obsPreview = st.observation
          ? escapeHtml(st.observation.slice(0, 160)) + (st.observation.length > 160 ? "..." : "")
          : "";
        toolsHtml += `
          <div class="tool-call-card ${colorClass}" style="margin-bottom:6px; opacity:0.95;">
            <div class="tool-call-header">
              <i class="fa-solid ${icon}"></i>
              <span class="tool-call-name">已调用工具: ${escapeHtml(toolName)}</span>
              <span class="tool-status-badge ${colorClass}">${isErr ? "反馈异常" : "执行成功"}</span>
            </div>
            ${obsPreview ? `<div class="tool-call-result-preview">${obsPreview}</div>` : ""}
          </div>
        `;
      });
      toolsHtml += "</div>";
    }

    row.innerHTML = `
      <div class="msg-avatar"><i class="fa-solid fa-compass"></i></div>
      <div class="msg-bubble">
        ${toolsHtml}
        <div class="msg-text final-answer">${formatMarkdown(turn.assistant_response)}</div>
        <div class="msg-timestamp">${turn.timestamp ? turn.timestamp.slice(11, 19) : getCurrentTime()}</div>
      </div>
    `;
    chatStream.appendChild(row);
  }

  /**
   * 新建全新会话
   */
  async function startNewSession(requestBackend = true) {
    try {
      if (requestBackend) {
        const resp = await fetch("/api/session/new", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ title: "新旅游行程规划" }),
        });
        const data = await resp.json();
        currentSessionId = data.session_id;
      }
    } catch (e) {
      currentSessionId = null;
    }

    // 重置聊天舞台为欢迎指引
    chatStream.innerHTML = `
      <div class="welcome-guide">
        <div class="guide-badge">
          <i class="fa-solid fa-compass"></i> 专业一站式旅游规划智能体
        </div>
        <h2>您好，我是您的专属 TravelAgent 出行管家</h2>
        <p class="guide-subtitle">
          请在下方输入您的<b>目的地、出行人数、时间点约束</b>（如：<i>“周六下午3点必须到达广州塔”</i>），
          我将自动调度 MCP 天气、交通接驳与景点美食知识库，为您量身定制一条龙深度攻略。
        </p>
        <div class="quick-prompts">
          <div class="prompt-chip" data-text="帮我规划广州2日游，全程坐地铁，周六下午3点必须到广州塔登塔，预算适中，想吃老字号粤菜早茶">
            <span class="chip-icon">🗼</span>
            <div class="chip-content">
              <strong>广州2日地铁深度游</strong>
              <small>周六15:00广州塔登塔 · 地道西关早茶</small>
            </div>
          </div>
          <div class="prompt-chip" data-text="从广州大学城出发去深圳湾公园看海，下午3点前到达，晚上返回广州，优先公交地铁，推荐沿途美食">
            <span class="chip-icon">🌊</span>
            <div class="chip-content">
              <strong>广州大学城 ➔ 深圳湾公园</strong>
              <small>跨城通勤接驳 · 15:00前必达 · 沿途地道风味</small>
            </div>
          </div>
          <div class="prompt-chip" data-text="带父母游览北京3天2晚，行程平缓不走回头路，必去故宫颐和园，优先打车网约车，推荐烤鸭老字号">
            <span class="chip-icon">🏯</span>
            <div class="chip-content">
              <strong>北京3天孝亲悠闲游</strong>
              <small>故宫颐和园无障碍预约 · 老字号四季民福烤鸭</small>
            </div>
          </div>
        </div>
      </div>
    `;

    // 重新挂载灵感卡片点击事件
    chatStream.querySelectorAll(".prompt-chip").forEach((chip) => {
      chip.addEventListener("click", () => {
        chatTextarea.value = chip.dataset.text;
        chatTextarea.focus();
        triggerSend();
      });
    });

    loadSessions();
    chatTextarea.focus();
  }

  /**
   * 导出下载会话记录为 Markdown
   */
  function downloadSession(sessionId) {
    const targetId = sessionId || currentSessionId;
    if (!targetId) {
      alert("当前暂无可导出的对话记录，请先在下方发送旅游诉求开始规划！");
      return;
    }
    window.open(`/api/session/download?id=${encodeURIComponent(targetId)}`, "_blank");
  }

  /**
   * 删除指定会话记录
   */
  async function deleteSession(sessionId) {
    if (!sessionId) return;
    if (!confirm("确定要删除这条对话历史记录吗？删除后将无法恢复。")) return;

    try {
      const resp = await fetch("/api/session/delete", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ session_id: sessionId }),
      });
      const data = await resp.json();
      if (!resp.ok) throw new Error(data.error || "删除失败");

      if (currentSessionId === sessionId) {
        startNewSession();
      } else {
        loadSessions();
      }
    } catch (e) {
      alert("删除失败: " + e.message);
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
