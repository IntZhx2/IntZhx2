<script setup lang="ts">
import { reactive, watch } from "vue";
import { useApp } from "../stores/app";
import Icon from "../components/Icon.vue";
import type { Settings } from "../types/contracts";
const app = useApp(),
  form = reactive<{
    ac: Settings["ac"];
    wellbeing: Settings["wellbeing"];
    absent_confirm_min: number;
    absent_lamp_off_min: number;
    absent_ac_off_min: number;
  }>({
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
  });
function reset() {
  if (app.settings)
    for (const key of Object.keys(form) as (keyof typeof form)[])
      Object.assign(form, {
        [key]: JSON.parse(JSON.stringify(app.settings[key])),
      });
}
watch(() => app.settings, reset, { immediate: true });
async function save() {
  await app.saveSettings(JSON.parse(JSON.stringify(form)));
}
</script>
<template>
  <div class="page-enter settings-page">
    <div class="page-heading">
      <div>
        <h1>偏好设置</h1>
        <p>设置环境联动、离座规则和关怀阈值。</p>
      </div>
    </div>
    <form @submit.prevent="save">
      <section class="card padded-card">
        <div class="section-kicker"><Icon name="snow" /> 环境自动化</div>
        <el-form label-position="top"
          ><div class="form-two">
            <el-form-item label="专注时空调如何响应"
              ><el-select v-model="form.ac.auto_rule" aria-label="空调自动规则"
                ><el-option label="温度过高时自动开启" value="auto" /><el-option
                  label="先询问，再开启"
                  value="ask" /><el-option
                  label="不自动控制"
                  value="off" /></el-select></el-form-item
            ><el-form-item label="空调目标温度（°C）"
              ><el-input-number
                v-model="form.ac.summer_temp"
                :min="16"
                :max="30" /></el-form-item
            ><el-form-item label="自动开启温度阈值（°C）"
              ><el-input-number
                v-model="form.ac.trigger_on_temp"
                :min="16"
                :max="45"
                :step="0.5" /></el-form-item
            ><el-form-item label="高湿度提示阈值（%）"
              ><el-input-number
                v-model="form.ac.high_humidity_trigger"
                :min="0"
                :max="100"
            /></el-form-item></div
        ></el-form>
      </section>
      <section class="card padded-card">
        <div class="section-kicker"><Icon name="user" /> 离座照顾</div>
        <el-form label-position="top"
          ><div class="form-three">
            <el-form-item label="确认离座（分钟）"
              ><el-input-number
                v-model="form.absent_confirm_min"
                :min="1"
                :max="60" /></el-form-item
            ><el-form-item label="关灯与插座（分钟）"
              ><el-input-number
                v-model="form.absent_lamp_off_min"
                :min="1"
                :max="120" /></el-form-item
            ><el-form-item label="关闭空调（分钟）"
              ><el-input-number
                v-model="form.absent_ac_off_min"
                :min="form.absent_lamp_off_min"
                :max="240"
            /></el-form-item></div
        ></el-form>
        <p class="muted">
          锁屏立即暂停专注。离座阶梯的先后关系由后端校验，保存后即时生效。
        </p>
      </section>
      <section class="card padded-card">
        <div class="section-kicker"><Icon name="leaf" /> 疲劳关怀与心流</div>
        <p v-if="!app.healthAvailable" class="muted">
          健康引擎尚未接入。这些配置可以保存，接入后才会用于评分和介入。
        </p>
        <el-form label-position="top"
          ><div class="form-three">
            <el-form-item label="L1 灯光提醒分值"
              ><el-input-number
                v-model="form.wellbeing.l1_score"
                :min="0"
                :max="98" /></el-form-item
            ><el-form-item label="L2 语音关心分值"
              ><el-input-number
                v-model="form.wellbeing.l2_score"
                :min="form.wellbeing.l1_score + 1"
                :max="99" /></el-form-item
            ><el-form-item label="L3 休息建议分值"
              ><el-input-number
                v-model="form.wellbeing.l3_score"
                :min="form.wellbeing.l2_score + 1"
                :max="100" /></el-form-item
            ><el-form-item label="连续专注阈值（分钟）"
              ><el-input-number
                v-model="form.wellbeing.max_continuous_focus_min"
                :min="1"
                :max="240" /></el-form-item
            ><el-form-item label="同级提醒冷却（分钟）"
              ><el-input-number
                v-model="form.wellbeing.cooldown_min"
                :min="1"
                :max="120" /></el-form-item
            ><el-form-item label="每次心流顺延（分钟）"
              ><el-input-number
                v-model="form.wellbeing.flow_extension_min"
                :min="1"
                :max="60" /></el-form-item
            ><el-form-item label="最多顺延次数"
              ><el-input-number
                v-model="form.wellbeing.max_flow_extensions"
                :min="0"
                :max="2"
            /></el-form-item></div
        ></el-form>
      </section>
      <div class="settings-footer">
        <span
          ><Icon name="shield" :size="15" />
          {{
            app.preview ? "示例设置仅在本页生效" : "设置仅保存到当前账号"
          }}</span
        >
        <div>
          <el-button @click="reset">还原已保存值</el-button
          ><el-button
            type="primary"
            native-type="submit"
            :loading="app.busy"
            :disabled="!app.connected"
            >保存设置</el-button
          >
        </div>
      </div>
    </form>
  </div>
</template>
