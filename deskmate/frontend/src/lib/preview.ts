import type {
  Settings,
  Snapshot,
  Timeline,
  Workspace,
} from "../types/contracts";
export function previewData(): {
  state: Snapshot;
  workspaces: Workspace[];
  settings: Settings;
  timeline: Timeline;
} {
  const now = new Date(),
    before = (minutes: number) =>
      new Date(now.getTime() - minutes * 60000).toISOString();
  const workspace: Workspace = {
    id: 1,
    name: "软件工程项目",
    aliases: ["软工"],
    focus_minutes: 45,
    lamp: { brightness: 80, color_temp: 4000 },
    ac: { auto_on: true, temperature: 26 },
    items: [
      { type: "vscode", path: "D:\\Projects\\DeskMate" },
      { type: "url", url: "https://edu.cnblogs.com/" },
    ],
    layout: "code_left_browser_right",
    custom_layout: null,
  };
  return {
    state: {
      edge_online: false,
      demo_mode: true,
      devices: {
        lamp: { online: true, on: true, brightness: 80, color_temp: 4000 },
        plug: { online: true, on: true, power_w: 12.5 },
        ac: {
          online: true,
          on: true,
          mode: "cool",
          temperature: 26,
          inferred: true,
        },
        climate: {
          online: true,
          temperature: 26.5,
          humidity: 55,
          updated_at: now.toISOString(),
        },
        motion: {
          online: true,
          last_motion_at: now.toISOString(),
          illuminance: "weak",
        },
        speaker: { online: true, voice_bridge_ok: true, ir_supported: true },
      },
      presence: {
        present: true,
        since: before(38),
        sources: { motion: true, keyboard_mouse: true, screen_locked: false },
      },
      focus: {
        state: "focusing",
        session_id: 1,
        workspace_name: workspace.name,
        goal: "完成需求分析与前端原型",
        phase_started_at: before(12),
        phase_ends_at: new Date(
          now.getTime() + 32 * 60000 + 18000,
        ).toISOString(),
        remaining_seconds: 1938,
        pomodoro_index: 2,
        flow_extensions: 0,
        focus_seconds_today: 5640,
      },
      fatigue: {
        level: 0,
        score: 24,
        in_flow: false,
        reasons: [],
        updated_at: now.toISOString(),
      },
      current_input_stats: null,
    },
    workspaces: [
      workspace,
      {
        ...structuredClone(workspace),
        id: 2,
        name: "阅读与思考",
        aliases: ["阅读"],
        focus_minutes: 25,
        lamp: { brightness: 65, color_temp: 3500 },
        items: [{ type: "app", name: "Obsidian.exe" }],
        layout: "maximize",
      },
    ],
    settings: {
      focus_lamp: { brightness: 80, color_temp: 4000 },
      relax_lamp: { brightness: 40, color_temp: 2700 },
      sleep_lamp: { brightness: 10, color_temp: 2500 },
      auto_lamp_after: "18:00",
      motion_window_min: 5,
      absent_lamp_sleep_min: 3,
      app_whitelist: ["Code.exe", "Chrome.exe", "Obsidian.exe"],
      study_categories: ["Code.exe", "Obsidian.exe"],
      entertainment_categories: ["Steam.exe"],
      voice_takeover_prefixes: ["帮我", "桌伴"],
      ac: {
        auto_rule: "auto",
        summer_temp: 26,
        trigger_on_temp: 27.5,
        high_humidity_trigger: 75,
      },
      wellbeing: {
        l1_score: 40,
        l2_score: 55,
        l3_score: 75,
        max_continuous_focus_min: 60,
        cooldown_min: 15,
        flow_extension_min: 10,
        max_flow_extensions: 2,
      },
      absent_confirm_min: 3,
      absent_lamp_off_min: 15,
      absent_ac_off_min: 30,
    },
    timeline: {
      date: new Intl.DateTimeFormat("en-CA", {
        timeZone: "Asia/Shanghai",
      }).format(now),
      inputs: Array.from({ length: 36 }, (_, i) => ({
        minute: before(35 - i),
        activity_rate:
          [76, 93, 88, 121, 130, 102, 87, 148, 164, 139, 155, 124][i % 12]! +
          Math.round(Math.sin(i) * 12),
        top_category: "study",
      })),
      env: Array.from({ length: 12 }, (_, i) => ({
        at: before(33 - i * 3),
        temperature: 26.1 + (i % 4) * 0.2,
        humidity: 53 + (i % 5),
      })),
      fatigue_events: [{ at: before(25), level: 1, score: 42 }],
      focus_spans: [
        {
          started_at: before(106),
          ended_at: before(61),
          workspace: workspace.name,
        },
      ],
    },
  };
}
