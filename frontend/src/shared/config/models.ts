// 维护模型公开标签与展示名称，实际 Provider 参数由后端配置决定。
export const MODEL_LABELS = ["GLM-4.7", "通义千问", "DeepSeek", "Moonshot Kimi"] as const;

export type ModelLabel = (typeof MODEL_LABELS)[number];

export const DEFAULT_MODEL: ModelLabel = MODEL_LABELS[0];

export const MODEL_DISPLAY_NAMES: Record<ModelLabel, string> = {
  "GLM-4.7": "glm-4.7",
  通义千问: "qwen3.5-plus",
  DeepSeek: "deepseek-v4-flash",
  "Moonshot Kimi": "kimi-k3",
};

export const MODEL_OPTIONS = MODEL_LABELS.map((value) => ({
  label: MODEL_DISPLAY_NAMES[value],
  value,
}));
