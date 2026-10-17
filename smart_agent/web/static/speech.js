/**
 * SmartAgent 语音模块 (Speech STT & TTS Engine)
 * 基于现代浏览器标准 Web Speech API 实现语音指令录入与智能体自然语音朗读。
 */

class SpeechEngine {
  constructor() {
    this.recognition = null;
    this.isListening = false;
    this.autoTTS = true;
    this.synth = window.speechSynthesis || null;

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
   * 文本转语音朗读 (Text-to-Speech)
   */
  speak(text) {
    if (!this.synth || !this.autoTTS) return;

    // 清除 Markdown 标记与代码块，保留纯净朗读文本
    const cleanText = text
      .replace(/```[\s\S]*?```/g, "已为您执行相关代码与数据块")
      .replace(/`([^`]+)`/g, "$1")
      .replace(/[-*#]/g, "")
      .replace(/\[(.*?)\]\(.*?\)/g, "$1")
      .trim();

    if (!cleanText) return;

    try {
      this.synth.cancel(); // 停止当前正在播放的声音
      const utter = new SpeechSynthesisUtterance(cleanText);
      utter.lang = "zh-CN";
      utter.rate = 1.05;
      utter.pitch = 1.0;

      // 尝试匹配中文发音音色
      const voices = this.synth.getVoices();
      const zhVoice = voices.find(v => v.lang.includes("zh") || v.lang.includes("cmn"));
      if (zhVoice) utter.voice = zhVoice;

      this.synth.speak(utter);
    } catch (e) {
      console.warn("TTS 朗读异常:", e);
    }
  }

  toggleTTS() {
    this.autoTTS = !this.autoTTS;
    if (!this.autoTTS && this.synth) {
      this.synth.cancel();
    }
    return this.autoTTS;
  }
}

window.speechEngine = new SpeechEngine();
