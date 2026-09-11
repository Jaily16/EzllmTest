// 离线用例使用人工配置和内存状态，覆盖 SSE、公开配置、旧结果保留及路由契约。
/** 实际 SSE、公开配置、菜单路由与工作流状态的离线回归。 */
import test from "node:test";
import assert from "node:assert/strict";
import { parseSseBlock } from "../src/shared/transport/sse.ts";
import {
  frontendConfigurationPath,
  loadFrontendConfiguration,
  parseFrontendConfiguration,
} from "../tools/configuration.mjs";
import { fileURLToPath } from "node:url";
import { mkdtempSync, writeFileSync, unlinkSync, rmdirSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { spawnSync } from "node:child_process";
import { frontendPublicDefinitions } from "../tools/frontend-public-env.mjs";
import {
  useTestWorkflow,
  normalizeSelections,
} from "../src/entities/workflow/model/useTestWorkflow.ts";
import {
  resetProjectAnalysisState,
  setProjectAnalysisReady,
  isWorkflowRouteAllowed,
} from "../src/entities/project/model/analysis.ts";

/* 人工 SSE 块覆盖心跳、多行 JSON、null 和损坏数据，不建立网络连接。 */
test("SSE comments, multi-line data, invalid JSON and empty frames", () => {
  assert.equal(parseSseBlock(": heartbeat"), null);
  assert.deepEqual(parseSseBlock('event: result\ndata: {"value":\ndata: 3}'), {
    event: "result",
    data: { value: 3 },
  });
  assert.equal(parseSseBlock("data: null"), null);
  assert.throws(() => parseSseBlock("data: broken"));
});
const valid = [
  "VUE_APP_API_BASE_URL=http://127.0.0.1:8230",
  "VUE_APP_AGENT_API_BASE_URL=http://127.0.0.1:8231",
  "VUE_APP_OBSERVABILITY_API_BASE_URL=http://127.0.0.1:8140",
].join("\n");
/* 用人工配置验证公开字段数量、跨端字段、端口和地址限制，错误不得包含测试秘密值。 */
test("frontend exposes exactly three URLs and rejects secrets, duplicates and remote URL", () => {
  const config = parseFrontendConfiguration(valid);
  assert.equal(Object.keys(frontendPublicDefinitions(config)).length, 3);
  for (const invalid of [
    valid + "\nDATABASE_URL=synthetic-private",
    valid + "\nFRONTEND_PORT=0",
    valid + "\nFRONTEND_PORT=8180\nFRONTEND_PORT=8181",
    valid.replace("127.0.0.1", "example.com"),
  ]) {
    assert.throws(
      () => parseFrontendConfiguration(invalid),
      (error) =>
        error.message.startsWith("frontend_config:") &&
        !error.message.includes("synthetic-private"),
    );
  }
});
/* 用内存状态验证依赖锁及重试失败恢复有效结果；同时检查选择条件稳定排序。 */
test("workflow gates and failure preserve completed result", () => {
  const storage = new Map();
  globalThis.localStorage = {
    /* 从内存 Map 模拟存储读取，不接触用户浏览器记录。 */
    getItem: (k) => storage.get(k) ?? null,
    /* 把人工恢复载荷写入内存 Map，不写真实浏览器存储。 */
    setItem: (k, v) => storage.set(k, v),
    /* 仅移除测试内存中的恢复键。 */
    removeItem: (k) => storage.delete(k),
  };
  const workflow = useTestWorkflow({
    baseUrl: "http://127.0.0.1:49999",
    pid: "EzOffline",
    steps: [
      { operation: "a", label: "first" },
      { operation: "b", label: "second" },
    ],
  });
  assert.equal(workflow.canRunStep("b"), false);
  assert.equal(workflow.beginStep("a"), true);
  workflow.completeStep("a", "effective", {}, { artifactKey: "a", sourceRevision: "revision" });
  assert.equal(workflow.canRunStep("b"), true);
  assert.equal(workflow.beginStep("a", { regenerate: true, keepPreviousOnFailure: true }), true);
  workflow.failStep("a");
  assert.equal(workflow.resultFor("a"), "effective");
  assert.deepEqual(normalizeSelections({ b: 2, a: { z: 1, y: 2 } }), { a: { y: 2, z: 1 }, b: 2 });
});
/* 只更新人工项目菜单，验证未允许的测试路由保持关闭。 */
test("project menu keeps route guards based on current state", () => {
  resetProjectAnalysisState();
  assert.equal(isWorkflowRouteAllowed("/unit"), false);
  setProjectAnalysisReady({
    test_plan: true,
    unit_test: true,
    integration_test: false,
    api_test: false,
    ui_test: false,
    db_test: false,
    functional_test: false,
    nonfunctional_test: false,
    acceptance_test: false,
  });
  assert.equal(isWorkflowRouteAllowed("/unit"), true);
  assert.equal(isWorkflowRouteAllowed("/api"), false);
});

/* 从当前路由源码提取路径和名称，与冻结 fixture 比较；不会启动浏览器。 */
test("route URL and name ordering stays at the V6 contract", async () => {
  const { readFileSync } = await import("node:fs");
  const text = readFileSync(new URL("../src/app/router/index.ts", import.meta.url), "utf8");
  const values = [...text.matchAll(/\b(path|name)\s*:\s*(["'])(.*?)\2/g)].map((match) => ({
    field: match[1],
    value: match[3],
  }));
  const expected = JSON.parse(
    readFileSync(new URL("./router-fixture.json", import.meta.url), "utf8"),
  );
  assert.deepEqual(values, expected);
});

/* 固定源解析不读取真实 .env；人工文件验证显式兼容，临时目录由验收进程指定。 */
test("local frontend selector is CWD independent, exclusive and keeps explicit loading", () => {
  const scratch = mkdtempSync(join(tmpdir(), "frontend-config-"));
  const originalCwd = process.cwd();
  const path = join(scratch, "synthetic.env");
  try {
    writeFileSync(path, valid);
    process.chdir(scratch);
    for (const command of ["serve", "build"]) {
      assert.equal(
        frontendConfigurationPath([command, "--local-config"]),
        fileURLToPath(new URL("../.env", import.meta.url)),
      );
      assert.equal(frontendConfigurationPath([command, "--env-file", path]), path);
      assert.deepEqual(loadFrontendConfiguration(path), parseFrontendConfiguration(valid));
      for (const args of [
        [command],
        [command, "--env-file", "relative.env"],
        [command, "--local-config", "--env-file", path],
        [command, "--local-config", "extra"],
      ])
        assert.throws(() => frontendConfigurationPath(args), /frontend_config:/);
    }
    assert.throws(() => loadFrontendConfiguration(join(scratch, "missing.env")), /file_unreadable/);
    const help = spawnSync(
      process.execPath,
      [fileURLToPath(new URL("../tools/frontend.mjs", import.meta.url)), "--help"],
      { cwd: scratch, encoding: "utf8" },
    );
    assert.equal(help.status, 0);
    assert.match(help.stdout, /--local-config/);
  } finally {
    process.chdir(originalCwd);
    unlinkSync(path);
    rmdirSync(scratch);
  }
});
