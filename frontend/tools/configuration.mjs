// 只解析显式前端配置；跨端字段和路径链接必须拒绝，错误不得回显值。
/** 显式读取前端配置：仅三个公开 URL 和工具端口，不发现 dotenv。 */
import { readFileSync, lstatSync, realpathSync } from "node:fs";
import { resolve, isAbsolute, dirname } from "node:path";
import { PUBLIC_FRONTEND_FIELDS, frontendPublicDefinitions } from "./frontend-public-env.mjs";

const allowed = new Set([...PUBLIC_FRONTEND_FIELDS, "FRONTEND_PORT"]);
/* 配置错误只包含类别和允许的字段名，不带配置值或文件正文。 */
const fail = (category, name = "") => {
  throw new Error("frontend_config:" + category + (name ? ":" + name : ""));
};

/* 解析显式前端配置，拒绝重复、未知及跨端字段；只产出前端公开字段和启动端口。 */
export function parseFrontendConfiguration(text) {
  const values = {};
  for (let line of text.replace(/^\uFEFF/, "").split(/\r?\n/)) {
    line = line.trim();
    if (!line || line.startsWith("#")) continue;
    if (line.startsWith("export ")) line = line.slice(7).trimStart();
    const match = /^([A-Za-z_][A-Za-z0-9_]*)\s*=(.*)$/.exec(line);
    if (!match) fail("invalid_entry");
    const [, name, raw] = match;
    if (!allowed.has(name)) fail("unknown_or_cross_module_field");
    if (Object.hasOwn(values, name)) fail("duplicate_field", name);
    let value = raw.trim();
    if (/^['"]/.test(value)) {
      const end = value.indexOf(value[0], 1);
      if (
        end < 1 ||
        (value.slice(end + 1).trim() &&
          !value
            .slice(end + 1)
            .trimStart()
            .startsWith("#"))
      )
        fail("invalid_quoted_value", name);
      value = value.slice(1, end);
    } else value = value.split(" #", 1)[0].trimEnd();
    if (/[\r\n\0]/.test(value)) fail("invalid_value", name);
    values[name] = value;
  }
  frontendPublicDefinitions(values);
  const port = values.FRONTEND_PORT ?? "8180";
  if (!/^[1-9][0-9]*$/.test(port) || Number(port) > 65535) fail("invalid_port", "FRONTEND_PORT");
  return Object.freeze({ ...values, FRONTEND_PORT: port });
}

/* 要求绝对普通文件路径并检查祖先链接，严格按 UTF-8 读取；失败不回显内容。 */
export function loadFrontendConfiguration(path) {
  if (!path || !isAbsolute(path)) fail("explicit_file_required");
  try {
    const absolute = resolve(path);
    for (let current = absolute; ; current = dirname(current)) {
      if (
        lstatSync(current).isSymbolicLink() ||
        realpathSync(current).toLowerCase() !== current.toLowerCase()
      )
        fail("reparse_path_forbidden");
      if (dirname(current) === current) break;
    }
    if (!lstatSync(absolute).isFile()) fail("regular_file_required");
    return parseFrontendConfiguration(
      new TextDecoder("utf-8", { fatal: true }).decode(readFileSync(absolute)),
    );
  } catch (error) {
    if (error instanceof Error && error.message.startsWith("frontend_config:")) throw error;
    fail("file_unreadable");
  }
}
