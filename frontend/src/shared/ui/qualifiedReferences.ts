export const QUALIFIED_REFERENCE_SEPARATOR = " ｜ ";

export interface QualifiedReference {
  value: string;
  label: string;
  detail: string;
  displayName: string;
  qualifiedName: string;
  sourceHint: string;
}

/**
 * 解析限定引用，并保持现有状态与错误处理语义。
 *
 * @param rawValue 沿用当前 TypeScript 类型约束的输入。
 *
 * @returns 保持当前 TypeScript 返回类型与调用方约定。
 */
export const parseQualifiedReference = (rawValue: string): QualifiedReference => {
  const parts = rawValue.split(QUALIFIED_REFERENCE_SEPARATOR).map((part) => part.trim());
  if (parts.length < 2) {
    return {
      value: rawValue,
      label: rawValue,
      detail: rawValue,
      displayName: rawValue,
      qualifiedName: rawValue,
      sourceHint: "",
    };
  }
  const [displayName, qualifiedName, sourceHint = ""] = parts;
  const sourceLabel = sourceHint ? `（来源：${sourceHint}）` : "";
  return {
    value: rawValue,
    label: `${displayName} — ${qualifiedName}${sourceLabel}`,
    detail: `${qualifiedName}${sourceLabel}`,
    displayName,
    qualifiedName,
    sourceHint,
  };
};
