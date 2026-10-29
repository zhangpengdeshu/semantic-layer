<template>
  <div class="semantic-page">
    <div class="semantic-page__header">
      <div>
        <h2 class="semantic-page__title">新建语义模型</h2>
        <p class="semantic-page__subtitle">先定义业务语义，完成后再绑定数据集</p>
      </div>
      <el-button @click="$router.push('/models')">返回列表</el-button>
    </div>

    <el-alert v-if="error" type="error" show-icon :title="error" @close="error = ''" />

    <div class="wizard-card">
      <el-steps :active="step" finish-status="success" simple>
        <el-step title="基本信息" />
        <el-step title="字段" />
        <el-step title="粒度" />
        <el-step title="维度" />
        <el-step title="度量" />
        <el-step title="确认" />
      </el-steps>

      <div v-show="step === 0" class="wizard-body">
        <el-form label-width="100px">
          <el-form-item label="主题域" required>
            <el-select v-model="form.domain_id" filterable placeholder="选择主题域" class="form-block">
              <el-option v-for="item in domains" :key="item.domain_id" :label="item.name" :value="item.domain_id" />
            </el-select>
          </el-form-item>
          <el-form-item label="模型名" required>
            <el-input v-model.trim="form.name" placeholder="order" />
          </el-form-item>
          <el-form-item label="业务名">
            <el-input v-model.trim="form.business_name" placeholder="订单" />
          </el-form-item>
          <el-form-item label="描述">
            <el-input v-model.trim="form.description" type="textarea" :rows="3" />
          </el-form-item>
          <el-form-item label="负责人">
            <el-input v-model.trim="form.owner" />
          </el-form-item>
        </el-form>
      </div>

      <div v-show="step === 1" class="wizard-body">
        <div class="wizard-toolbar">
          <span class="muted-text">先定义业务需要的字段，不需要物理列</span>
          <el-button size="small" @click="addField">添加字段</el-button>
        </div>
        <el-table :data="fields" size="small" border>
          <el-table-column label="字段名" min-width="140">
            <template #default="{ row }">
              <el-input v-model.trim="row.name" size="small" placeholder="order_id" />
            </template>
          </el-table-column>
          <el-table-column label="业务名" min-width="130">
            <template #default="{ row }">
              <el-input v-model.trim="row.business_name" size="small" placeholder="订单号" />
            </template>
          </el-table-column>
          <el-table-column label="角色" width="120">
            <template #default="{ row }">
              <el-select v-model="row.semantic_type" size="small">
                <el-option label="key" value="key" />
                <el-option label="dimension" value="dimension" />
                <el-option label="time" value="time" />
                <el-option label="measure" value="measure" />
              </el-select>
            </template>
          </el-table-column>
          <el-table-column label="类型" width="110">
            <template #default="{ row }">
              <el-select v-model="row.data_type" size="small">
                <el-option label="string" value="string" />
                <el-option label="number" value="number" />
                <el-option label="date" value="date" />
                <el-option label="boolean" value="boolean" />
                <el-option label="unknown" value="unknown" />
              </el-select>
            </template>
          </el-table-column>
          <el-table-column label="操作" width="70">
            <template #default="{ $index }">
              <el-button link class="danger-text" @click="fields.splice($index, 1)">删除</el-button>
            </template>
          </el-table-column>
        </el-table>
      </div>

      <div v-show="step === 2" class="wizard-body">
        <el-form label-width="100px">
          <el-form-item label="粒度字段" required>
            <el-select v-model="form.grain" multiple filterable placeholder="选择粒度字段" class="form-block">
              <el-option v-for="item in fields" :key="item.name" :label="item.business_name || item.name"
                :value="item.name" />
            </el-select>
          </el-form-item>
        </el-form>
        <el-alert type="info" :closable="false" show-icon title="粒度决定了一行数据代表什么；必须显式声明，后续校验会检查。" />
      </div>

      <div v-show="step === 3" class="wizard-body">
        <div class="wizard-toolbar">
          <span class="muted-text">维度是可分组、可过滤的分析角度</span>
          <el-button size="small" @click="addDimension">添加维度</el-button>
        </div>
        <el-table :data="dimensions" size="small" border>
          <el-table-column label="维度名" min-width="140">
            <template #default="{ row }">
              <el-input v-model.trim="row.name" size="small" placeholder="渠道" />
            </template>
          </el-table-column>
          <el-table-column label="来源字段" min-width="160">
            <template #default="{ row }">
              <el-select v-model="row.field_name" size="small" filterable placeholder="选择字段">
                <el-option v-for="item in fields" :key="item.name" :label="item.business_name || item.name"
                  :value="item.name" />
              </el-select>
            </template>
          </el-table-column>
          <el-table-column label="类型" width="130">
            <template #default="{ row }">
              <el-select v-model="row.dimension_type" size="small">
                <el-option label="categorical" value="categorical" />
                <el-option label="time" value="time" />
              </el-select>
            </template>
          </el-table-column>
          <el-table-column label="操作" width="70">
            <template #default="{ $index }">
              <el-button link class="danger-text" @click="dimensions.splice($index, 1)">删除</el-button>
            </template>
          </el-table-column>
        </el-table>
      </div>

      <div v-show="step === 4" class="wizard-body">
        <div class="wizard-toolbar">
          <span class="muted-text">度量是内部聚合原料，指标会引用它</span>
          <el-button size="small" @click="addMeasure">添加度量</el-button>
        </div>
        <el-table :data="measures" size="small" border>
          <el-table-column label="度量名" min-width="150">
            <template #default="{ row }">
              <el-input v-model.trim="row.name" size="small" placeholder="order_amount_sum" />
            </template>
          </el-table-column>
          <el-table-column label="来源字段" min-width="150">
            <template #default="{ row }">
              <el-select v-model="row.field_name" size="small" filterable placeholder="选择字段">
                <el-option v-for="item in fields" :key="item.name" :label="item.business_name || item.name"
                  :value="item.name" />
              </el-select>
            </template>
          </el-table-column>
          <el-table-column label="聚合" width="130">
            <template #default="{ row }">
              <el-select v-model="row.agg" size="small">
                <el-option label="sum" value="sum" />
                <el-option label="count" value="count" />
                <el-option label="count_distinct" value="count_distinct" />
                <el-option label="avg" value="avg" />
                <el-option label="min" value="min" />
                <el-option label="max" value="max" />
              </el-select>
            </template>
          </el-table-column>
          <el-table-column label="可加性" width="140">
            <template #default="{ row }">
              <el-select v-model="row.additivity" size="small">
                <el-option label="additive" value="additive" />
                <el-option label="semi_additive" value="semi_additive" />
                <el-option label="non_additive" value="non_additive" />
              </el-select>
            </template>
          </el-table-column>
          <el-table-column label="操作" width="70">
            <template #default="{ $index }">
              <el-button link class="danger-text" @click="measures.splice($index, 1)">删除</el-button>
            </template>
          </el-table-column>
        </el-table>
      </div>

      <div v-show="step === 5" class="wizard-body">
        <div class="review-block">
          <div class="review-row"><span>模型</span><strong>{{ form.business_name || form.name }}</strong></div>
          <div class="review-row"><span>主题域</span><strong>{{ domainName }}</strong></div>
          <div class="review-row"><span>字段</span><strong>{{ fields.length }}</strong></div>
          <div class="review-row"><span>粒度</span><strong>{{ form.grain.join(' + ') || '-' }}</strong></div>
          <div class="review-row"><span>维度</span><strong>{{ dimensions.length }}</strong></div>
          <div class="review-row"><span>度量</span><strong>{{ measures.length }}</strong></div>
        </div>
        <el-alert type="info" :closable="false" show-icon title="创建后模型为草稿状态，可继续在详情页补指标、关系与绑定。" />
      </div>

      <div class="wizard-footer">
        <el-button v-if="step > 0" @click="step -= 1">上一步</el-button>
        <el-button v-if="step < 5" type="primary" @click="next">下一步</el-button>
        <el-button v-if="step === 5" type="primary" :loading="saving" @click="handleFinish">创建模型</el-button>
      </div>
    </div>
  </div>
</template>

<script lang="ts">
/* eslint-disable camelcase */
import {
  createModel,
  batchCreateFields,
  setGrain,
  createDimension,
  createMeasure,
  runModelValidation,
} from '@/api/semantic'
import { useSemanticStore } from '@/stores/semantic'

export default {
  name: 'SemanticModelCreate',
  beforeRouteLeave(to, from, next) {
    if (!this.isDirty()) {
      next()
      return
    }
    this.$confirm('新建模型尚未保存，确定离开？', '提示', { type: 'warning' })
      .then(() => next())
      .catch(() => next(false))
  },
  data(): any {
    return {
      step: 0,
      saving: false,
      error: '',
      domains: [],
      form: {
        domain_id: null,
        name: '',
        business_name: '',
        description: '',
        owner: '',
        grain: [],
      },
      fields: [
        { name: 'order_id', business_name: '订单号', semantic_type: 'key', data_type: 'string' },
        { name: 'order_date', business_name: '下单日期', semantic_type: 'time', data_type: 'date' },
        { name: 'order_amount', business_name: '订单金额', semantic_type: 'measure', data_type: 'number' },
      ],
      dimensions: [],
      measures: [],
    }
  },
  computed: {
    domainName() {
      const match = this.domains.find(item => item.domain_id === this.form.domain_id)
      return match ? match.name : '-'
    },
  },
  created() {
    this.loadDomains()
  },
  methods: {
    isDirty() {
      return Boolean(
        this.step > 0 || this.form.name || this.form.business_name || this.dimensions.length || this.measures.length
      )
    },
    async loadDomains() {
      try {
        this.domains = await useSemanticStore().fetchDomains()
        if (this.domains.length && !this.form.domain_id) this.form.domain_id = this.domains[0].domain_id
      } catch (error) {
        this.error = (error && error.message) || '加载主题域失败'
      }
    },
    addField() {
      this.fields.push({ name: '', business_name: '', semantic_type: 'dimension', data_type: 'string' })
    },
    addDimension() {
      this.dimensions.push({ name: '', field_name: '', dimension_type: 'categorical' })
    },
    addMeasure() {
      this.measures.push({ name: '', field_name: '', agg: 'sum', additivity: 'additive' })
    },
    validateStep() {
      if (this.step === 0) {
        if (!this.form.domain_id || !this.form.name) {
          this.$message.warning('主题域和模型名必填')
          return false
        }
      }
      if (this.step === 1) {
        if (!this.fields.length || this.fields.some(item => !item.name)) {
          this.$message.warning('字段名不能为空')
          return false
        }
      }
      if (this.step === 2 && !this.form.grain.length) {
        this.$message.warning('请选择粒度字段')
        return false
      }
      return true
    },
    next() {
      if (!this.validateStep()) return
      this.step += 1
    },
    async handleFinish() {
      if (!this.validateStep()) return
      this.saving = true
      try {
        const model = await createModel({
          domain_id: this.form.domain_id,
          name: this.form.name,
          business_name: this.form.business_name,
          description: this.form.description,
          owner: this.form.owner,
        })
        const createdFields = await batchCreateFields(model.model_id, this.fields)
        const fieldMap = {}
        createdFields.forEach(item => { fieldMap[item.name] = item.field_id })
        await setGrain(model.model_id, this.form.grain.map(name => fieldMap[name]).filter(Boolean))
        for (const item of this.dimensions) {
          if (!item.name || !item.field_name) continue
          await createDimension(model.model_id, {
            name: item.name,
            field_id: fieldMap[item.field_name],
            dimension_type: item.dimension_type,
          })
        }
        for (const item of this.measures) {
          if (!item.name || !item.field_name) continue
          await createMeasure(model.model_id, {
            name: item.name,
            field_id: fieldMap[item.field_name],
            agg: item.agg,
            additivity: item.additivity,
          })
        }
        try {
          await runModelValidation(model.model_id, 'semantic')
        } catch (error) {
          // 校验失败不阻塞创建，详情页可查看问题
        }
        this.$message.success('模型创建成功')
        this.$router.push(`/models/${model.model_id}`)
      } catch (error) {
        this.error = (error && error.message) || '创建模型失败'
      } finally {
        this.saving = false
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

.wizard-card {
  background: #fff;
  border: 1px solid #ebeef5;
  border-radius: 6px;
  padding: 16px;
}

.wizard-body {
  padding: 24px 12px 8px;
  min-height: 320px;
}

.wizard-toolbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 12px;
}

.wizard-footer {
  display: flex;
  justify-content: flex-end;
  gap: 8px;
  padding-top: 16px;
  border-top: 1px solid #ebeef5;
}

.form-block {
  width: 100%;
}

.danger-text {
  color: #f56c6c;
}

.muted-text {
  color: #909399;
  font-size: 13px;
}

.review-block {
  max-width: 560px;
  border: 1px solid #ebeef5;
  border-radius: 4px;
  padding: 16px;
}

.review-row {
  display: flex;
  justify-content: space-between;
  padding: 8px 0;
  border-bottom: 1px solid #f5f7fa;
}

.review-row:last-child {
  border-bottom: none;
}

.review-row span {
  color: #909399;
}
</style>