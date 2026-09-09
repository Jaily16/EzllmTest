// Node 离线测试的源码加载适配，不向产品源码写入转译产物。
/** Node 内置测试加载实际 TypeScript，不引入测试框架或写入编译副本。 */
import { registerHooks } from "node:module";
import { readFileSync, existsSync } from "node:fs";
import { fileURLToPath, pathToFileURL } from "node:url";
import ts from "typescript";

registerHooks({
  /* 仅为离线 Node 用例解析源码别名和 TypeScript 扩展，不改变产品构建解析规则。 */
  resolve(specifier, context, nextResolve) {
    let candidate;
    if (specifier.startsWith("@/"))
      candidate = new URL("../src/" + specifier.slice(2), import.meta.url);
    else if (specifier.startsWith(".") && context.parentURL?.endsWith(".ts"))
      candidate = new URL(specifier, context.parentURL);
    if (candidate && !/\.[a-z]+$/i.test(candidate.pathname)) {
      const path = fileURLToPath(candidate) + ".ts";
      if (existsSync(path)) return { url: pathToFileURL(path).href, shortCircuit: true };
    }
    return nextResolve(specifier, context);
  },
  /* 将测试实际引用的 TypeScript 在内存转译为 ES 模块，不向源码目录输出产物。 */
  load(url, context, nextLoad) {
    if (url.endsWith(".ts")) {
      const source = ts.transpileModule(readFileSync(new URL(url), "utf8"), {
        compilerOptions: { module: ts.ModuleKind.ESNext, target: ts.ScriptTarget.ES2022 },
      }).outputText;
      return { format: "module", source, shortCircuit: true };
    }
    return nextLoad(url, context);
  },
});
