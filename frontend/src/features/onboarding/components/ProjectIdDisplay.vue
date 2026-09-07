<template>
  <section
    class="project-id"
    :class="{ 'project-id--compact': compact }"
    :aria-labelledby="titleId"
  >
    <div class="project-id__copy">
      <strong :id="titleId">{{ label }}</strong>
      <code>{{ pid }}</code>
      <p>{{ guidance }}</p>
      <span class="project-id__announcement" aria-live="polite">{{ announcement }}</span>
    </div>
    <el-button type="primary" plain :disabled="!pid" @click="copyProjectId">
      复制项目 ID
    </el-button>
  </section>
</template>

<script lang="ts" setup>
/* global defineProps, withDefaults */
import { ref } from "vue";
import useClipboard from "vue-clipboard3";

const props = withDefaults(
  defineProps<{
    pid: string;
    label?: string;
    guidance?: string;
    compact?: boolean;
    titleId?: string;
  }>(),
  {
    label: "项目 ID",
    guidance: "这是恢复项目的唯一入口，请妥善保存且不要公开分享。",
    compact: false,
    titleId: "project-id-title",
  },
);

const { toClipboard } = useClipboard();
const announcement = ref("");

/**
 * 复制项目 ID，并保持现有状态与错误处理语义。
 */
const copyProjectId = async (): Promise<void> => {
  try {
    await toClipboard(props.pid);
    announcement.value = "项目 ID 已复制";
  } catch {
    announcement.value = "复制失败，请手动选择项目 ID 保存";
  }
};
</script>

<style scoped>
.project-id {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--ez-space-4);
  min-width: 0;
  padding: var(--ez-space-4);
  border: 1px solid var(--ez-color-brand-100);
  border-radius: var(--ez-radius-medium);
  background: var(--ez-color-brand-50);
}

.project-id--compact {
  padding: var(--ez-space-3);
}
.project-id__copy {
  min-width: 0;
}

strong,
code,
p {
  overflow-wrap: anywhere;
}

strong,
code {
  display: block;
}

code {
  margin-top: var(--ez-space-1);
  color: var(--ez-color-brand-700);
  font-family: var(--ez-font-code);
  font-size: var(--ez-font-size-14);
}

p {
  margin: var(--ez-space-1) 0 0;
  color: var(--ez-color-text-secondary);
  font-size: var(--ez-font-size-13);
  line-height: var(--ez-line-height-body);
}

.project-id__announcement {
  display: block;
  min-height: 1.4em;
  margin-top: var(--ez-space-1);
  color: var(--ez-color-success);
  font-size: var(--ez-font-size-12);
}

@media (max-width: 480px) {
  .project-id {
    align-items: stretch;
    flex-direction: column;
  }
  .project-id :deep(.el-button) {
    width: 100%;
    margin: 0;
  }
}
</style>
