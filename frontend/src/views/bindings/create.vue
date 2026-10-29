<template>
  <div class="semantic-page">
    <div class="semantic-page__header">
      <div>
        <h2 class="semantic-page__title">新建数据绑定</h2>
        <p class="semantic-page__subtitle">绑定是语义模型到数据集/表/视图的物化映射</p>
      </div>
      <el-button @click="goBack">返回</el-button>
    </div>

    <el-alert v-if="error" type="error" show-icon :title="error" @close="error = ''" />

    <div class="form-card">
      <el-form label-width="120px">
        <el-form-item label="语义模型" required>
          <el-select v-model="form.model_id" filterable class="form-block" @change="loadModels">
            <el-option v-for="item in models" :key="item.model_id" :label="item.business_name || item.name"
              :value="item.model_id" />
          </el-select>
        </el-form-item>
        <el-form-item label="绑定类型">
          <el-select v-model="form.binding_type" class="form-block">
            <el-option label="dataset" value="dataset" />
            <el-option label="table" value="table" />
            <el-option label="view" value="view" />
            <el-option label="subquery" value="subquery" />
          </el-select>
        </el-form-item>
        <el-form-item v-if="form.binding_type === 'dataset'" label="数据集">
          <el-select v-model="form.dataset_id" filterable class="form-block" placeholder="从目录选择数据集"
            @change="handleDatasetChange">
            <el-option v-for="item in datasets" :key="item.dataset_id" :label="item.dataset_name || item.dataset_code"
              :value="item.dataset_id" />
          </el-select>
        </el-form-item>
        <el-form-item label="查询引用" required>
          <el-input v-model.trim="form.query_ref" placeholder="dataset.ds_order_detail" />
          <div class="muted-text">问数时使用的物理表/视图/子查询引用</div>
        </el-form-item>
        <el-form-item label="来源系统">
          <el-input v-model.trim="form.source_system" placeholder="chatbi_dataset" />
        </el-form-item>
        <el-form-item label="数据集 ID">
          <el-input v-model.trim="form.external_dataset_id" />
        </el-form-item>
        <el-form-item label="主绑定">
          <el-switch v-model="form.is_primary" />
          <span class="muted-text form-hint">同一模型只允许一个主绑定</span>
        </el-form-item>
        <el-form-item label="行过滤">
          <el-input v-model.trim="form.row_filter" placeholder="可选，例如 is_deleted = 0" />
        </el-form-item>
      </el-form>
      <div class="form-footer">
        <el-button @click="goBack">取消</el-button>
        <el-button type="primary" :loading="saving" @click="handleSave">创建并去映射</el-button>
      </div>
    </div>
  </div>
</template>

<script lang="ts">
/* eslint-disable camelcase */
import { listModels, listDatasets, createBinding } from '@/api/semantic'

export default {
  name: 'SemanticBindingCreate',
  data(): any {
    return {
      saving: false,
      error: '',
      models: [],
      datasets: [],
      form: {
        model_id: null,
        binding_type: 'dataset',
        dataset_id: null,
        query_ref: '',
        source_system: 'chatbi_dataset',
        external_dataset_id: '',
        is_primary: false,
        row_filter: '',
      },
    }
  },
  created() {
    const modelId = Number(this.$route.query.model_id)
    if (modelId) this.form.model_id = modelId
    this.loadModels()
    this.loadDatasets()
  },
  methods: {
    async loadModels() {
      try {
        const data = await listModels({ page: 1, page_size: 200 })
        this.models = data.items || []
      } catch (error) {
        this.error = (error && error.message) || '加载模型失败'
      }
    },
    async loadDatasets() {
      try {
        const data = await listDatasets({ page: 1, page_size: 200 })
        this.datasets = data.items || []
      } catch (error) {
        // ignore
      }
    },
    handleDatasetChange(datasetId) {
      const dataset = this.datasets.find(item => item.dataset_id === datasetId)
      if (!dataset) return
      this.form.source_system = dataset.source_system
      this.form.external_dataset_id = dataset.external_dataset_id
      this.form.query_ref = dataset.schema_name && dataset.table_name
        ? `${dataset.schema_name}.${dataset.table_name}`
        : (dataset.table_name || dataset.dataset_code || '')
    },
    async handleSave() {
      if (!this.form.model_id || !this.form.query_ref) {
        return this.$message.warning('模型和查询引用必填')
      }
      this.saving = true
      try {
        const payload = { ...this.form, status: 'draft' }
        delete payload.dataset_id
        const binding = await createBinding(this.form.model_id, payload)
        this.$message.success('绑定已创建')
        this.$router.push(`/bindings/${binding.binding_id}/mapping`)
      } catch (error) {
        this.error = (error && error.message) || '创建绑定失败'
      } finally {
        this.saving = false
      }
    },
    goBack() {
      this.$router.push({ path: '/bindings', query: this.form.model_id ? { model_id: this.form.model_id } : {} })
    },
  },
}
</script>

<style scoped>
.semantic-page {
  padding: 16px;
}

.semantic-page__header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  margin-bottom: 16px;
}

.semantic-page__title {
  margin: 0;
  font-size: 20px;
  font-weight: 600;
  color: #303133;
}

.semantic-page__subtitle {
  margin: 6px 0 0;
  color: #909399;
  font-size: 13px;
}

.form-card {
  background: #fff;
  border: 1px solid #ebeef5;
  border-radius: 6px;
  padding: 20px;
  max-width: 760px;
}

.form-block {
  width: 100%;
}

.form-footer {
  display: flex;
  justify-content: flex-end;
  gap: 8px;
  padding-top: 16px;
  border-top: 1px solid #ebeef5;
}

.muted-text {
  color: #909399;
  font-size: 12px;
}

.form-hint {
  margin-left: 8px;
}
</style>