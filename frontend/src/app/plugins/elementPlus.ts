// 应用插件装配负责组件注册，页面不重复安装全局插件。
import type { App, Component } from "vue";
import {
  Box,
  Close,
  CollectionTag,
  DataAnalysis,
  Files,
  HelpFilled,
  HomeFilled,
  Lock,
  Magnet,
  Menu,
  MessageBox,
  Monitor,
  Notebook,
  Orange,
  Platform,
  Reading,
} from "@element-plus/icons-vue";
import { ElAlert } from "element-plus/es/components/alert/index";
import { ElButton } from "element-plus/es/components/button/index";
import { ElCollapse, ElCollapseItem } from "element-plus/es/components/collapse/index";
import { ElDialog } from "element-plus/es/components/dialog/index";
import { ElIcon } from "element-plus/es/components/icon/index";
import { ElInput } from "element-plus/es/components/input/index";
import {
  ElMenu,
  ElMenuItem,
  ElMenuItemGroup,
  ElSubMenu,
} from "element-plus/es/components/menu/index";
import { ElMessage } from "element-plus/es/components/message/index";
import { ElMessageBox } from "element-plus/es/components/message-box/index";
import { ElOption, ElSelect } from "element-plus/es/components/select/index";
import { ElProgress } from "element-plus/es/components/progress/index";
import { ElRadioButton, ElRadioGroup } from "element-plus/es/components/radio/index";
import { ElSegmented } from "element-plus/es/components/segmented/index";
import { ElStep, ElSteps } from "element-plus/es/components/steps/index";
import { ElTag } from "element-plus/es/components/tag/index";
import { ElUpload } from "element-plus/es/components/upload/index";

import "element-plus/es/components/alert/style/css";
import "element-plus/es/components/button/style/css";
import "element-plus/es/components/collapse/style/css";
import "element-plus/es/components/collapse-item/style/css";
import "element-plus/es/components/dialog/style/css";
import "element-plus/es/components/icon/style/css";
import "element-plus/es/components/input/style/css";
import "element-plus/es/components/menu/style/css";
import "element-plus/es/components/menu-item/style/css";
import "element-plus/es/components/menu-item-group/style/css";
import "element-plus/es/components/message/style/css";
import "element-plus/es/components/message-box/style/css";
import "element-plus/es/components/progress/style/css";
import "element-plus/es/components/radio-button/style/css";
import "element-plus/es/components/radio-group/style/css";
import "element-plus/es/components/segmented/style/css";
import "element-plus/es/components/step/style/css";
import "element-plus/es/components/steps/style/css";
import "element-plus/es/components/sub-menu/style/css";
import "element-plus/es/components/tag/style/css";
import "element-plus/es/components/upload/style/css";

const components: Component[] = [
  ElAlert,
  ElButton,
  ElCollapse,
  ElCollapseItem,
  ElDialog,
  ElIcon,
  ElInput,
  ElMenu,
  ElMenuItem,
  ElMenuItemGroup,
  ElOption,
  ElProgress,
  ElRadioButton,
  ElRadioGroup,
  ElSegmented,
  ElSelect,
  ElStep,
  ElSteps,
  ElSubMenu,
  ElTag,
  ElUpload,
];

const icons: Record<string, Component> = {
  Box,
  Close,
  CollectionTag,
  DataAnalysis,
  Files,
  HelpFilled,
  HomeFilled,
  Lock,
  Magnet,
  Menu,
  MessageBox,
  Monitor,
  Notebook,
  Orange,
  Platform,
  Reading,
};

/** 仅注册项目实际使用的 Element Plus 组件及图标，插件安装由应用入口统一调用。 */
export const installElementPlus = (app: App): void => {
  components.forEach((component) => {
    if (component.name) app.component(component.name, component);
  });
  Object.entries(icons).forEach(([name, component]) => app.component(name, component));
};

export { ElMessage, ElMessageBox };
