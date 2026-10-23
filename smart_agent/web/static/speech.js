/**
 * SmartAgent 语音模块 (Speech STT & TTS Engine)
 * 基于现代浏览器标准 Web Speech API 实现语音指令录入与智能体自然语音朗读。
 */

class SpeechEngine {
  constructor() {
    this.recognition = null;
    this.isListening = false;
    this.isSpeaking = false;
    this.synth = window.speechSynthesis || null;
    if (this.synth) {
      try {
        this.synth.cancel();
      } catch (e) {}
    }

    this.onResultCallback = null;
    this.onStatusChangeCallback = null;

    this._initSTT();
  }

  /**
   * 初始化语音识别 (Speech-to-Text)
   */
  _initSTT() {
    const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
    if (!SpeechRecognition) {
      console.warn("当前浏览器环境不支持 Web Speech API 语音识别，请使用 Chrome/Edge 或桌面现代浏览器。");
      return;
    }

    try {
      this.recognition = new SpeechRecognition();
      this.recognition.lang = "zh-CN";
      this.recognition.continuous = false;
      this.recognition.interimResults = true;

      this.recognition.onstart = () => {
        this.isListening = true;
        if (this.onStatusChangeCallback) this.onStatusChangeCallback(true);
      };

      this.recognition.onresult = (event) => {
        let transcript = "";
        for (let i = event.resultIndex; i < event.results.length; i++) {
          transcript += event.results[i][0].transcript;
        }
        if (this.onResultCallback) {
          this.onResultCallback(transcript, event.results[0].isFinal);
        }
      };

      this.recognition.onerror = (event) => {
        console.warn("语音识别异常或结束:", event.error);
        this.stopListening();
      };

      this.recognition.onend = () => {
        this.isListening = false;
        if (this.onStatusChangeCallback) this.onStatusChangeCallback(false);
      };
    } catch (e) {
      console.error("初始化 SpeechRecognition 失败:", e);
    }
  }

  /**
   * 启动麦克风语音录入
   */
  startListening(onResult, onStatusChange) {
    if (!this.recognition) {
      alert("当前浏览器暂未开启或不支持 Web 语音录入功能，请在 Chrome/Edge 中体验或直接文字键入。");
      return;
    }
    this.onResultCallback = onResult;
    this.onStatusChangeCallback = onStatusChange;

    if (this.isListening) {
      this.stopListening();
      return;
    }

    try {
      this.recognition.start();
    } catch (e) {
      console.warn("语音识别已在进行中或权限受限:", e);
    }
  }

  /**
   * 停止语音录入
   */
  stopListening() {
    if (this.recognition && this.isListening) {
      try {
        this.recognition.stop();
      } catch (e) {}
    }
    this.isListening = false;
    if (this.onStatusChangeCallback) this.onStatusChangeCallback(false);
  }

  /**
   * 净化待朗读文本：去除 Markdown 格式符号、代码块与 Emoji，保证听感纯净流畅
   */
  cleanTextForSpeech(text) {
    if (!text) return "";
    let clean = text;
    // 移除代码块
    clean = clean.replace(/```[\s\S]*?```/g, " ");
    // 移除行内代码
    clean = clean.replace(/`[^`]+`/g, " ");
    // 移除链接 [text](url) -> text
    clean = clean.replace(/\[([^\]]+)\]\([^)]+\)/g, "$1");
    // 移除 Markdown 标题标记与水平线
    clean = clean.replace(/^#{1,6}\s+/gm, "");
    clean = clean.replace(/^[-*_]{3,}\s*$/gm, "");
    // 移除粗体/斜体
    clean = clean.replace(/\*\*([^*]+)\*\*/g, "$1").replace(/\*([^*]+)\*/g, "$1");
    // 移除引用符号
    clean = clean.replace(/^>\s+/gm, "");
    // 移除表格管道符，换为停顿逗号
    clean = clean.replace(/\|/g, "，");
    // 移除无序列表符
    clean = clean.replace(/^[-*+•]\s+/gm, "");
    // 移除大部分 Emoji 图标
    clean = clean.replace(/[\uD800-\uDBFF][\uDC00-\uDFFF]/g, "");
    // 合并多余空白换行
    clean = clean.replace(/\s+/g, " ").trim();
    return clean;
  }

  /**
   * 自然语音朗读文本 (Text-to-Speech)
   */
  speak(text, onStart, onEnd) {
    if (!this.synth) {
      alert("当前浏览器环境不支持语音合成 (Web SpeechSynthesis API)。");
      return;
    }
    this.stopSpeaking();

    const clean = this.cleanTextForSpeech(text);
    if (!clean) return;

    try {
      const utterance = new SpeechSynthesisUtterance(clean);
      utterance.lang = "zh-CN";
      utterance.rate = 1.05;
      utterance.pitch = 1.0;

      utterance.onstart = () => {
        this.isSpeaking = true;
        if (onStart) onStart();
      };

      utterance.onend = () => {
        this.isSpeaking = false;
        if (onEnd) onEnd();
      };

      utterance.onerror = (e) => {
        console.warn("TTS 朗读异常:", e);
        this.isSpeaking = false;
        if (onEnd) onEnd();
      };

      this.synth.speak(utterance);
    } catch (err) {
      console.error("启动语音朗读失败:", err);
      this.isSpeaking = false;
      if (onEnd) onEnd();
    }
  }

  /**
   * 停止当前语音朗读
   */
  stopSpeaking() {
    if (this.synth) {
      try {
        this.synth.cancel();
      } catch (e) {}
    }
    this.isSpeaking = false;
  }
}

window.speechEngine = new SpeechEngine();
