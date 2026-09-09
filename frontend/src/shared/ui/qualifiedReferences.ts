// 把目标限定引用拆为展示信息；请求始终保留原始稳定值。
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
 * 保留原始值用于请求，将限定名和来源提示分开显示，兼容旧的非限定名称。
 * @param rawValue 沿用当前 TypeScript 类型约束的输入。
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
