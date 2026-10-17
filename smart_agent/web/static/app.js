/**
 * SmartAgent 前端主交互逻辑 (Main App Engine)
 * 统筹 Agent 接口通信、ReAct 规划轨迹渲染、SQLite 待办状态双向同步与事件总线。
 */

document.addEventListener("DOMContentLoaded", () => {
  // DOM 元素引用
  const messagesContainer = document.getElementById("messages-container");
  const userInput = document.getElementById("user-input");
  const btnSend = document.getElementById("btn-send");
  const btnMic = document.getElementById("btn-mic");
  const btnClearChat = document.getElementById("btn-clear-chat");
  const btnToggleTTS = document.getElementById("btn-toggle-tts");
  const voiceIndicator = document.getElementById("voice-indicator");
  const todosContainer = document.getElementById("todos-container");
  const toolsContainer = document.getElementById("tools-container");
  const btnRefreshTodos = document.getElementById("btn-refresh-todos");
  const quickTodoInput = document.getElementById("quick-todo-input");
  const quickTodoBtn = document.getElementById("quick-todo-btn");

  // 设置模态弹窗元素
  const btnOpenSettings = document.getElementById("btn-open-settings");
  const btnCloseSettings = document.getElementById("btn-close-settings");
  const settingsModal = document.getElementById("settings-modal");
  const cfgApiBase = document.getElementById("cfg-api-base");
  const cfgApiKey = document.getElementById("cfg-api-key");
  const cfgModel = document.getElementById("cfg-model");
  const btnSaveSettings = document.getElementById("btn-save-settings");
  const btnSwitchOffline = document.getElementById("btn-switch-offline");
  const statusModeText = document.getElementById("status-mode-text");
  const currentModeBadge = document.getElementById("current-mode-badge");

  let currentFilter = "all";

  // 服务商预设配置字典
  const PROVIDER_PRESETS = {
    bailian: {
      base: "https://dashscope.aliyuncs.com/compatible-mode/v1",
      model: "qwen-plus",
      hint: "阿里云百炼 (通义千问) 兼容接口",
    },
    deepseek: {
      base: "https://api.deepseek.com/v1",
      model: "deepseek-chat",
      hint: "DeepSeek 官方 API",
    },
    silicon: {
      base: "https://api.siliconflow.cn/v1",
      model: "Qwen/Qwen2.5-7B-Instruct",
      hint: "硅基流动免费/普惠模型接口",
    },
    zhipu: {
      base: "https://open.bigmodel.cn/api/paas/v4",
      model: "glm-4-flash",
      hint: "智谱清言免费开放模型",
    },
    openai: {
      base: "https://api.openai.com/v1",
      model: "gpt-4o-mini",
      hint: "OpenAI 官方 API",
    },
    ollama: {
      base: "http://localhost:11434/v1",
      model: "qwen2.5:7b",
      hint: "本地私有化 Ollama 部署",
    },
  };

  // 1. 初始化加载
  loadTools();
  loadTodos();
  loadConfig();

  // 设置模态弹窗绑定
  if (btnOpenSettings) {
    btnOpenSettings.addEventListener("click", () => {
      loadConfig();
      settingsModal.classList.add("active");
    });
  }

  if (btnCloseSettings) {
    btnCloseSettings.addEventListener("click", () => {
      settingsModal.classList.remove("active");
    });
  }

  settingsModal.addEventListener("click", (e) => {
    if (e.target === settingsModal) {
      settingsModal.classList.remove("active");
    }
  });

  // 服务商预设按钮切换
  document.querySelectorAll(".provider-chip").forEach((chip) => {
    chip.addEventListener("click", () => {
      document.querySelectorAll(".provider-chip").forEach((c) => c.classList.remove("active"));
      chip.classList.add("active");
      const provider = chip.dataset.provider;
      const preset = PROVIDER_PRESETS[provider];
      if (preset) {
        cfgApiBase.value = preset.base;
        cfgModel.value = preset.model;
      }
    });
  });

  // 保存模型配置
  if (btnSaveSettings) {
    btnSaveSettings.addEventListener("click", async () => {
      const apiKey = cfgApiKey.value.trim();
      const apiBase = cfgApiBase.value.trim();
      const model = cfgModel.value.trim();

      if (!apiKey) {
        alert("请输入有效的 API Key！若需在离线模式下运行，可点击“切换为本地离线模式”。");
        return;
      }

      btnSaveSettings.disabled = true;
      btnSaveSettings.innerHTML = '<i class="fa-solid fa-spinner fa-spin"></i> 正在应用配置...';

      try {
        const resp = await fetch("/api/config", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ api_key: apiKey, api_base: apiBase, model: model }),
        });
        const data = await resp.json();
        alert("配置成功！" + data.message);
        settingsModal.classList.remove("active");
        loadConfig();
      } catch (e) {
        alert("保存配置失败: " + e.message);
      } finally {
        btnSaveSettings.disabled = false;
        btnSaveSettings.innerHTML = '<i class="fa-solid fa-check"></i> 保存并启用在线大模型';
      }
    });
  }

  // 切换为本地离线模式
  if (btnSwitchOffline) {
    btnSwitchOffline.addEventListener("click", async () => {
      try {
        const resp = await fetch("/api/config", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ api_key: "", api_base: cfgApiBase.value, model: cfgModel.value }),
        });
        const data = await resp.json();
        cfgApiKey.value = "";
        alert("已切换为本地离线规则引擎！");
        settingsModal.classList.remove("active");
        loadConfig();
      } catch (e) {
        alert("切换失败: " + e.message);
      }
    });
  }

  async function loadConfig() {
    try {
      const resp = await fetch("/api/config");
      const data = await resp.json();
      if (cfgApiBase) cfgApiBase.value = data.api_base || "https://dashscope.aliyuncs.com/compatible-mode/v1";
      if (cfgModel) cfgModel.value = data.model || "qwen-plus";

      if (data.has_key) {
        if (statusModeText) statusModeText.innerHTML = `在线大模型 (${data.model})`;
        if (currentModeBadge) currentModeBadge.innerHTML = `<span style="color: var(--accent-green)">🟢 在线大模型模式 (${data.model}, Key: ${data.masked_key})</span>`;
      } else {
        if (statusModeText) statusModeText.innerHTML = `本地离线引擎`;
        if (currentModeBadge) currentModeBadge.innerHTML = `<span style="color: var(--accent-amber)">🟡 本地离线规则引擎（免 Key 极速模式）</span>`;
      }
    } catch (e) {
      console.warn("加载模型配置失败", e);
    }
  }

  // 2. 侧边栏选项卡切换
  document.querySelectorAll(".tab-btn").forEach((btn) => {
    btn.addEventListener("click", () => {
      document.querySelectorAll(".tab-btn").forEach((b) => b.classList.remove("active"));
      document.querySelectorAll(".tab-content").forEach((c) => c.classList.remove("active"));
      btn.classList.add("active");
      const tabId = "tab-" + btn.dataset.tab;
      const target = document.getElementById(tabId);
      if (target) target.classList.add("active");
    });
  });

  // 3. 待办过滤切换
  document.querySelectorAll(".filter-pill").forEach((pill) => {
    pill.addEventListener("click", () => {
      document.querySelectorAll(".filter-pill").forEach((p) => p.classList.remove("active"));
      pill.classList.add("active");
      currentFilter = pill.dataset.filter;
      loadTodos();
    });
  });

  // 4. 快捷 Prompt 按钮绑定
  document.querySelectorAll(".chip-btn").forEach((chip) => {
    chip.addEventListener("click", () => {
      const promptText = chip.dataset.prompt;
      userInput.value = promptText;
      userInput.focus();
      sendMessage();
    });
  });

  // 5. 输入框自适应与回车发送
  userInput.addEventListener("keydown", (e) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      sendMessage();
    }
  });

  btnSend.addEventListener("click", sendMessage);

  // 6. 语音录入 (STT) 交互绑定
  btnMic.addEventListener("click", () => {
    window.speechEngine.startListening(
      (text, isFinal) => {
        userInput.value = text;
        if (isFinal) {
          setTimeout(() => {
            sendMessage();
          }, 300);
        }
      },
      (listening) => {
        if (listening) {
          btnMic.classList.add("recording");
          voiceIndicator.classList.add("active");
        } else {
          btnMic.classList.remove("recording");
          voiceIndicator.classList.remove("active");
        }
      }
    );
  });

  // 7. 语音朗读 (TTS) 切换
  btnToggleTTS.addEventListener("click", () => {
    const enabled = window.speechEngine.toggleTTS();
    btnToggleTTS.classList.toggle("active", enabled);
    btnToggleTTS.innerHTML = enabled
      ? '<i class="fa-solid fa-volume-high"></i>'
      : '<i class="fa-solid fa-volume-xmark"></i>';
  });

  // 8. 清空会话历史
  btnClearChat.addEventListener("click", async () => {
    if (!confirm("确定要清空当前的智能体对话与上下文记忆吗？")) return;
    try {
      await fetch("/api/clear", { method: "POST" });
      messagesContainer.innerHTML = `
        <div class="message-row assistant">
          <div class="avatar"><i class="fa-solid fa-robot"></i></div>
          <div class="message-content">
            <div class="bubble"><p>🧹 上下文记忆已清空，开启全新的任务规划！</p></div>
          </div>
        </div>
      `;
    } catch (e) {
      alert("清空记忆失败: " + e);
    }
  });

  // 9. 刷新待办与快捷添加
  btnRefreshTodos.addEventListener("click", loadTodos);
  quickTodoBtn.addEventListener("click", addQuickTodo);
  quickTodoInput.addEventListener("keydown", (e) => {
    if (e.key === "Enter") addQuickTodo();
  });

  /**
   * 发送聊天消息并驱动智能体 ReAct 循环
   */
  async function sendMessage() {
    const text = userInput.value.trim();
    if (!text) return;

    // 渲染用户输入泡泡
    appendUserMessage(text);
    userInput.value = "";
    userInput.style.height = "auto";

    // 渲染临时等待泡泡
    const loadingId = "loading-" + Date.now();
    appendLoadingMessage(loadingId);
    scrollToBottom();

    try {
      const resp = await fetch("/api/chat", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: jsonToString({ message: text }),
      });

      const data = await resp.json();
      removeElement(loadingId);

      if (data.error) {
        appendAssistantMessage("⚠️ 执行出错: " + data.error);
        return;
      }

      // 渲染完整的 Agent 规划与执行轨迹
      appendAgentResponse(data.answer, data.traces);
      scrollToBottom();

      // 同步刷新 SQLite 待办面板（因为对话可能修改了待办状态）
      loadTodos();

      // 智能体语音播报 (TTS)
      window.speechEngine.speak(data.answer);
    } catch (e) {
      removeElement(loadingId);
      appendAssistantMessage("网络或服务异常: " + e.message);
    }
  }

  function appendUserMessage(text) {
    const row = document.createElement("div");
    row.className = "message-row user";
    row.innerHTML = `
      <div class="avatar"><i class="fa-solid fa-user"></i></div>
      <div class="message-content">
        <div class="bubble"><p>${escapeHtml(text)}</p></div>
        <span class="message-time">${getCurrentTime()}</span>
      </div>
    `;
    messagesContainer.appendChild(row);
  }

  function appendLoadingMessage(id) {
    const row = document.createElement("div");
    row.className = "message-row assistant";
    row.id = id;
    row.innerHTML = `
      <div class="avatar"><i class="fa-solid fa-robot"></i></div>
      <div class="message-content">
        <div class="bubble">
          <p><i class="fa-solid fa-spinner fa-spin"></i> SmartAgent 正在思考并执行任务...</p>
        </div>
      </div>
    `;
    messagesContainer.appendChild(row);
  }

  function appendAssistantMessage(text) {
    const row = document.createElement("div");
    row.className = "message-row assistant";
    row.innerHTML = `
      <div class="avatar"><i class="fa-solid fa-robot"></i></div>
      <div class="message-content">
        <div class="bubble">${formatMarkdown(text)}</div>
        <span class="message-time">${getCurrentTime()}</span>
      </div>
    `;
    messagesContainer.appendChild(row);
  }

  function appendAgentResponse(answer, traces) {
    const row = document.createElement("div");
    row.className = "message-row assistant";

    let tracesHtml = "";
    if (traces && traces.length > 0) {
      const traceItems = [];
      traces.forEach((tr) => {
        if (tr.type === "thought" && tr.content) {
          traceItems.push(`
            <div class="trace-item thought">
              <i class="fa-solid fa-brain"></i> <strong>思考规划</strong>: ${escapeHtml(tr.content)}
            </div>
          `);
        } else if (tr.type === "tool_call") {
          const tool = tr.details ? tr.details.tool : "";
          const args = tr.details ? JSON.stringify(tr.details.arguments, null, 2) : "";
          traceItems.push(`
            <div class="trace-item tool_call">
              <div class="trace-header call">
                <i class="fa-solid fa-gears"></i> <span>MCP 工具调用: <strong>${escapeHtml(tool)}</strong></span>
              </div>
              <div class="trace-body">${escapeHtml(args)}</div>
            </div>
          `);
        } else if (tr.type === "tool_result") {
          const resText = tr.content || "";
          traceItems.push(`
            <div class="trace-item tool_call">
              <div class="trace-header result">
                <i class="fa-solid fa-circle-check"></i> <span>工具执行反馈 (Observation)</span>
              </div>
              <div class="trace-body">${escapeHtml(resText)}</div>
            </div>
          `);
        }
      });

      if (traceItems.length > 0) {
        tracesHtml = `<div class="trace-block">${traceItems.join("")}</div>`;
      }
    }

    row.innerHTML = `
      <div class="avatar"><i class="fa-solid fa-robot"></i></div>
      <div class="message-content">
        ${tracesHtml}
        <div class="bubble">${formatMarkdown(answer)}</div>
        <span class="message-time">${getCurrentTime()}</span>
      </div>
    `;
    messagesContainer.appendChild(row);
  }

  /**
   * 加载 MCP 工具列表
   */
  async function loadTools() {
    try {
      const resp = await fetch("/api/tools");
      const data = await resp.json();
      const tools = data.tools || [];
      if (tools.length === 0) {
        toolsContainer.innerHTML = '<div class="loading-placeholder">暂无可用的 MCP 工具</div>';
        return;
      }

      toolsContainer.innerHTML = tools
        .map(
          (t) => `
        <div class="tool-card">
          <div class="tool-card-header">
            <span class="tool-name">${escapeHtml(t.name)}</span>
            <i class="fa-solid fa-microchip" style="color: var(--accent-blue)"></i>
          </div>
          <p class="tool-desc">${escapeHtml(t.description)}</p>
        </div>
      `
        )
        .join("");
    } catch (e) {
      toolsContainer.innerHTML = '<div class="loading-placeholder">加载工具失败</div>';
    }
  }

  /**
   * 加载 SQLite 待办数据
   */
  async function loadTodos() {
    try {
      const resp = await fetch("/api/todos");
      const data = await resp.json();
      let todos = data.todos || [];

      if (currentFilter !== "all") {
        todos = todos.filter((t) => t.status === currentFilter);
      }

      if (todos.length === 0) {
        todosContainer.innerHTML = '<div class="loading-placeholder">暂无匹配的待办记录</div>';
        return;
      }

      todosContainer.innerHTML = todos
        .map((t) => {
          const isDone = t.status === "completed";
          const priClass = `tag-priority-${t.priority || "medium"}`;
          return `
          <div class="todo-item ${isDone ? "completed" : ""}" data-id="${t.id}">
            <div class="todo-left">
              <input type="checkbox" class="todo-check" ${isDone ? "checked" : ""} onchange="toggleTodoStatus(${t.id}, this.checked)" />
              <div class="todo-details">
                <span class="todo-title">${escapeHtml(t.title)}</span>
                <span class="todo-meta">
                  <span class="${priClass}">[${t.priority}]</span>
                  <span>#${escapeHtml(t.category || "general")}</span>
                  ${t.due_date ? `<span>🕒 ${escapeHtml(t.due_date)}</span>` : ""}
                </span>
              </div>
            </div>
            <button class="todo-delete-btn" onclick="deleteTodo(${t.id})" title="删除">
              <i class="fa-solid fa-xmark"></i>
            </button>
          </div>
        `;
        })
        .join("");
    } catch (e) {
      todosContainer.innerHTML = '<div class="loading-placeholder">加载待办失败</div>';
    }
  }

  /**
   * 快捷添加待办
   */
  async function addQuickTodo() {
    const title = quickTodoInput.value.trim();
    if (!title) return;

    try {
      await fetch("/api/todos", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: jsonToString({ title: title, priority: "medium", category: "work" }),
      });
      quickTodoInput.value = "";
      loadTodos();
    } catch (e) {
      alert("添加失败: " + e);
    }
  }

  window.toggleTodoStatus = async (id, isDone) => {
    const status = isDone ? "completed" : "pending";
    try {
      await fetch(`/api/todos/${id}`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: jsonToString({ status: status }),
      });
      loadTodos();
    } catch (e) {
      alert("更新失败: " + e);
    }
  };

  window.deleteTodo = async (id) => {
    try {
      await fetch(`/api/todos/${id}`, { method: "DELETE" });
      loadTodos();
    } catch (e) {
      alert("删除失败: " + e);
    }
  };

  // 工具辅助函数
  function jsonToString(obj) {
    return JSON.stringify(obj);
  }

  function scrollToBottom() {
    messagesContainer.scrollTop = messagesContainer.scrollHeight;
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
    // 单行代码
    html = html.replace(/`([^`]+)`/g, "<code>$1</code>");
    // 换行
    html = html.replace(/\n/g, "<br/>");
    return html;
  }
});
