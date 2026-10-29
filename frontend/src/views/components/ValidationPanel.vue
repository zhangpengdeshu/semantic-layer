<template>
  <div class="validation-panel">
    <div class="validation-panel__header">
      <span class="validation-panel__title">{{ title }}</span>
      <el-tag v-if="issues.length" :type="hasError ? 'danger' : 'success'" size="small">
        {{ hasError ? '未通过' : '通过' }}
      </el-tag>
      <el-button v-if="showRun" link size="small" :loading="loading" @click="$emit('run')">重新校验</el-button>
    </div>
    <div v-if="loading" class="validation-panel__empty">校验中...</div>
    <div v-else-if="!issues.length" class="validation-panel__empty">没有发现问题</div>
    <ul v-else class="validation-panel__list">
      <li v-for="(item, index) in issues" :key="index" class="validation-panel__item">
        <el-tag :type="item.level === 'error' ? 'danger' : 'warning'" size="small" effect="plain">
          {{ item.level === 'error' ? '错误' : '警告' }}
        </el-tag>
        <span class="validation-panel__code">{{ item.code }}</span>
        <span class="validation-panel__message">{{ item.message }}</span>
        <span v-if="item.suggestion" class="validation-panel__suggestion">{{ item.suggestion }}</span>
      </li>
    </ul>
  </div>
</template>

<script lang="ts">
import type { PropType } from 'vue'

export default {
  name: 'SemanticValidationPanel',
  props: {
    title: { type: String, default: '校验结果' },
    issues: { type: Array as PropType<any[]>, default: () => [] },
    loading: { type: Boolean, default: false },
    showRun: { type: Boolean, default: false },
  },
  computed: {
    hasError(): boolean {
      return (this.issues as any[]).some((item) => item.level === 'error')
    },
  },
}
</script>

<style scoped>
.validation-panel { border: 1px solid #ebeef5; border-radius: 4px; background: #fff; }
.validation-panel__header { display: flex; align-items: center; gap: 8px; padding: 10px 12px; border-bottom: 1px solid #ebeef5; }
.validation-panel__title { font-weight: 600; color: #303133; flex: 1; }
.validation-panel__empty { padding: 16px 12px; color: #909399; font-size: 13px; }
.validation-panel__list { list-style: none; margin: 0; padding: 0; max-height: 320px; overflow: auto; }
.validation-panel__item { display: flex; align-items: flex-start; gap: 8px; padding: 8px 12px; border-bottom: 1px solid #f5f7fa; font-size: 13px; }
.validation-panel__item:last-child { border-bottom: none; }
.validation-panel__code { color: #909399; font-family: Menlo, monospace; white-space: nowrap; }
.validation-panel__message { color: #303133; }
.validation-panel__suggestion { color: #909399; }
</style>