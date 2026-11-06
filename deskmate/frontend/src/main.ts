import { createApp } from "vue";
import { createPinia } from "pinia";
import {
  ElButton,
  ElInput,
  ElSelect,
  ElOption,
  ElInputNumber,
  ElSwitch,
  ElSlider,
  ElDialog,
  ElDrawer,
  ElForm,
  ElFormItem,
  ElAlert,
  ElLoading,
  ElConfigProvider,
} from "element-plus";
import "element-plus/es/components/base/style/css";
import "element-plus/es/components/button/style/css";
import "element-plus/es/components/input/style/css";
import "element-plus/es/components/select/style/css";
import "element-plus/es/components/option/style/css";
import "element-plus/es/components/input-number/style/css";
import "element-plus/es/components/switch/style/css";
import "element-plus/es/components/slider/style/css";
import "element-plus/es/components/dialog/style/css";
import "element-plus/es/components/drawer/style/css";
import "element-plus/es/components/form/style/css";
import "element-plus/es/components/form-item/style/css";
import "element-plus/es/components/alert/style/css";
import "element-plus/es/components/loading/style/css";
import "element-plus/es/components/message/style/css";
import "element-plus/es/components/message-box/style/css";
import "highlight.js/styles/github.css";
import "./style.css";
import App from "./App.vue";
const app = createApp(App).use(createPinia());
for (const component of [
  ElButton,
  ElInput,
  ElSelect,
  ElOption,
  ElInputNumber,
  ElSwitch,
  ElSlider,
  ElDialog,
  ElDrawer,
  ElForm,
  ElFormItem,
  ElAlert,
  ElConfigProvider,
])
  app.component(component.name!, component);
app.directive("loading", ElLoading.directive);
app.mount("#app");
