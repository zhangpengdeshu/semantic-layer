<template>
  <div v-loading="loading" class="semantic-page">
    <div class="semantic-page__header">
      <div>
        <h2 class="semantic-page__title">字段映射</h2>
        <p class="semantic-page__subtitle">
          <span class="mono-text">{{ binding.query_ref }}</span>
          <span class="dot">·</span>
          <StatusBadge :status="binding.status" />
          <span class="dot">·</span>
          覆盖率 {{ Math.round((coverage || 0) * 100) }}%
        </p>
      </div>
      <div class="header-actions">
        <el-button @click="$router.push({ path: '/bindings', query: { model_id: binding.model_id } })">返回绑定</el-button>
        <el-button :loading="saving" @click="handleAutoMap">自动映射</el-button>
        <el-button :loading="saving" type="primary" @click="handleSave">保存映射</el-button>
        <el-button @click="handleCertify">认证绑定</el-button>
      </div>
    </div>

    <el-alert v-if="error" type="error" show-icon :title="error" @close="error = ''" />
    <el-alert v-if="drift.drifted" type="warning" show-icon :closable="false"
      :title="`检测到漂移：缺失 ${(drift.missing || []).length} 个列，类型不一致 ${(drift.type_mismatch || []).length} 个`" />

    <div class="table-card">
      <div class="table-card__body">
        <el-table :data="items" size="small" border max-height="560">
          <el-table-column prop="field_name" label="语义字段" min-width="150">
            <template #default="{ row }">
              <div>{{ row.field_name }}</div>
              <div class="muted-text">{{ row.business_name }}</div>
            </template>
          </el-table-column>
          <el-table-column prop="semantic_type" label="角色" width="100" />
          <el-table-column prop="data_type" label="类型" width="90" />
          <el-table-column label="物理列" min-width="200">
            <template #default="{ row }">
              <el-select v-model="row.column_name" filterable clearable allow-create default-first-option size="small"
                placeholder="选择或输入物理列" class="form-block">
                <el-option v-for="col in columns" :key="col.column_name"
                  :label="`${col.column_name} (${col.column_type || ''})`" :value="col.column_name" />
              </el-select>
            </template>
          </el-table-column>
          <el-table-column label="转换表达式" min-width="180">
            <template #default="{ row }">
              <el-input v-model.trim="row.transform" size="small" placeholder="CAST({col} AS DATE)" />
            </template>
          </el-table-column>
          <el-table-column label="状态" width="110">
            <template #default="{ row }">
              <StatusBadge :status="row.status === 'unmapped' ? 'unbound' : row.status" />
            </template>
          </el-table-column>
        </el-table>
      </div>
    </div>
  </div>
</template>

<script lang="ts">
/* eslint-disable camelcase */
import {
  getFieldMappings,
  bindingColumns,
  saveFieldMappings,
  autoMapBinding,
  bindingDrift,
  createCertification,
} from '@/api/semantic'
import StatusBadge from '../components/StatusBadge.vue'

export default {
  name: 'SemanticBindingMapping',
  components: { StatusBadge },
  data(): any {
    return {
      loading: false,
      saving: false,
      error: '',
      binding: {},
      items: [],
      columns: [],
      coverage: 0,
      drift: {},
    }
  },
  computed: {
    bindingId() {
      return Number(this.$route.params.id)
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
        const data = await getFieldMappings(this.bindingId)
        this.binding = data.binding || {}
        this.items = (data.items || []).map(item => ({
          ...item,
          column_name: item.column_name || '',
          transform: item.transform || '',
        }))
        this.coverage = data.coverage || 0
        this.columns = await bindingColumns(this.bindingId)
        this.drift = await bindingDrift(this.bindingId)
      } catch (error) {
        this.error = (error && error.message) || '加载字段映射失败'
      } finally {
        this.loading = false
      }
    },
    async handleAutoMap() {
      this.saving = true
      try {
        const result = await autoMapBinding(this.bindingId)
        this.$message.success(`自动映射 ${result.mapped || 0} 个字段`)
        this.load()
      } catch (error) {
        this.$message.error((error && error.message) || '自动映射失败')
      } finally {
        this.saving = false
      }
    },
    async handleSave() {
      const payload = this.items
        .filter(item => item.column_name)
        .map(item => ({
          field_id: item.field_id,
          column_name: item.column_name,
          transform: item.transform || null,
          status: 'draft',
        }))
      if (!payload.length) return this.$message.warning('至少映射一个字段')
      this.saving = true
      try {
        await saveFieldMappings(this.bindingId, payload)
        this.$message.success('映射已保存')
        this.load()
      } catch (error) {
        this.$message.error((error && error.message) || '保存失败')
      } finally {
        this.saving = false
      }
    },
    async handleCertify() {
      try {
        await this.$confirm('提交绑定认证？认证后主绑定才参与问数。', '提示', { type: 'warning' })
        await createCertification({ asset_type: 'binding', asset_id: this.bindingId })
        this.$message.success('已提交认证')
      } catch (error) {
        if (error !== 'cancel') this.$message.error((error && error.message) || '提交失败')
      }
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

.dot {
  margin: 0 6px;
}

.header-actions {
  display: flex;
  gap: 8px;
}

.form-block {
  width: 100%;
}

.muted-text {
  color: #909399;
  font-size: 12px;
}
</style>