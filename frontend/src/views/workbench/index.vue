<template>
  <div class="semantic-page">
    <div class="semantic-page__header">
      <div>
        <h2 class="semantic-page__title">{{ $t('semanticLayer.workbench') }}</h2>
        <p class="semantic-page__subtitle">语义资产健康度、待办与最近问数</p>
      </div>
      <el-button :loading="loading" @click="load">刷新</el-button>
    </div>

    <el-alert v-if="error" type="error" show-icon :title="error" @close="error = ''" />

    <div v-loading="loading" class="stat-grid">
      <div v-for="item in statCards" :key="item.key" class="stat-card">
        <div class="stat-card__label">{{ item.label }}</div>
        <div class="stat-card__value">{{ item.value }}</div>
        <div class="stat-card__hint">{{ item.hint }}</div>
      </div>
    </div>

    <el-row :gutter="16" class="workbench-row">
      <el-col :span="12">
        <div class="panel">
          <div class="panel__header">
            <span>{{ $t('semanticLayer.recentModels') }}</span>
            <el-button link size="small" @click="$router.push('/models')">查看全部</el-button>
          </div>
          <el-table :data="recentModels" size="small" empty-text="暂无模型">
            <el-table-column label="模型" min-width="160">
              <template #default="{ row }">
                <span class="link-text" @click="openModel(row)">{{ row.business_name || row.name }}</span>
              </template>
            </el-table-column>
            <el-table-column prop="domain_name" label="主题域" width="110" />
            <el-table-column label="状态" width="100">
              <template #default="{ row }">
                <StatusBadge :status="row.status" />
              </template>
            </el-table-column>
          </el-table>
        </div>
      </el-col>
      <el-col :span="12">
        <div class="panel">
          <div class="panel__header">
            <span>{{ $t('semanticLayer.pending') }}</span>
            <el-button link size="small" @click="$router.push('/release')">认证工作台</el-button>
          </div>
          <el-table :data="pending" size="small" empty-text="暂无待办">
            <el-table-column prop="asset_type" label="类型" width="90" />
            <el-table-column prop="asset_id" label="资产 ID" width="90" />
            <el-table-column prop="requested_by" label="申请人" width="110" />
            <el-table-column label="状态" width="100">
              <template #default="{ row }">
                <StatusBadge :status="row.status" />
              </template>
            </el-table-column>
          </el-table>
        </div>
      </el-col>
    </el-row>

    <div class="panel">
      <div class="panel__header">
        <span>{{ $t('semanticLayer.recentQueries') }}</span>
        <el-button link size="small" @click="$router.push('/admin')">查看审计</el-button>
      </div>
      <el-table :data="recentQueries" size="small" empty-text="暂无问数记录">
        <el-table-column prop="question" label="问题" min-width="260" show-overflow-tooltip />
        <el-table-column prop="row_count" label="行数" width="90" />
        <el-table-column prop="elapsed_ms" label="耗时(ms)" width="100" />
        <el-table-column label="状态" width="100">
          <template #default="{ row }">
            <StatusBadge :status="row.status" />
          </template>
        </el-table-column>
        <el-table-column prop="created_at" label="时间" width="180" />
      </el-table>
    </div>
  </div>
</template>

<script lang="ts">
import { workbench } from '@/api/semantic'
import StatusBadge from '../components/StatusBadge.vue'

export default {
  name: 'SemanticWorkbench',
  components: { StatusBadge },
  data(): any {
    return {
      loading: false,
      error: '',
      stats: {},
      recentModels: [],
      pending: [],
      recentQueries: [],
    }
  },
  computed: {
    statCards() {
      const stats = this.stats || {}
      return [
        { key: 'models', label: '语义模型', value: stats.models || 0, hint: `${stats.certified_models || 0} 个已认证` },
        { key: 'metrics', label: '指标', value: stats.metrics || 0, hint: '含外部口径落地' },
        { key: 'unbound', label: '待绑定模型', value: stats.unbound_models || 0, hint: '无认证主绑定' },
        { key: 'pending', label: '待认证', value: stats.pending_certifications || 0, hint: '需要评审' },
        { key: 'queries', label: '24h 问数', value: stats.queries_24h || 0, hint: '语义链路请求' },
        { key: 'failed', label: '24h 校验失败', value: stats.failed_validations_24h || 0, hint: '需关注' },
      ]
    },
  },
  created() {
    this.load()
  },
  methods: {
    async load() {
      this.loading = true
      this.error = ''
      try {
        const data = await workbench()
        this.stats = data.stats || {}
        this.recentModels = data.recent_models || []
        this.pending = data.pending_certifications || []
        this.recentQueries = data.recent_queries || []
      } catch (error) {
        this.error = (error && error.message) || '加载工作台失败'
      } finally {
        this.loading = false
      }
    },
    openModel(row) {
      this.$router.push(`/models/${row.model_id}`)
    },
  },
}
</script>

<style scoped>
.semantic-page { padding: 16px; }
.semantic-page__header { display: flex; align-items: flex-start; justify-content: space-between; margin-bottom: 16px; }
.semantic-page__title { margin: 0; font-size: 20px; font-weight: 600; color: #303133; }
.semantic-page__subtitle { margin: 6px 0 0; color: #909399; font-size: 13px; }
.stat-grid { display: grid; grid-template-columns: repeat(6, minmax(0, 1fr)); gap: 12px; margin-bottom: 16px; }
.stat-card { background: #fff; border: 1px solid #ebeef5; border-radius: 6px; padding: 14px 16px; }
.stat-card__label { color: #909399; font-size: 13px; }
.stat-card__value { margin-top: 6px; font-size: 26px; font-weight: 600; color: #303133; }
.stat-card__hint { margin-top: 4px; color: #c0c4cc; font-size: 12px; }
.workbench-row { margin-bottom: 16px; }
.panel { background: #fff; border: 1px solid #ebeef5; border-radius: 6px; margin-bottom: 16px; }
.panel__header { display: flex; align-items: center; justify-content: space-between; padding: 12px 16px; border-bottom: 1px solid #ebeef5; font-weight: 600; color: #303133; }
.link-text { color: #409eff; cursor: pointer; }
@media (max-width: 1200px) {
  .stat-grid { grid-template-columns: repeat(3, minmax(0, 1fr)); }
}
</style>
