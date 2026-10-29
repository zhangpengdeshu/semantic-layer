<template>
  <div class="semantic-page">
    <div class="semantic-page__header">
      <div>
        <h2 class="semantic-page__title">数据绑定</h2>
        <p class="semantic-page__subtitle">将语义模型映射到物理表，主绑定用于问数编译，可随时做漂移检查</p>
      </div>
      <div class="semantic-page__actions">
        <el-button :loading="loading" @click="loadBindings">刷新</el-button>
        <el-button type="primary" :disabled="!modelId" @click="openCreate">新建绑定</el-button>
      </div>
    </div>

    <div class="filter-bar">
      <el-select v-model="modelId" filterable placeholder="选择语义模型" class="filter-item filter-item--md" @change="loadBindings">
        <el-option v-for="item in models" :key="item.model_id" :label="item.business_name || item.name" :value="item.model_id" />
      </el-select>
    </div>

    <el-alert v-if="error" type="error" show-icon :title="error" @close="error = ''" />

    <div class="table-card">
      <div class="table-card__header">
        <span class="table-card__title">绑定列表</span>
        <span class="muted-text">共 {{ bindings.length }} 个绑定</span>
      </div>
      <div class="table-card__body">
        <el-table v-loading="loading" :data="bindings" size="small" empty-text="请选择模型或先创建绑定">
          <el-table-column prop="query_ref" label="查询引用" min-width="240" show-overflow-tooltip>
            <template #default="{ row }">
              <span class="mono-text">{{ row.query_ref }}</span>
            </template>
          </el-table-column>
          <el-table-column prop="binding_type" label="类型" width="100" />
          <el-table-column prop="source_system" label="来源系统" width="140" />
          <el-table-column label="覆盖率" width="150">
            <template #default="{ row }">
              <div class="coverage-cell">
                <el-progress :percentage="coveragePercent(row)" :stroke-width="6" :show-text="false" />
                <span class="coverage-cell__text">{{ coveragePercent(row) }}%</span>
              </div>
            </template>
          </el-table-column>
          <el-table-column label="状态" width="190">
            <template #default="{ row }">
              <StatusBadge :status="row.status" />
              <StatusBadge v-if="row.is_primary" status="ready" text="主绑定" class="status-gap" />
              <StatusBadge v-if="row.drifted" status="drifted" class="status-gap" />
            </template>
          </el-table-column>
          <el-table-column label="操作" width="260" fixed="right">
            <template #default="{ row }">
              <el-button link @click="openMapping(row)">字段映射</el-button>
              <el-button link @click="handleSetPrimary(row)">设为主绑定</el-button>
              <el-button link @click="handleDrift(row)">漂移检查</el-button>
            </template>
          </el-table-column>
        </el-table>
      </div>
    </div>

    <div class="panel">
      <div class="panel__header">
        <span>数据集目录（只读参考）</span>
        <el-button link size="small" @click="loadDatasets">刷新</el-button>
      </div>
      <el-table v-loading="datasetLoading" :data="datasets" size="small" empty-text="暂无数据集，请先同步目录">
        <el-table-column prop="dataset_name" label="数据集" min-width="180" show-overflow-tooltip />
        <el-table-column prop="dataset_code" label="编码" min-width="140" />
        <el-table-column prop="source_system" label="来源系统" width="150" />
        <el-table-column prop="table_name" label="表" min-width="160" show-overflow-tooltip />
        <el-table-column prop="column_count" label="字段数" width="90" align="center" />
        <el-table-column label="操作" width="100">
          <template #default="{ row }">
            <el-button link @click="openDataset(row)">查看字段</el-button>
          </template>
        </el-table-column>
      </el-table>
    </div>

    <el-dialog title="数据集字段" v-model="datasetVisible" width="720px">
      <div class="mono-text dataset-title">{{ dataset.dataset_name }}（{{ datasetRef(dataset) }}）</div>
      <el-table :data="dataset.columns || []" size="small" max-height="420">
        <el-table-column prop="column_name" label="物理列" min-width="160" />
        <el-table-column prop="column_type" label="类型" width="120" />
        <el-table-column prop="business_name" label="业务名" min-width="140" />
        <el-table-column prop="sample_value" label="样例值" min-width="140" />
        <el-table-column prop="ordinal" label="序号" width="70" />
      </el-table>
    </el-dialog>

    <el-dialog title="漂移检查" v-model="driftVisible" width="620px">
      <el-alert
        :type="drift.drifted ? 'warning' : 'success'" :closable="false" show-icon
        :title="drift.drifted ? '绑定与物理目录不一致' : '绑定与物理目录一致'" />
      <div v-if="(drift.missing || []).length" class="section">
        <div class="section__header">缺失列</div>
        <el-tag v-for="item in drift.missing" :key="item" type="danger" size="small" class="tag-gap">{{ item }}</el-tag>
      </div>
      <div v-if="(drift.type_mismatch || []).length" class="section">
        <div class="section__header">类型不一致</div>
        <div v-for="item in drift.type_mismatch" :key="item.field" class="muted-text">
          {{ item.field }}: {{ item.field_type }} → {{ item.column_type }}
        </div>
      </div>
      <div v-if="(drift.new_columns || []).length" class="section">
        <div class="section__header">新增列</div>
        <el-tag v-for="item in drift.new_columns" :key="item" size="small" class="tag-gap">{{ item }}</el-tag>
      </div>
    </el-dialog>
  </div>
</template>

<script lang="ts">
/* eslint-disable camelcase */
import {
  listModels,
  listBindings,
  setPrimaryBinding,
  bindingDrift,
  listDatasets,
  getDataset,
} from '@/api/semantic'
import StatusBadge from '../components/StatusBadge.vue'

export default {
  name: 'SemanticBindings',
  components: { StatusBadge },
  data(): any {
    return {
      loading: false,
      datasetLoading: false,
      error: '',
      models: [],
      modelId: null,
      bindings: [],
      datasets: [],
      datasetVisible: false,
      dataset: {},
      driftVisible: false,
      drift: {},
    }
  },
  created() {
    this.loadModels()
    this.loadDatasets()
    const queryModelId = Number(this.$route.query.model_id)
    if (queryModelId) this.modelId = queryModelId
  },
  methods: {
    async loadModels() {
      try {
        const data = await listModels({ page: 1, page_size: 200 })
        this.models = data.items || []
        if (!this.modelId && this.models.length) {
          this.modelId = this.models[0].model_id
          this.loadBindings()
        }
      } catch (error) {
        this.error = (error && error.message) || '加载模型失败'
      }
    },
    async loadBindings() {
      if (!this.modelId) return
      this.loading = true
      try {
        this.bindings = await listBindings(this.modelId)
      } catch (error) {
        this.error = (error && error.message) || '加载绑定失败'
      } finally {
        this.loading = false
      }
    },
    async loadDatasets() {
      this.datasetLoading = true
      try {
        const data = await listDatasets({ page: 1, page_size: 100 })
        this.datasets = data.items || []
      } catch (error) {
        // ignore
      } finally {
        this.datasetLoading = false
      }
    },
    openCreate() {
      this.$router.push({ path: '/bindings/create', query: { model_id: this.modelId } })
    },
    openMapping(row) {
      this.$router.push(`/bindings/${row.binding_id}/mapping`)
    },
    async handleSetPrimary(row) {
      try {
        await setPrimaryBinding(row.binding_id)
        this.$message.success('已设为主绑定')
        this.loadBindings()
      } catch (error) {
        this.$message.error((error && error.message) || '设置失败')
      }
    },
    async handleDrift(row) {
      try {
        this.drift = await bindingDrift(row.binding_id)
        this.driftVisible = true
      } catch (error) {
        this.$message.error('漂移检查失败')
      }
    },
    async openDataset(row) {
      try {
        this.dataset = await getDataset(row.dataset_id)
        this.datasetVisible = true
      } catch (error) {
        this.$message.error('加载数据集失败')
      }
    },
    datasetRef(dataset) {
      if (!dataset) return '-'
      if (dataset.schema_name && dataset.table_name) return `${dataset.schema_name}.${dataset.table_name}`
      return dataset.table_name || dataset.dataset_code || '-'
    },
    coveragePercent(row) {
      return Math.round((row.coverage || 0) * 100)
    },
  },
}
</script>

<style scoped>
.dataset-title {
  margin-bottom: 12px;
}
</style>