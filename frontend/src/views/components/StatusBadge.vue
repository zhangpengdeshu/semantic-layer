<template>
  <el-tag :type="tagType" size="small" effect="plain">{{ label }}</el-tag>
</template>

<script lang="ts">
const STATUS_MAP: Record<string, { type: string; label: string }> = {
  draft: { type: 'info', label: '草稿' },
  certified: { type: 'success', label: '已认证' },
  deprecated: { type: 'info', label: '已废弃' },
  unbound: { type: 'warning', label: '待绑定' },
  partial: { type: 'warning', label: '部分映射' },
  ready: { type: 'success', label: '可问数' },
  drifted: { type: 'danger', label: '已漂移' },
  pending: { type: 'warning', label: '待处理' },
  approved: { type: 'success', label: '已通过' },
  rejected: { type: 'danger', label: '已驳回' },
  passed: { type: 'success', label: '通过' },
  failed: { type: 'danger', label: '未通过' },
  ok: { type: 'success', label: '成功' },
  clarification: { type: 'warning', label: '需要澄清' },
  error: { type: 'danger', label: '错误' },
  warning: { type: 'warning', label: '警告' },
  info: { type: 'info', label: '提示' },
  active: { type: 'success', label: '启用' },
}

export default {
  name: 'SemanticStatusBadge',
  props: {
    status: { type: String, default: '' },
    text: { type: String, default: '' },
  },
  computed: {
    meta(): { type: string; label: string } {
      return STATUS_MAP[this.status] || { type: 'info', label: this.status || '-' }
    },
    tagType(): string {
      return this.meta.type
    },
    label(): string {
      return this.text || this.meta.label
    },
  },
}
</script>