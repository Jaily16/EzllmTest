import json
from pathlib import Path


from repo_paths import canonical_frontend_path
from repo_paths import REPO_ROOT as ROOT
FRONTEND = ROOT / "ez_front_dev"


def test_vite_toolchain_is_exact_and_vue_cli_is_removed():
    package = json.loads((FRONTEND / "package.json").read_text(encoding="utf-8"))
    contract = json.loads(
        (ROOT / "ops" / "version-contract.json").read_text(encoding="utf-8")
    )
    assert {
        key: package["scripts"][key]
        for key in ("serve", "build", "lint", "type-check")
    } == {
        "serve": "vite --host 127.0.0.1",
        "build": "vite build",
        "lint": "eslint src",
        "type-check": "vue-tsc --noEmit",
    }
    assert package["scripts"]["format"] == (
        "prettier --ignore-path ../.prettierignore --write src"
    )
    assert package["scripts"]["format:check"] == (
        "prettier --ignore-path ../.prettierignore --check src"
    )
    assert package["devDependencies"] | {
        key: package["devDependencies"].get(key)
        for key in (
            "vite",
            "@vitejs/plugin-vue",
            "@vue/compiler-sfc",
            "vue-tsc",
            "typescript",
            "eslint",
            "@eslint/js",
            "eslint-plugin-vue",
            "@typescript-eslint/parser",
            "@typescript-eslint/eslint-plugin",
            "@vue/eslint-config-typescript",
        )
    }
    assert {
        key: package["devDependencies"][key]
        for key in (
            "vite",
            "@vitejs/plugin-vue",
            "@vue/compiler-sfc",
            "vue-tsc",
            "typescript",
            "eslint",
            "@eslint/js",
            "eslint-plugin-vue",
            "@typescript-eslint/parser",
            "@typescript-eslint/eslint-plugin",
            "@vue/eslint-config-typescript",
        )
    } == {
        key: contract["node_lock"]["direct_dev_dependencies"][key]
        for key in (
            "vite",
            "@vitejs/plugin-vue",
            "@vue/compiler-sfc",
            "vue-tsc",
            "typescript",
            "eslint",
            "@eslint/js",
            "eslint-plugin-vue",
            "@typescript-eslint/parser",
            "@typescript-eslint/eslint-plugin",
            "@vue/eslint-config-typescript",
        )
    }
    assert not any(key.startswith("@vue/cli-") for key in package["devDependencies"])
    assert not (FRONTEND / "vue.config.js").exists()
    assert not (FRONTEND / "babel.config.js").exists()
    assert not (FRONTEND / ".eslintrc.js").exists()


def test_vite_config_preserves_alias_env_and_production_contracts():
    config = (FRONTEND / "vite.config.ts").read_text(encoding="utf-8")
    for required in (
        'envPrefix: ["VITE_", "VUE_APP_"]',
        'alias: { "@": fileURLToPath(new URL("./src", import.meta.url)) }',
        'target: "es2022"',
        'cssTarget: "chrome111"',
        "sourcemap: false",
        "__VUE_PROD_HYDRATION_MISMATCH_DETAILS__: false",
    ):
        assert required in config
    index = (FRONTEND / "index.html").read_text(encoding="utf-8")
    assert '<html lang="zh-CN">' in index
    assert '<link rel="icon" type="image/png" sizes="48x48" href="/favicon.png">' in index
    assert "<title>ez_front_dev</title>" in index
    assert '<script type="module" src="/src/main.ts"></script>' in index
    assert not (FRONTEND / "public/index.html").exists()


def test_vite_sources_use_typed_env_and_static_esm_assets():
    source_text = "\n".join(
        path.read_text(encoding="utf-8")
        for path in (FRONTEND / "src").rglob("*")
        if path.suffix in {".ts", ".vue"}
    )
    assert "process.env" not in source_text
    assert "require(" not in source_text
    assert "webpackChunkName" not in source_text
    env_types = (FRONTEND / "src/vite-env.d.ts").read_text(encoding="utf-8")
    for name in (
        "VUE_APP_API_BASE_URL",
        "VUE_APP_AGENT_API_BASE_URL",
        "VUE_APP_GRAFANA_BASE_URL",
    ):
        assert f"readonly {name}: string" in env_types
    tsconfig = json.loads((FRONTEND / "tsconfig.json").read_text(encoding="utf-8"))
    assert tsconfig["compilerOptions"]["moduleResolution"] == "Bundler"
    assert tsconfig["compilerOptions"]["sourceMap"] is False
    assert "vite/client" in tsconfig["compilerOptions"]["types"]


def test_trace_projection_is_truthful_and_has_optional_grafana_link():
    state = canonical_frontend_path("ez_front_dev/src/state/agentWorkbench.ts").read_text(encoding="utf-8")
    workbench = canonical_frontend_path("ez_front_dev/src/components/AgentWorkbench.vue").read_text(
        encoding="utf-8"
    )
    main = (FRONTEND / "src/main.ts").read_text(encoding="utf-8")
    assert 'trace_status: "not_instrumented" | "instrumented"' in state
    assert "trace_id: string | null" in state
    assert "$grafanaBaseUrl" in main
    assert "copyTraceId" in workbench
    assert "grafanaTraceUrl" in workbench
    assert "尚未启用（Aspect 7）" not in workbench
    assert "v-html" not in workbench


def test_vite_defers_select_css_with_the_lazy_test_target_chunk():
    plugin = canonical_frontend_path("ez_front_dev/src/plugins/elementPlus.ts").read_text(encoding="utf-8")
    selector = canonical_frontend_path("ez_front_dev/src/components/testing/TestTargetSelector.vue").read_text(
        encoding="utf-8"
    )
    for stylesheet in (
        'element-plus/es/components/option/style/css',
        'element-plus/es/components/select/style/css',
    ):
        assert stylesheet not in plugin
        assert stylesheet in selector
