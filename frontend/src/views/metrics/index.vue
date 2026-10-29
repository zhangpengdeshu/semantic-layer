<template>
  <div class="semantic-page">
    <div class="semantic-page__header">
      <div>
        <h2 class="semantic-page__title">指标管理</h2>
        <p class="semantic-page__subtitle">维护原子、比率、派生、累计与转化指标的口径与依赖关系</p>
      </div>
      <div class="semantic-page__actions">
        <el-button :loading="loading" @click="load">刷新</el-button>
        <el-button type="primary" @click="openCreate">新建指标</el-button>
      </div>
    </div>

    <div class="filter-bar">
      <el-input v-model.trim="filters.q" placeholder="搜索指标名称 / 业务名" clearable class="filter-item filter-item--md"
        @keyup.enter="load" @clear="load" />
      <el-select v-model="filters.metric_type" placeholder="全部类型" clearable class="filter-item filter-item--sm"
        @change="load">
        <el-option v-for="(label, value) in typeLabels" :key="value" :label="label" :value="value" />
      </el-select>
      <el-select v-model="filters.status" placeholder="全部状态" clearable class="filter-item filter-item--sm"
        @change="load">
        <el-option label="草稿" value="draft" />
        <el-option label="已认证" value="certified" />
        <el-option label="已废弃" value="deprecated" />
      </el-select>
      <el-button type="primary" @click="load">查询</el-button>
    </div>

    <el-alert v-if="error" type="error" show-icon :title="error" @close="error = ''" />

    <div class="table-card">
      <div class="table-card__header">
        <span class="table-card__title">指标列表</span>
        <span class="muted-text">共 {{ total }} 个</span>
      </div>
      <div class="table-card__body">
        <el-table v-loading="loading" :data="items" size="small" empty-text="暂无指标">
          <el-table-column label="指标" min-width="160" show-overflow-tooltip>
            <template #default="{ row }">
              <div>{{ row.business_name || row.name }}</div>
              <div class="mono-text muted-text">{{ row.name }}</div>
            </template>
          </el-table-column>
          <el-table-column label="类型" width="120">
            <template #default="{ row }">
              <el-tag size="small" effect="plain">{{ typeLabel(row.metric_type) }}</el-tag>
            </template>
          </el-table-column>
          <el-table-column prop="model_name" label="归属模型" min-width="130" show-overflow-tooltip />
          <el-table-column prop="unit" label="单位" width="90" />
          <el-table-column prop="owner" label="负责人" width="110" />
          <el-table-column label="状态" width="110">
            <template #default="{ row }">
              <StatusBadge :status="row.status" />
            </template>
          </el-table-column>
          <el-table-column label="操作" width="220" fixed="right">
            <template #default="{ row }">
              <el-button link @click="openEdit(row)">编辑</el-button>
              <el-button link @click="handleValidate(row)">校验</el-button>
              <el-button link @click="handleGraph(row)">依赖</el-button>
              <el-button link class="danger-text" @click="handleDelete(row)">删除</el-button>
            </template>
          </el-table-column>
        </el-table>
      </div>
      <div class="table-card__footer">
        <el-pagination background v-model:current-page="page" :page-size="pageSize" :page-sizes="[10, 20, 50]"
          :total="total" layout="total, sizes, prev, pager, next" @size-change="handleSizeChange"
          @current-change="load" />
      </div>
    </div>

    <el-dialog :title="form.metric_id ? '编辑指标' : '新建指标'" v-model="dialogVisible" width="720px">
      <el-form label-width="100px">
        <el-form-item label="名称" required><el-input v-model.trim="form.name" placeholder="gmv" /></el-form-item>
        <el-form-item label="业务名"><el-input v-model.trim="form.business_name" placeholder="GMV" /></el-form-item>
        <el-form-item label="类型">
          <el-select v-model="form.metric_type" class="form-block" @change="handleTypeChange">
            <el-option v-for="(label, value) in typeLabels" :key="value" :label="label" :value="value" />
          </el-select>
        </el-form-item>
        <el-form-item label="归属模型">
          <el-select v-model="form.model_id" filterable clearable class="form-block" @change="loadMeasures">
            <el-option v-for="item in models" :key="item.model_id" :label="item.business_name || item.name"
              :value="item.model_id" />
          </el-select>
        </el-form-item>
        <el-form-item label="口径定义"><el-input v-model.trim="form.definition" type="textarea" :rows="2"
            placeholder="业务定义或派生表达式" /></el-form-item>
        <el-form-item label="过滤条件"><el-input v-model.trim="form.filter"
            placeholder="status in ('paid')" /></el-form-item>
        <el-form-item label="单位"><el-input v-model.trim="form.unit" placeholder="CNY / % / 单" /></el-form-item>
        <el-form-item v-if="form.metric_type === 'cumulative'" label="累计窗口">
          <el-select v-model="form.window_spec" clearable filterable allow-create default-first-option
            class="form-block" placeholder="留空表示累计至今">
            <el-option label="累计至今" value="" />
            <el-option label="近 7 天" value="7 day" />
            <el-option label="近 30 天" value="30 day" />
            <el-option label="近 90 天" value="90 day" />
            <el-option label="近 12 个月" value="12 month" />
          </el-select>
        </el-form-item>
        <el-form-item v-if="form.metric_type === 'cumulative'" label="累计起始">
          <el-select v-model="form.grain_to_date" clearable class="form-block" placeholder="可选，按周期重置">
            <el-option label="month（月初至今）" value="month" />
            <el-option label="quarter（季初至今）" value="quarter" />
            <el-option label="year（年初至今）" value="year" />
          </el-select>
        </el-form-item>
        <el-form-item label="同义词">
          <el-select v-model="form.synonyms" multiple filterable allow-create default-first-option class="form-block">
            <el-option v-for="item in synonymOptions" :key="item" :label="item" :value="item" />
          </el-select>
        </el-form-item>

        <el-form-item label="指标输入">
          <div class="input-list">
            <div v-for="(item, index) in form.inputs" :key="index" class="input-row">
              <el-select v-model="item.input_type" class="input-row__type">
                <el-option label="度量" value="measure" />
                <el-option label="指标" value="metric" />
              </el-select>
              <el-select v-model="item.role" class="input-row__role">
                <el-option label="输入" value="input" />
                <el-option label="分子" value="numerator" />
                <el-option label="分母" value="denominator" />
                <el-option label="基线" value="base" />
                <el-option label="转化" value="conversion" />
              </el-select>
              <el-select v-model="item.input_ref" filterable class="input-row__ref" placeholder="选择输入">
                <el-option v-for="opt in inputOptions(item.input_type)" :key="opt.value" :label="opt.label"
                  :value="opt.value" />
              </el-select>
              <el-button link class="danger-text" @click="form.inputs.splice(index, 1)">删除</el-button>
            </div>
            <el-button size="small" @click="addInput">添加输入</el-button>
          </div>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="saving" @click="handleSave">保存</el-button>
      </template>
    </el-dialog>

    <el-dialog title="指标校验结果" v-model="validationVisible" width="620px">
      <ValidationPanel :issues="validation.issues || []" :loading="validating" />
    </el-dialog>

    <el-dialog title="指标依赖" v-model="graphVisible" width="620px">
      <div v-if="graph.nodes && graph.nodes.length" class="graph-list">
        <div v-for="node in graph.nodes" :key="node.metric_id" class="graph-node">
          <span class="mono-text">{{ node.name }}</span>
          <span class="muted-text">{{ node.metric_type }}</span>
        </div>
      </div>
      <div v-else class="muted-text">没有依赖</div>
      <div v-if="graph.edges && graph.edges.length" class="section">
        <div class="section__header"><span>引用关系</span></div>
        <div v-for="(edge, index) in graph.edges" :key="index" class="muted-text">
          {{ edge.from }} → {{ edge.to }} ({{ edge.role }})
        </div>
      </div>
    </el-dialog>
  </div>
</template>

<script lang="ts">
/* eslint-disable camelcase */
import {
  listMetrics,
  listMeasures,
  listSynonyms,
  createMetric,
  updateMetric,
  deleteMetric,
  validateMetric,
  metricDependencyGraph,
} from '@/api/semantic'
import { useSemanticStore } from '@/stores/semantic'
import StatusBadge from '../components/StatusBadge.vue'
import ValidationPanel from '../components/ValidationPanel.vue'

export default {
  name: 'SemanticMetrics',
  components: { StatusBadge, ValidationPanel },
  data(): any {
    return {
      loading: false,
      saving: false,
      validating: false,
      error: '',
      items: [],
      models: [],
      measures: [],
      allMetrics: [],
      synonymOptions: [],
      total: 0,
      page: 1,
      pageSize: 20,
      filters: { q: '', metric_type: '', status: '' },
      typeLabels: {
        simple: '原子指标',
        ratio: '比率指标',
        derived: '派生指标',
        cumulative: '累计指标',
        conversion: '转化指标',
      },
      dialogVisible: false,
      validationVisible: false,
      graphVisible: false,
      validation: {},
      graph: {},
      form: this.emptyForm(),
    }
  },
  created() {
    this.loadModels()
    this.loadAllMetrics()
    this.loadSynonymOptions()
    this.load()
  },
  methods: {
    emptyForm() {
      return {
        metric_id: null,
        model_id: null,
        name: '',
        business_name: '',
        metric_type: 'simple',
        definition: '',
        filter: '',
        unit: '',
        window_spec: null,
        grain_to_date: null,
        synonyms: [],
        inputs: [{ input_type: 'measure', input_ref: null, role: 'input' }],
      }
    },
    async loadModels() {
      try {
        this.models = await useSemanticStore().fetchModels()
      } catch (error) {
        // ignore
      }
    },
    async loadAllMetrics() {
      try {
        const data = await listMetrics({ page: 1, page_size: 200 })
        this.allMetrics = data.items || []
      } catch (error) {
        // ignore
      }
    },
    async loadSynonymOptions() {
      try {
        const items = (await listSynonyms()) || []
        this.synonymOptions = Array.from(new Set(items.map(item => item.synonym).filter(Boolean)))
      } catch (error) {
        this.synonymOptions = []
      }
    },
    async loadMeasures() {
      this.measures = []
      if (!this.form.model_id) return
      try {
        this.measures = await listMeasures(this.form.model_id)
      } catch (error) {
        this.measures = []
      }
    },
    async load() {
      this.loading = true
      this.error = ''
      try {
        const data = await listMetrics({
          q: this.filters.q,
          metric_type: this.filters.metric_type || undefined,
          status: this.filters.status || undefined,
          page: this.page,
          page_size: this.pageSize,
        })
        this.items = data.items || []
        this.total = data.total || 0
      } catch (error) {
        this.error = (error && error.message) || '加载指标失败'
      } finally {
        this.loading = false
      }
    },
    handleSizeChange(size) {
      this.pageSize = size
      this.page = 1
      this.load()
    },
    inputOptions(type) {
      if (type === 'measure') {
        return (this.measures || []).map(item => ({ value: item.measure_id, label: item.business_name || item.name }))
      }
      return (this.allMetrics || [])
        .filter(item => !this.form.metric_id || item.metric_id !== this.form.metric_id)
        .map(item => ({ value: item.metric_id, label: item.business_name || item.name }))
    },
    addInput() {
      this.form.inputs.push({ input_type: 'measure', input_ref: null, role: 'input' })
    },
    typeLabel(type) {
      return this.typeLabels[type] || type || '-'
    },
    handleTypeChange(type) {
      if (type === 'ratio') {
        this.form.inputs = [
          { input_type: 'metric', input_ref: null, role: 'numerator' },
          { input_type: 'metric', input_ref: null, role: 'denominator' },
        ]
      } else if (type === 'conversion') {
        this.form.inputs = [
          { input_type: 'metric', input_ref: null, role: 'base' },
          { input_type: 'metric', input_ref: null, role: 'conversion' },
        ]
      } else if (type === 'simple' || type === 'cumulative') {
        this.form.inputs = [{ input_type: 'measure', input_ref: null, role: 'input' }]
      }
    },
    openCreate() {
      this.form = this.emptyForm()
      this.dialogVisible = true
    },
    async openEdit(row) {
      this.form = {
        metric_id: row.metric_id,
        model_id: row.model_id,
        name: row.name,
        business_name: row.business_name,
        metric_type: row.metric_type,
        definition: row.definition,
        filter: row.filter,
        unit: row.unit,
        window_spec: row.window_spec || null,
        grain_to_date: row.grain_to_date || null,
        synonyms: row.synonyms || [],
        inputs: (row.inputs || []).map(item => ({
          input_type: item.input_type,
          input_ref: item.input_ref,
          role: item.role,
        })),
      }
      await this.loadMeasures()
      this.dialogVisible = true
    },
    async handleSave() {
      if (!this.form.name) return this.$message.warning('指标名称不能为空')
      this.saving = true
      try {
        const payload = { ...this.form }
        delete payload.metric_id
        if (payload.metric_type !== 'cumulative') {
          delete payload.window_spec
          delete payload.grain_to_date
        } else {
          payload.window_spec = payload.window_spec || null
          payload.grain_to_date = payload.grain_to_date || null
        }
        if (this.form.metric_id) await updateMetric(this.form.metric_id, payload)
        else await createMetric(payload)
        this.dialogVisible = false
        this.$message.success('保存成功')
        this.load()
        this.loadAllMetrics()
      } catch (error) {
        this.$message.error((error && error.message) || '保存失败')
      } finally {
        this.saving = false
      }
    },
    async handleDelete(row) {
      try {
        await this.$confirm(`删除指标「${row.name}」？`, '提示', { type: 'warning' })
        await deleteMetric(row.metric_id)
        this.load()
        this.loadAllMetrics()
      } catch (error) {
        if (error !== 'cancel') this.$message.error((error && error.message) || '删除失败')
      }
    },
    async handleValidate(row) {
      this.validating = true
      this.validationVisible = true
      try {
        this.validation = await validateMetric(row.metric_id)
      } catch (error) {
        this.$message.error((error && error.message) || '校验失败')
      } finally {
        this.validating = false
      }
    },
    async handleGraph(row) {
      try {
        this.graph = await metricDependencyGraph(row.metric_id)
        this.graphVisible = true
      } catch (error) {
        this.$message.error('加载依赖失败')
      }
    },
  },
}
</script>

<style scoped>
.input-list {
  width: 100%;
}

.input-row {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 8px;
}

.input-row__type {
  width: 110px;
}

.input-row__role {
  width: 110px;
}

.input-row__ref {
  flex: 1;
}

.graph-list {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.graph-node {
  display: flex;
  justify-content: space-between;
  border: 1px solid #ebeef5;
  border-radius: 4px;
  padding: 8px 10px;
}

.section {
  margin-top: 16px;
}

.section__header {
  font-weight: 600;
  margin-bottom: 8px;
}

.muted-text {
  color: #909399;
  font-size: 13px;
}
</style>