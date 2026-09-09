// 只负责 SSE 块解码；连接、取消、保存和重放语义由调用方管理。
/** 通用 SSE 单帧解码，保留注释、多行 data 与 JSON 错误语义。 */
export interface ParsedSseEvent {
  event: string;
  data: Record<string, unknown>;
}

/* 解析单个 SSE 块的事件名及多行 JSON data；跳过注释心跳，JSON 错误交给流生命周期处理器。 */
export const parseSseBlock = (block: string): ParsedSseEvent | null => {
  let event = "message";
  const dataLines: string[] = [];
  for (const line of block.split(/\r?\n/)) {
    if (line.startsWith(":")) continue;
    if (line.startsWith("event:")) {
      event = line.slice(6).trim();
    } else if (line.startsWith("data:")) {
      dataLines.push(line.slice(5).trimStart());
    }
  }
  if (dataLines.length === 0) return null;
  const parsed = JSON.parse(dataLines.join("\n"));
  if (typeof parsed !== "object" || parsed === null) return null;
  return { event, data: parsed as Record<string, unknown> };
};
