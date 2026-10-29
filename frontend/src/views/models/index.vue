<template>
  <div class="semantic-page">
    <div class="semantic-page__header">
      <div>
        <h2 class="semantic-page__title">语义模型</h2>
        <p class="semantic-page__subtitle">语义模型是问数口径的载体，覆盖率反映字段与物理表的绑定完成度</p>
      </div>
      <div class="semantic-page__actions">
        <el-button :loading="loading" @click="load">刷新</el-button>
        <el-button type="primary" @click="$router.push('/models/create')">新建模型</el-button>
      </div>
    </div>

    <div class="filter-bar">
      <el-input
        v-model.trim="filters.q" placeholder="搜索模型名称 / 业务名" clearable class="filter-item filter-item--md"
        @keyup.enter="load" @clear="load" />
      <el-select
        v-model="filters.domain_id" placeholder="全部主题域" clearable class="filter-item filter-item--sm"
        @change="load">
        <el-option v-for="item in domains" :key="item.domain_id" :label="item.name" :value="item.domain_id" />
      </el-select>
      <el-select v-model="filters.status" placeholder="全部状态" clearable class="filter-item filter-item--sm" @change="load">
        <el-option label="草稿" value="draft" />
        <el-option label="已认证" value="certified" />
        <el-option label="已废弃" value="deprecated" />
      </el-select>
      <el-select v-model="filters.queryable" placeholder="可问数" clearable class="filter-item filter-item--sm" @change="load">
        <el-option label="可问数" :value="true" />
        <el-option label="不可问数" :value="false" />
      </el-select>
      <el-button type="primary" @click="load">查询</el-button>
    </div>

    <el-alert v-if="error" type="error" show-icon :title="error" @close="error = ''" />

    <div class="table-card">
      <div class="table-card__header">
        <span class="table-card__title">模型列表</span>
        <span class="muted-text">共 {{ total }} 个</span>
      </div>
      <div class="table-card__body">
        <el-table v-loading="loading" :data="items" size="small" row-key="model_id" empty-text="暂无语义模型">
          <el-table-column label="模型" min-width="180" show-overflow-tooltip>
            <template #default="{ row }">
              <span class="link-text" @click="openDetail(row)">{{ row.business_name || row.name }}</span>
              <div class="mono-text muted-text">{{ row.name }}</div>
            </template>
          </el-table-column>
          <el-table-column prop="domain_name" label="主题域" width="120" />
          <el-table-column label="粒度" min-width="140">
            <template #default="{ row }">
              <span class="mono-text">{{ grainText(row) }}</span>
            </template>
          </el-table-column>
          <el-table-column prop="field_total" label="字段" width="70" align="center" />
          <el-table-column label="覆盖率" width="140">
            <template #default="{ row }">
              <div class="coverage-cell">
                <el-progress :percentage="coveragePercent(row)" :stroke-width="6" :show-text="false" />
                <span class="coverage-cell__text">{{ coveragePercent(row) }}%</span>
              </div>
            </template>
          </el-table-column>
          <el-table-column label="状态" width="170">
            <template #default="{ row }">
              <StatusBadge :status="row.binding_status" />
              <StatusBadge v-if="row.queryable" status="ready" text="可问数" class="status-gap" />
            </template>
          </el-table-column>
          <el-table-column prop="owner" label="负责人" width="110" />
          <el-table-column label="操作" width="190" fixed="right">
            <template #default="{ row }">
              <el-button link @click="openDetail(row)">详情</el-button>
              <el-button link @click="handleValidate(row, 'semantic')">语义校验</el-button>
              <el-button link @click="handleValidate(row, 'queryable')">可问数校验</el-button>
            </template>
          </el-table-column>
        </el-table>
      </div>
      <div class="table-card__footer">
        <el-pagination
          background v-model:current-page="page" :page-size="pageSize" :page-sizes="[10, 20, 50]"
          :total="total" layout="total, sizes, prev, pager, next" @size-change="handleSizeChange" @current-change="load" />
      </div>
    </div>

    <el-dialog :title="validationTitle" v-model="validationVisible" width="620px">
      <ValidationPanel :issues="validation.issues || []" :loading="validating" show-run @run="runValidation" />
    </el-dialog>
  </div>
</template>

<script lang="ts">
/* eslint-disable camelcase */
import { listModels, listDomains, runModelValidation } from '@/api/semantic'
import StatusBadge from '../components/StatusBadge.vue'
import ValidationPanel from '../components/ValidationPanel.vue'

export default {
  name: 'SemanticModels',
  components: { StatusBadge, ValidationPanel },
  data(): any {
    return {
      loading: false,
      validating: false,
      error: '',
      items: [],
      domains: [],
      total: 0,
      page: 1,
      pageSize: 20,
      filters: { q: '', domain_id: null, status: '', queryable: null },
      validationVisible: false,
      validation: {},
      validationModelId: null,
      validationLevel: 'semantic',
    }
  },
  computed: {
    validationTitle() {
      return this.validationLevel === 'queryable' ? '可问数校验结果' : '语义校验结果'
    },
  },
  created() {
    this.loadDomains()
    this.load()
  },
  methods: {
    async loadDomains() {
      try {
        const data = await listDomains({ page: 1, page_size: 200 })
        this.domains = data.items || []
      } catch (error) {
        // 主题域加载失败不阻塞模型列表
      }
    },
    async load() {
      this.loading = true
      this.error = ''
      try {
        const data = await listModels({
          q: this.filters.q,
          domain_id: this.filters.domain_id || undefined,
          status: this.filters.status || undefined,
          queryable: this.filters.queryable === null ? undefined : this.filters.queryable,
          page: this.page,
          page_size: this.pageSize,
        })
        this.items = data.items || []
        this.total = data.total || 0
      } catch (error) {
        this.error = (error && error.message) || '加载模型失败'
      } finally {
        this.loading = false
      }
    },
    handleSizeChange(size) {
      this.pageSize = size
      this.page = 1
      this.load()
    },
    grainText(row) {
      if (row.grain_text) return row.grain_text
      const grain = row.grain || []
      if (Array.isArray(grain)) return grain.map(item => item.name).join(' + ') || '-'
      return grain || '-'
    },
    coveragePercent(row) {
      return Math.round((row.coverage || 0) * 100)
    },
    openDetail(row) {
      this.$router.push(`/models/${row.model_id}`)
    },
    handleValidate(row, level) {
      this.validationModelId = row.model_id
      this.validationLevel = level
      this.validation = {}
      this.validationVisible = true
      this.runValidation()
    },
    async runValidation() {
      if (!this.validationModelId) return
      this.validating = true
      try {
        this.validation = await runModelValidation(this.validationModelId, this.validationLevel)
        this.load()
      } catch (error) {
        this.$message.error((error && error.message) || '校验失败')
      } finally {
        this.validating = false
      }
    },
  },
}
</script>