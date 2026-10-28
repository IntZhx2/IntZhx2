# 硬件实体与接口映射表 (docs/hardware/entities.md)

> 本文档是 DeskMate 硬件与边缘端（任务 A-01）的核心交付产物。
> 记录各设备在 Home Assistant 中的 `entity_id`、核心属性与接口调用示例。

---

## 1. 实体映射清单

| 逻辑设备名 (`device`) | 真实硬件型号 | Home Assistant `entity_id` | 状态 / 控制属性 | 接入方式 |
|---|---|---|---|---|
| `lamp` | 米家台灯 1S (lamp4) | `light.yeelink_cn_313523278_lamp4_s_2_light` | 开关 (`on`/`off`)、亮度 `brightness` (1~255 或 `brightness_pct` 1~100%)、色温 `color_temp_kelvin` (**2600~5000K**) | Wi-Fi (Xiaomi Home) |
| `plug` | 米家智能插座 3 (cuco.v3) | `switch.cuco_cn_945537660_v3_on_p_2_1` | 开关 (`on`/`off`)、当前功率 `sensor.cuco_cn_945537660_v3_electric_power_p_11_2` (W) | Wi-Fi (Xiaomi Home) |
| `motion` | 小米人体传感器 2 (bmgl01) | `event.lumi_cn_blt_3_17rvrv1hoeg00_bmgl01_motion_detected_e_2_1` | 移动事件 `Motion Detected`、光照 `sensor.lumi_..._illumination_degree_p_2_1` (Weak/Strong) | BLE 蓝牙（经小爱网关） |
| `climate` | 米家智能温湿度计 3 (t9) | `sensor.miaomiaoc_cn_blt_3_1f1nk3kg4k800_t9_temperature_p_3_1001` | 实时温度 (`℃`)、湿度 (`%`) | BLE 蓝牙（经小爱网关） |
| `speaker` | 小爱音箱 Play 增强版 (L05C) | `media_player.xiaomi_cn_567257618_l05c` | 媒体状态、音量、TTS 播报、红外发射通道 | Wi-Fi / 红外 / BLE Mesh 网关 |

---

## 2. 硬件控制规范与 API 示例

### 2.1 台灯控制 (lamp)
* **注意**：米家台灯 1S 的 MIoT 色温有效区间为 **2600K ~ 5000K**（低于 2600K 会触发 Property 越界错误）。
* **专注模式（冷白光 4000K，80% 亮度）**:
  ```json
  POST /api/services/light/turn_on
  {
    "entity_id": "light.yeelink_cn_313523278_lamp4_s_2_light",
    "brightness": 204,
    "color_temp_kelvin": 4000
  }
  ```
* **伴眠/放松模式（暖黄光 2600K，10% 亮度）**:
  ```json
  POST /api/services/light/turn_on
  {
    "entity_id": "light.yeelink_cn_313523278_lamp4_s_2_light",
    "brightness": 25,
    "color_temp_kelvin": 2600
  }
  ```

### 2.2 插座控制 (plug)
* **通电 / 断电**:
  ```json
  POST /api/services/switch/turn_on (或 turn_off)
  {
    "entity_id": "switch.cuco_cn_945537660_v3_on_p_2_1"
  }
  ```
* **读取当前功率**:
  `GET /api/states/sensor.cuco_cn_945537660_v3_electric_power_p_11_2`

### 2.3 人体移动监测 (motion)
* **移动事件监听**:
  `GET /api/states/event.lumi_cn_blt_3_17rvrv1hoeg00_bmgl01_motion_detected_e_2_1`

### 2.4 温湿度读取 (climate)
* **温度**: `GET /api/states/sensor.miaomiaoc_cn_blt_3_1f1nk3kg4k800_t9_temperature_p_3_1001`

---

## 3. 验收验证记录 (A-01)
- [x] Home Assistant 官方 Docker 容器稳定运行在 `http://localhost:8123`；
- [x] 安装官方集成 `ha_xiaomi_home` 并成功绑定米家账号；
- [x] 生成长期访问令牌，全部 5 款物理设备实体映射完成并入库；
- [x] 台灯专注光（4000K/80%）与伴眠光（2600K/10%）通过 Python 脚本实体验证成功。
