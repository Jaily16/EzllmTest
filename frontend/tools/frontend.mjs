// 命令行工具显式读取前端配置并清理继承冲突，serve 与 build 共享配置投影。
/** 普通终端的 Vite 入口：先校验显式文件，再加载工具和应用。 */
import { fileURLToPath } from "node:url";
import { frontendConfigurationPath, loadFrontendConfiguration } from "./configuration.mjs";

const args = process.argv.slice(2);
if (args.includes("--help")) {
  console.log(
    "node tools/frontend.mjs <serve|build> <--local-config | --env-file <absolute frontend config>>",
  );
} else {
  try {
    const configPath = frontendConfigurationPath(args);
    const values = loadFrontendConfiguration(configPath);
    for (const name of Object.keys(process.env)) {
      if (
        /^(VUE_APP_|VITE_|EZLLMTEST_|OBSERVABILITY_|AGENT_|DOTENV_|DATABASE_|REDIS_)/i.test(name) ||
        /PASSWORD|SECRET|TOKEN|API_KEY|NODE_OPTIONS/i.test(name)
      )
        delete process.env[name];
    }
    process.env.EZLLMTEST_FRONTEND_ENV_FILE = configPath;
    const vite = await import("vite");
    const options = {
      root: fileURLToPath(new URL("../", import.meta.url)),
      configFile: fileURLToPath(new URL("../vite.config.ts", import.meta.url)),
    };
    if (args[0] === "build") await vite.build(options);
    else {
      const server = await vite.createServer({
        ...options,
        server: { host: "127.0.0.1", port: Number(values.FRONTEND_PORT), strictPort: true },
      });
      await server.listen();
      server.printUrls();
    }
  } catch (error) {
    console.error(
      error instanceof Error && /^frontend_config:/.test(error.message)
        ? error.message
        : "frontend_tool:failed",
    );
    process.exitCode = 1;
  }
}
