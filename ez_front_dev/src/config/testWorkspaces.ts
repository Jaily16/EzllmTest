/* global require */
import type { TestMenuState } from "@/state/projectAnalysis";

export type TestWorkspaceKey = Exclude<keyof TestMenuState, "test_plan">;

export type TestWorkspaceStatus =
  | "available"
  | "stale"
  | "locked"
  | "not-recommended"
  | "regenerating";

export interface TestWorkspaceDefinition {
  key: TestWorkspaceKey;
  title: string;
  englishTitle: string;
  route: string;
  terminalOperation: string;
  nextStep: string;
  illustration: string;
}

export interface TestWorkspaceCardViewModel extends TestWorkspaceDefinition {
  status: TestWorkspaceStatus;
  statusLabel: string;
  reason: string;
  progressHint: string;
  disabled: boolean;
}

export const TEST_WORKSPACES: readonly TestWorkspaceDefinition[] = [
  {
    key: "unit_test",
    title: "单元测试",
    englishTitle: "Unit Testing",
    route: "/unit",
    terminalOperation: "unit_case",
    nextStep: "先识别可测试模块、类与函数，再生成当前会话结果。",
    illustration: require("@/assets/static/image/test-types-v2/unit-testing.png"),
  },
  {
    key: "integration_test",
    title: "集成测试",
    englishTitle: "Integration Testing",
    route: "/integration",
    terminalOperation: "integration_case",
    nextStep: "先分析模块协作关系，再选择集成策略与目标。",
    illustration: require("@/assets/static/image/test-types-v2/integration-testing.png"),
  },
  {
    key: "api_test",
    title: "API 接口测试",
    englishTitle: "API Testing",
    route: "/api",
    terminalOperation: "api_case",
    nextStep: "先识别接口与约束，再生成当前会话结果。",
    illustration: require("@/assets/static/image/test-types-v2/api-testing.png"),
  },
  {
    key: "ui_test",
    title: "前端 UI 测试",
    englishTitle: "UI Testing",
    route: "/ui",
    terminalOperation: "ui_case",
    nextStep: "先分析页面与交互，再生成并保存测试结果。",
    illustration: require("@/assets/static/image/test-types-v2/ui-testing.png"),
  },
  {
    key: "db_test",
    title: "数据库测试",
    englishTitle: "Database Testing",
    route: "/database",
    terminalOperation: "db_case",
    nextStep: "先分析数据结构与约束，再生成并保存测试结果。",
    illustration: require("@/assets/static/image/test-types-v2/database-testing.png"),
  },
  {
    key: "functional_test",
    title: "系统功能性测试",
    englishTitle: "Functional Testing",
    route: "/functional",
    terminalOperation: "functional_case",
    nextStep: "先识别业务用例，再生成当前会话结果。",
    illustration: require("@/assets/static/image/test-types-v2/functional-testing.png"),
  },
  {
    key: "nonfunctional_test",
    title: "系统非功能性测试",
    englishTitle: "Nonfunctional Testing",
    route: "/nfunctional",
    terminalOperation: "nonfunctional_case",
    nextStep: "先提取质量属性与约束，再生成当前会话结果。",
    illustration: require("@/assets/static/image/test-types-v2/nonfunctional-testing.png"),
  },
  {
    key: "acceptance_test",
    title: "验收测试",
    englishTitle: "Acceptance Testing",
    route: "/acceptance",
    terminalOperation: "acceptance_case",
    nextStep: "先核对验收目标，再生成并保存测试结果。",
    illustration: require("@/assets/static/image/test-types-v2/acceptance-testing.png"),
  },
] as const;
