// CONTRACTS v2。服务端未定义的健康报告字段不作为已有契约使用。
export interface User {
  id: number;
  username: string;
  is_demo: boolean;
}
export interface LampState {
  online: boolean;
  on: boolean;
  brightness: number;
  color_temp: number;
}
export interface AcState {
  online: boolean;
  on: boolean;
  mode: "cool" | "heat" | "fan" | "dry";
  temperature: number;
  inferred: boolean;
}
export interface Devices {
  lamp?: LampState;
  ac?: AcState;
  plug?: { online: boolean; on: boolean; power_w: number | null };
  motion?: {
    online: boolean;
    last_motion_at: string;
    illuminance: "strong" | "weak" | null;
  };
  climate?: {
    online: boolean;
    temperature: number;
    humidity: number;
    updated_at: string;
  };
  speaker?: {
    online: boolean;
    voice_bridge_ok: boolean;
    ir_supported: boolean;
  };
}
export interface FocusState {
  state: "idle" | "focusing" | "short_break" | "paused";
  session_id: number | null;
  workspace_name: string;
  goal: string;
  phase_started_at: string | null;
  phase_ends_at: string | null;
  remaining_seconds: number;
  pomodoro_index: number;
  flow_extensions: number;
  focus_seconds_today: number;
}
export interface InputMinute {
  minute: string;
  keys: number;
  clicks: number;
  scrolls: number;
  active_seconds: number;
  app_switches: number;
  front_process: string;
  front_title_category: string;
  activity_rate: number;
}
export interface Snapshot {
  edge_online: boolean;
  demo_mode: boolean;
  devices: Devices;
  presence: {
    present: boolean;
    since: string;
    sources: {
      motion: boolean;
      keyboard_mouse: boolean;
      screen_locked: boolean;
    };
  };
  focus: FocusState;
  fatigue: {
    level: number;
    score: number;
    in_flow: boolean;
    reasons: string[];
    updated_at: string;
  };
  current_input_stats: InputMinute | null;
}
export interface WorkspaceItem {
  type: "vscode" | "folder" | "url" | "app";
  path?: string;
  url?: string;
  name?: string;
}
export interface Workspace {
  id: number;
  name: string;
  aliases: string[];
  focus_minutes: number;
  lamp: { brightness: number; color_temp: number };
  ac: { auto_on: boolean; temperature: number };
  items: WorkspaceItem[];
  layout: "code_left_browser_right" | "maximize" | "split_half" | "custom";
  custom_layout: Record<string, unknown> | null;
}
export type WorkspaceIn = Omit<Workspace, "id">;
export interface Envelope {
  v: 2;
  type: "event" | "cmd" | "result" | "ping" | "pong";
  id: string;
  ts: string;
  name: string;
  payload: Record<string, unknown>;
}
export interface Notice {
  level: "info" | "warn" | "alert";
  title: string;
  text: string;
  action: "none" | "rest_overlay";
}
export interface AssistResult {
  kind: "code_clip" | "screen_explain" | "search_summary";
  title: string;
  markdown: string;
}
export interface ToolEvent {
  agent: string;
  tool: string;
  args: Record<string, unknown>;
  status: "running" | "ok" | "error";
}
export interface VoiceLog {
  id?: number;
  at: string;
  text: string;
  route: string;
  trace: ToolEvent[];
  reply: string;
  latency_ms: number;
  ok: boolean;
}
export interface FocusSession {
  id: number;
  started_at: string;
  ended_at: string | null;
  focus_seconds: number;
  pomodoros_done: number;
  flow_extensions: number;
  goal: string;
  pause_count: number;
}
export interface Timeline {
  date: string;
  inputs: { minute: string; activity_rate: number; top_category: string }[];
  env: { at: string; temperature: number; humidity: number }[];
  fatigue_events: {
    at: string;
    level: number;
    score: number;
    reasons?: string[];
  }[];
  focus_spans: { started_at: string; ended_at: string; workspace: string }[];
}
export interface DailyReport {
  day?: string;
  date?: string;
  stats: Record<string, unknown>;
  ai_comment: string;
}
export interface Settings {
  focus_lamp: { brightness: number; color_temp: number };
  relax_lamp: { brightness: number; color_temp: number };
  sleep_lamp: { brightness: number; color_temp: number };
  auto_lamp_after: string;
  motion_window_min: number;
  absent_lamp_sleep_min: number;
  app_whitelist: string[];
  study_categories: string[];
  entertainment_categories: string[];
  voice_takeover_prefixes: string[];
  ac: {
    auto_rule: "auto" | "ask" | "off";
    summer_temp: number;
    trigger_on_temp: number;
    high_humidity_trigger: number;
  };
  wellbeing: {
    l1_score: number;
    l2_score: number;
    l3_score: number;
    max_continuous_focus_min: number;
    cooldown_min: number;
    flow_extension_min: number;
    max_flow_extensions: number;
  };
  absent_confirm_min: number;
  absent_lamp_off_min: number;
  absent_ac_off_min: number;
}
