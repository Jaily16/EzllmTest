<template>
  <section
    class="document-group"
    :data-state="status"
    :aria-labelledby="`${groupId}-title`"
    :aria-busy="busy || undefined"
  >
    <header class="document-group__header">
      <div>
        <h2 :id="`${groupId}-title`">{{ title }}</h2>
        <p>{{ description }}</p>
      </div>
      <span class="document-group__status">{{ statusLabel }}</span>
    </header>

    <div v-if="storedFiles.length" class="document-group__stored">
      <strong>已上传并将在重试时复用</strong>
      <ul>
        <li v-for="filename in storedFiles" :key="filename">{{ filename }}</li>
      </ul>
    </div>

    <p v-if="progress" class="document-group__progress" aria-live="polite">
      正在上传 {{ progress.current }}/{{ progress.total }}：{{ progress.fileName }}
    </p>
    <p v-if="error" class="document-group__error" role="alert">{{ error }}</p>

    <p v-if="disabled" class="document-group__locked" role="status">
      本组已有可复用文档，无需再次选择。
    </p>
    <el-upload
      v-else
      :file-list="modelValue"
      @update:file-list="updateModelValue"
      class="document-group__upload"
      drag
      accept=".txt,.pdf,.md,.doc,.docx"
      multiple
      show-file-list
      :http-request="noAutomaticUpload"
      :before-upload="beforeUpload"
      :before-remove="beforeRemove"
      :disabled="busy"
    >
      <div class="document-group__drop-copy">
        <strong>拖拽文档到此处，或点击选择</strong>
        <span>支持 txt、pdf、md、doc、docx；单个文件不超过 {{ maxSizeMb }}MB</span>
      </div>
      <template #tip>
        <p class="document-group__tip">待上传文件只保留在当前浏览器页面；刷新后需要重新选择。</p>
      </template>
    </el-upload>
  </section>
</template>

<script lang="ts" setup>
/* global defineEmits, defineProps */
import { computed } from "vue";
import type { UploadProps, UploadUserFile } from "element-plus";
import type { SetupStepState } from "@/features/onboarding/state/projectSetup";

interface UploadProgress {
  fileName: string;
  current: number;
  total: number;
}

const props = defineProps<{
  groupId: string;
  title: string;
  description: string;
  maxSizeMb: number;
  status: SetupStepState;
  storedFiles: string[];
  modelValue: UploadUserFile[];
  disabled: boolean;
  busy: boolean;
  progress?: UploadProgress;
  error?: string;
  beforeUpload: NonNullable<UploadProps["beforeUpload"]>;
  beforeRemove: NonNullable<UploadProps["beforeRemove"]>;
}>();

const emit = defineEmits<{
  (event: "update:modelValue", value: UploadUserFile[]): void;
}>();

const updateModelValue = (value: UploadUserFile[]): void => {
  if (value === props.modelValue) return;
  emit("update:modelValue", value);
};

const statusLabels: Record<SetupStepState, string> = {
  pending: "待补充",
  running: "上传中",
  completed: "已完成",
  failed: "需要重试",
};

const statusLabel = computed(() => statusLabels[props.status]);
const noAutomaticUpload = (): undefined => undefined;
</script>

<style scoped>
.document-group {
  min-width: 0;
  padding: var(--ez-space-6);
  border: 1px solid var(--ez-color-border);
  border-radius: var(--ez-radius-large);
  background: var(--ez-color-surface);
  box-shadow: var(--ez-shadow-small);
}

.document-group[data-state="running"] {
  border-color: var(--ez-color-brand-300);
}
.document-group[data-state="completed"] {
  border-color: var(--ez-color-success);
}
.document-group[data-state="failed"] {
  border-color: var(--ez-color-danger);
}

.document-group__header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: var(--ez-space-4);
  min-width: 0;
}

h2,
p {
  overflow-wrap: anywhere;
}

h2 {
  margin: 0;
  font-size: var(--ez-font-size-20);
  line-height: var(--ez-line-height-tight);
}

.document-group__header p,
.document-group__tip {
  margin: var(--ez-space-1) 0 0;
  color: var(--ez-color-text-secondary);
  font-size: var(--ez-font-size-13);
  line-height: var(--ez-line-height-body);
}

.document-group__status {
  flex: 0 0 auto;
  padding: var(--ez-space-1) var(--ez-space-2);
  border-radius: var(--ez-radius-pill);
  background: var(--ez-color-locked-bg);
  color: var(--ez-color-locked);
  font-size: var(--ez-font-size-12);
  font-weight: 700;
}

[data-state="running"] .document-group__status {
  background: var(--ez-color-brand-50);
  color: var(--ez-color-brand-700);
}

[data-state="completed"] .document-group__status {
  background: var(--ez-color-success-bg);
  color: var(--ez-color-success);
}

[data-state="failed"] .document-group__status {
  background: var(--ez-color-danger-bg);
  color: var(--ez-color-danger);
}

.document-group__stored,
.document-group__progress,
.document-group__error,
.document-group__locked {
  margin-top: var(--ez-space-4);
  padding: var(--ez-space-3);
  border-radius: var(--ez-radius-medium);
  overflow-wrap: anywhere;
}

.document-group__stored {
  background: var(--ez-color-success-bg);
  color: var(--ez-color-success);
}

.document-group__stored ul {
  margin: var(--ez-space-2) 0 0;
  padding-left: var(--ez-space-6);
}

.document-group__stored li {
  overflow-wrap: anywhere;
}
.document-group__progress {
  background: var(--ez-color-brand-50);
  color: var(--ez-color-brand-700);
}
.document-group__error {
  background: var(--ez-color-danger-bg);
  color: var(--ez-color-danger);
}
.document-group__locked {
  background: var(--ez-color-locked-bg);
  color: var(--ez-color-locked);
}

.document-group__upload {
  min-width: 0;
  margin-top: var(--ez-space-4);
}

.document-group__upload :deep(.el-upload),
.document-group__upload :deep(.el-upload-dragger) {
  width: 100%;
  min-width: 0;
}

.document-group__upload :deep(.el-upload-list__item-name) {
  white-space: normal;
  overflow-wrap: anywhere;
}

.document-group__drop-copy {
  display: grid;
  gap: var(--ez-space-1);
  color: var(--ez-color-text-primary);
}

.document-group__drop-copy span {
  color: var(--ez-color-text-secondary);
  font-size: var(--ez-font-size-13);
}

@media (max-width: 767px) {
  .document-group {
    padding: var(--ez-space-4);
  }
  .document-group__header {
    align-items: flex-start;
    flex-direction: column;
  }
}
</style>
