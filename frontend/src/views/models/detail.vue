<template>
  <div v-loading="loading" class="semantic-page">
    <div class="semantic-page__header">
      <div>
        <h2 class="semantic-page__title">{{ model.business_name || model.name || '模型详情' }}</h2>
        <p class="semantic-page__subtitle">
          <span class="mono-text">{{ model.name }}</span>
          <span class="dot">·</span>
          <span>{{ model.domain_name }}</span>
          <span class="dot">·</span>
          <StatusBadge :status="model.binding_status" />
          <StatusBadge v-if="model.queryable" status="ready" text="可问数" class="status-gap" />
        </p>
      </div>
      <div class="header-actions">
        <el-button @click="$router.push('/models')">返回列表</el-button>
        <el-button :loading="saving" @click="handleSubmitCertification">提交认证</el-button>
        <el-button type="primary" @click="handleValidate('semantic')">语义校验</el-button>
        <el-button type="primary" plain @click="handleValidate('queryable')">可问数校验</el-button>
      </div>
    </div>

    <el-alert v-if="error" type="error" show-icon :title="error" @close="error = ''" />

    <el-tabs v-model="activeTab" type="border-card">
      <el-tab-pane label="基本信息" name="basic">
        <div class="info-grid">
          <div class="info-item"><span>模型名</span><strong class="mono-text">{{ model.name }}</strong></div>
          <div class="info-item"><span>业务名</span><strong>{{ model.business_name || '-' }}</strong></div>
          <div class="info-item"><span>主题域</span><strong>{{ model.domain_name || '-' }}</strong></div>
          <div class="info-item"><span>负责人</span><strong>{{ model.owner || '-' }}</strong></div>
          <div class="info-item"><span>版本</span><strong>v{{ model.version }}</strong></div>
          <div class="info-item"><span>字段数</span><strong>{{ model.field_total || 0 }}</strong></div>
          <div class="info-item"><span>绑定覆盖率</span><strong>{{ Math.round((model.coverage || 0) * 100) }}%</strong></div>
          <div class="info-item"><span>主绑定</span><strong class="mono-text">{{ model.primary_query_ref || '-' }}</strong>
          </div>
        </div>
        <div class="section">
          <div class="section__header">
            <span>业务粒度</span>
            <el-button link size="small" @click="openGrain">编辑粒度</el-button>
          </div>
          <div class="tag-list">
            <el-tag v-for="item in model.grain || []" :key="item.field_id" size="small">{{ item.business_name ||
              item.name }}</el-tag>
            <span v-if="!(model.grain || []).length" class="muted-text">未声明粒度</span>
          </div>
        </div>
        <div class="section">
          <div class="section__header"><span>描述</span></div>
          <div class="muted-text">{{ model.description || '暂无描述' }}</div>
        </div>
      </el-tab-pane>

      <el-tab-pane :label="`字段 (${(model.fields || []).length})`" name="fields">
        <div class="tab-toolbar">
          <el-button size="small" type="primary" @click="openField()">添加字段</el-button>
        </div>
        <el-table :data="model.fields || []" size="small" border>
          <el-table-column prop="name" label="字段名" min-width="140" />
          <el-table-column prop="business_name" label="业务名" min-width="130" />
          <el-table-column prop="semantic_type" label="角色" width="110" />
          <el-table-column prop="data_type" label="类型" width="100" />
          <el-table-column prop="expression" label="表达式" min-width="160" show-overflow-tooltip />
          <el-table-column label="隐藏" width="70">
            <template #default="{ row }">{{ row.is_hidden ? '是' : '否' }}</template>
          </el-table-column>
          <el-table-column label="操作" width="130">
            <template #default="{ row }">
              <el-button link @click="openField(row)">编辑</el-button>
              <el-button link class="danger-text" @click="handleDeleteField(row)">删除</el-button>
            </template>
          </el-table-column>
        </el-table>
      </el-tab-pane>

      <el-tab-pane :label="`维度 (${(model.dimensions || []).length})`" name="dimensions">
        <div class="tab-toolbar">
          <el-button size="small" type="primary" @click="openDimension()">添加维度</el-button>
        </div>
        <el-table :data="model.dimensions || []" size="small" border>
          <el-table-column prop="name" label="维度名" min-width="140" />
          <el-table-column prop="field_name" label="来源字段" min-width="140" />
          <el-table-column prop="dimension_type" label="类型" width="120" />
          <el-table-column prop="time_granularity" label="时间粒度" width="110" />
          <el-table-column label="认证" width="80">
            <template #default="{ row }">{{ row.verified ? '是' : '否' }}</template>
          </el-table-column>
          <el-table-column label="操作" width="130">
            <template #default="{ row }">
              <el-button link @click="openDimension(row)">编辑</el-button>
              <el-button link class="danger-text" @click="handleDeleteDimension(row)">删除</el-button>
            </template>
          </el-table-column>
        </el-table>
      </el-tab-pane>

      <el-tab-pane :label="`度量 (${(model.measures || []).length})`" name="measures">
        <div class="tab-toolbar">
          <el-button size="small" type="primary" @click="openMeasure()">添加度量</el-button>
        </div>
        <el-table :data="model.measures || []" size="small" border>
          <el-table-column prop="name" label="度量名" min-width="160" />
          <el-table-column prop="field_name" label="来源字段" min-width="140" />
          <el-table-column prop="agg" label="聚合" width="120" />
          <el-table-column prop="additivity" label="可加性" width="130" />
          <el-table-column prop="unit" label="单位" width="90" />
          <el-table-column label="操作" width="130">
            <template #default="{ row }">
              <el-button link @click="openMeasure(row)">编辑</el-button>
              <el-button link class="danger-text" @click="handleDeleteMeasure(row)">删除</el-button>
            </template>
          </el-table-column>
        </el-table>
      </el-tab-pane>

      <el-tab-pane :label="`关系 (${(model.relationships || []).length})`" name="relationships">
        <div class="tab-toolbar">
          <el-button size="small" type="primary" @click="openRelationship()">添加关系</el-button>
          <el-button size="small" @click="handleSuggestions">候选关系</el-button>
        </div>
        <el-table :data="model.relationships || []" size="small" border>
          <el-table-column prop="name" label="关系名" min-width="140" />
          <el-table-column label="路径" min-width="220">
            <template #default="{ row }">
              {{ row.from_model_name }}.{{ row.from_field_name }} → {{ row.to_model_name }}.{{ row.to_field_name }}
            </template>
          </el-table-column>
          <el-table-column prop="cardinality" label="基数" width="90" />
          <el-table-column prop="join_type" label="JOIN" width="80" />
          <el-table-column label="认证" width="80">
            <template #default="{ row }">{{ row.verified ? '是' : '否' }}</template>
          </el-table-column>
          <el-table-column label="操作" width="130">
            <template #default="{ row }">
              <el-button link @click="openRelationship(row)">编辑</el-button>
              <el-button link class="danger-text" @click="handleDeleteRelationship(row)">删除</el-button>
            </template>
          </el-table-column>
        </el-table>
      </el-tab-pane>

      <el-tab-pane :label="`绑定 (${(model.bindings || []).length})`" name="bindings">
        <div class="tab-toolbar">
          <el-button size="small" type="primary" @click="openBinding()">新建绑定</el-button>
        </div>
        <el-table :data="model.bindings || []" size="small" border>
          <el-table-column prop="query_ref" label="查询引用" min-width="220" />
          <el-table-column prop="binding_type" label="类型" width="100" />
          <el-table-column prop="source_system" label="来源系统" width="140" />
          <el-table-column label="覆盖率" width="120">
            <template #default="{ row }">
              <el-progress :percentage="Math.round((row.coverage || 0) * 100)" :stroke-width="6" />
            </template>
          </el-table-column>
          <el-table-column label="状态" width="150">
            <template #default="{ row }">
              <StatusBadge :status="row.status" />
              <StatusBadge v-if="row.is_primary" status="ready" text="主绑定" class="status-gap" />
              <StatusBadge v-if="row.drifted" status="drifted" class="status-gap" />
            </template>
          </el-table-column>
          <el-table-column label="操作" width="200">
            <template #default="{ row }">
              <el-button link @click="openMapping(row)">字段映射</el-button>
              <el-button link @click="handleSetPrimary(row)">设为主绑定</el-button>
            </template>
          </el-table-column>
        </el-table>
      </el-tab-pane>

      <el-tab-pane label="校验" name="validation">
        <div class="tab-toolbar">
          <el-button size="small" type="primary" @click="handleValidate('semantic')">语义校验</el-button>
          <el-button size="small" type="primary" plain @click="handleValidate('queryable')">可问数校验</el-button>
        </div>
        <ValidationPanel title="最近一次校验" :issues="latestIssues" :loading="validating" />
        <div class="section">
          <div class="section__header"><span>校验历史</span></div>
          <el-table :data="validationRuns" size="small" border>
            <el-table-column prop="level" label="级别" width="110" />
            <el-table-column prop="status" label="结果" width="100">
              <template #default="{ row }">
                <StatusBadge :status="row.status" />
              </template>
            </el-table-column>
            <el-table-column prop="created_by" label="执行人" width="120" />
            <el-table-column prop="created_at" label="时间" width="180" />
            <el-table-column label="问题数" width="90">
              <template #default="{ row }">{{ (row.issues || []).length }}</template>
            </el-table-column>
          </el-table>
        </div>
      </el-tab-pane>

      <el-tab-pane label="版本" name="versions">
        <div class="muted-text">模型版本随语义变更递增；发布与回滚在「校验与发布」中管理。</div>
        <div class="section">
          <div class="info-grid">
            <div class="info-item"><span>当前版本</span><strong>v{{ model.version }}</strong></div>
            <div class="info-item"><span>认证状态</span><strong>{{ model.status }}</strong></div>
            <div class="info-item"><span>可问数</span><strong>{{ model.queryable ? '是' : '否' }}</strong></div>
            <div class="info-item"><span>最近更新</span><strong>{{ model.updated_at }}</strong></div>
          </div>
        </div>
        <div class="section">
          <div class="section__header">
            <span>快照版本</span>
            <el-button link size="small" @click="loadSnapshots">刷新</el-button>
          </div>
          <el-table v-loading="snapshotLoading" :data="snapshots" size="small" border empty-text="暂无快照">
            <el-table-column prop="version" label="版本" min-width="160" />
            <el-table-column label="状态" width="100">
              <template #default="{ row }">{{ row.status === 'active' ? '生效中' : '已归档' }}</template>
            </el-table-column>
            <el-table-column prop="published_by" label="发布人" width="120" />
            <el-table-column prop="published_at" label="发布时间" width="180" />
            <el-table-column label="操作" width="100">
              <template #default="{ row }">
                <el-button link @click="openRelease(row)">查看</el-button>
              </template>
            </el-table-column>
          </el-table>
        </div>
      </el-tab-pane>
    </el-tabs>

    <!-- 字段 -->
    <el-dialog :title="fieldForm.field_id ? '编辑字段' : '添加字段'" v-model="fieldVisible" width="560px">
      <el-form label-width="90px">
        <el-form-item label="字段名" required><el-input v-model.trim="fieldForm.name" /></el-form-item>
        <el-form-item label="业务名"><el-input v-model.trim="fieldForm.business_name" /></el-form-item>
        <el-form-item label="角色">
          <el-select v-model="fieldForm.semantic_type" class="form-block">
            <el-option label="key" value="key" />
            <el-option label="dimension" value="dimension" />
            <el-option label="time" value="time" />
            <el-option label="measure" value="measure" />
            <el-option label="unknown" value="unknown" />
          </el-select>
        </el-form-item>
        <el-form-item label="类型">
          <el-select v-model="fieldForm.data_type" class="form-block">
            <el-option label="string" value="string" />
            <el-option label="number" value="number" />
            <el-option label="date" value="date" />
            <el-option label="boolean" value="boolean" />
            <el-option label="unknown" value="unknown" />
          </el-select>
        </el-form-item>
        <el-form-item label="同义词">
          <el-select v-model="fieldForm.synonyms" multiple filterable allow-create default-first-option
            class="form-block">
            <el-option v-for="item in synonymOptions" :key="item" :label="item" :value="item" />
          </el-select>
        </el-form-item>
        <el-form-item label="表达式"><el-input v-model.trim="fieldForm.expression" /></el-form-item>
        <el-form-item label="隐藏"><el-switch v-model="fieldForm.is_hidden" /></el-form-item>
        <el-form-item label="描述"><el-input v-model.trim="fieldForm.description" type="textarea"
            :rows="2" /></el-form-item>
      </el-form>
      <template #footer>
        <span>
          <el-button @click="fieldVisible = false">取消</el-button>
          <el-button type="primary" :loading="saving" @click="saveField">保存</el-button>
        </span>
      </template>
    </el-dialog>

    <!-- 维度 -->
    <el-dialog :title="dimensionForm.dimension_id ? '编辑维度' : '添加维度'" v-model="dimensionVisible" width="520px">
      <el-form label-width="90px">
        <el-form-item label="维度名" required><el-input v-model.trim="dimensionForm.name" /></el-form-item>
        <el-form-item label="来源字段" required>
          <el-select v-model="dimensionForm.field_id" filterable class="form-block">
            <el-option v-for="item in model.fields || []" :key="item.field_id" :label="item.business_name || item.name"
              :value="item.field_id" />
          </el-select>
        </el-form-item>
        <el-form-item label="类型">
          <el-select v-model="dimensionForm.dimension_type" class="form-block">
            <el-option label="categorical" value="categorical" />
            <el-option label="time" value="time" />
          </el-select>
        </el-form-item>
        <el-form-item v-if="dimensionForm.dimension_type === 'time'" label="时间粒度">
          <el-select v-model="dimensionForm.time_granularity" class="form-block" clearable>
            <el-option label="day" value="day" />
            <el-option label="week" value="week" />
            <el-option label="month" value="month" />
            <el-option label="quarter" value="quarter" />
            <el-option label="year" value="year" />
          </el-select>
        </el-form-item>
        <el-form-item label="已认证"><el-switch v-model="dimensionForm.verified" /></el-form-item>
      </el-form>
      <template #footer>
        <span>
          <el-button @click="dimensionVisible = false">取消</el-button>
          <el-button type="primary" :loading="saving" @click="saveDimension">保存</el-button>
        </span>
      </template>
    </el-dialog>

    <!-- 度量 -->
    <el-dialog :title="measureForm.measure_id ? '编辑度量' : '添加度量'" v-model="measureVisible" width="520px">
      <el-form label-width="90px">
        <el-form-item label="度量名" required><el-input v-model.trim="measureForm.name" /></el-form-item>
        <el-form-item label="来源字段">
          <el-select v-model="measureForm.field_id" filterable clearable class="form-block">
            <el-option v-for="item in model.fields || []" :key="item.field_id" :label="item.business_name || item.name"
              :value="item.field_id" />
          </el-select>
        </el-form-item>
        <el-form-item label="表达式"><el-input v-model.trim="measureForm.expr" /></el-form-item>
        <el-form-item label="聚合">
          <el-select v-model="measureForm.agg" class="form-block">
            <el-option label="sum" value="sum" />
            <el-option label="count" value="count" />
            <el-option label="count_distinct" value="count_distinct" />
            <el-option label="avg" value="avg" />
            <el-option label="min" value="min" />
            <el-option label="max" value="max" />
          </el-select>
        </el-form-item>
        <el-form-item label="可加性">
          <el-select v-model="measureForm.additivity" class="form-block">
            <el-option label="additive" value="additive" />
            <el-option label="semi_additive" value="semi_additive" />
            <el-option label="non_additive" value="non_additive" />
          </el-select>
        </el-form-item>
        <el-form-item v-if="measureForm.additivity === 'semi_additive'" label="窗口选择">
          <el-select v-model="measureForm.window_choice" class="form-block">
            <el-option label="max" value="max" />
            <el-option label="min" value="min" />
          </el-select>
        </el-form-item>
        <el-form-item label="单位"><el-input v-model.trim="measureForm.unit" /></el-form-item>
      </el-form>
      <template #footer>
        <span>
          <el-button @click="measureVisible = false">取消</el-button>
          <el-button type="primary" :loading="saving" @click="saveMeasure">保存</el-button>
        </span>
      </template>
    </el-dialog>

    <!-- 关系 -->
    <el-dialog :title="relationshipForm.edge_id ? '编辑关系' : '添加关系'" v-model="relationshipVisible" width="560px">
      <el-form label-width="100px">
        <el-form-item label="关系名" required><el-input v-model.trim="relationshipForm.name" /></el-form-item>
        <el-form-item label="起点字段" required>
          <el-select v-model="relationshipForm.from_field_id" filterable class="form-block">
            <el-option v-for="item in model.fields || []" :key="item.field_id"
              :label="`${item.name} (${item.business_name || ''})`" :value="item.field_id" />
          </el-select>
        </el-form-item>
        <el-form-item label="目标模型" required>
          <el-select v-model="relationshipForm.to_model_id" filterable class="form-block"
            @change="handleTargetModelChange">
            <el-option v-for="item in targetModels" :key="item.model_id" :label="item.business_name || item.name"
              :value="item.model_id" />
          </el-select>
        </el-form-item>
        <el-form-item label="目标字段" required>
          <el-select v-model="relationshipForm.to_field_id" filterable class="form-block">
            <el-option v-for="item in targetFields" :key="item.field_id"
              :label="`${item.name} (${item.business_name || ''})`" :value="item.field_id" />
          </el-select>
        </el-form-item>
        <el-form-item label="基数">
          <el-select v-model="relationshipForm.cardinality" class="form-block">
            <el-option label="N:1" value="N:1" />
            <el-option label="1:1" value="1:1" />
            <el-option label="1:N" value="1:N" />
            <el-option label="N:N" value="N:N" />
          </el-select>
        </el-form-item>
        <el-form-item label="JOIN 类型">
          <el-select v-model="relationshipForm.join_type" class="form-block">
            <el-option label="inner" value="inner" />
            <el-option label="left" value="left" />
          </el-select>
        </el-form-item>
        <el-form-item label="已认证"><el-switch v-model="relationshipForm.verified" /></el-form-item>
      </el-form>
      <template #footer>
        <span>
          <el-button @click="relationshipVisible = false">取消</el-button>
          <el-button type="primary" :loading="saving" @click="saveRelationship">保存</el-button>
        </span>
      </template>
    </el-dialog>

    <!-- 绑定 -->
    <el-dialog title="新建绑定" v-model="bindingVisible" width="560px">
      <el-form label-width="110px">
        <el-form-item label="绑定类型">
          <el-select v-model="bindingForm.binding_type" class="form-block">
            <el-option label="dataset" value="dataset" />
            <el-option label="table" value="table" />
            <el-option label="view" value="view" />
            <el-option label="subquery" value="subquery" />
          </el-select>
        </el-form-item>
        <el-form-item label="查询引用" required>
          <el-input v-model.trim="bindingForm.query_ref" placeholder="dataset.ds_order_detail" />
        </el-form-item>
        <el-form-item label="来源系统"><el-input v-model.trim="bindingForm.source_system"
            placeholder="chatbi_dataset" /></el-form-item>
        <el-form-item label="数据集 ID"><el-input v-model.trim="bindingForm.external_dataset_id" /></el-form-item>
        <el-form-item label="主绑定"><el-switch v-model="bindingForm.is_primary" /></el-form-item>
        <el-form-item label="行过滤"><el-input v-model.trim="bindingForm.row_filter" placeholder="可选" /></el-form-item>
      </el-form>
      <template #footer>
        <span>
          <el-button @click="bindingVisible = false">取消</el-button>
          <el-button type="primary" :loading="saving" @click="saveBinding">保存并去映射</el-button>
        </span>
      </template>
    </el-dialog>

    <!-- 粒度 -->
    <el-dialog title="编辑粒度" v-model="grainVisible" width="520px">
      <el-select v-model="grainFields" multiple filterable class="form-block" placeholder="选择粒度字段">
        <el-option v-for="item in model.fields || []" :key="item.field_id" :label="item.business_name || item.name"
          :value="item.field_id" />
      </el-select>
      <template #footer>
        <span>
          <el-button @click="grainVisible = false">取消</el-button>
          <el-button type="primary" :loading="saving" @click="saveGrain">保存</el-button>
        </span>
      </template>
    </el-dialog>

    <!-- 候选关系 -->
    <el-dialog title="候选关系" v-model="suggestionVisible" width="680px">
      <el-table :data="suggestions" size="small" border empty-text="没有候选关系">
        <el-table-column label="起点" min-width="150">
          <template #default="{ row }">{{ row.from_model_name }}.{{ row.from_field_name }}</template>
        </el-table-column>
        <el-table-column label="终点" min-width="150">
          <template #default="{ row }">{{ row.to_model_name }}.{{ row.to_field_name }}</template>
        </el-table-column>
        <el-table-column prop="suggested_cardinality" label="建议基数" width="100" />
        <el-table-column label="置信度" width="100">
          <template #default="{ row }">{{ Math.round((row.confidence || 0) * 100) }}%</template>
        </el-table-column>
        <el-table-column label="操作" width="80">
          <template #default="{ row }">
            <el-button link @click="adoptSuggestion(row)">采用</el-button>
          </template>
        </el-table-column>
      </el-table>
    </el-dialog>
  </div>
</template>

<script lang="ts">
/* eslint-disable camelcase */
import {
  getModel,
  setGrain,
  createField,
  updateField,
  deleteField,
  createDimension,
  updateDimension,
  deleteDimension,
  createMeasure,
  updateMeasure,
  deleteMeasure,
  createRelationship,
  updateRelationship,
  deleteRelationship,
  relationshipSuggestions,
  createBinding,
  setPrimaryBinding,
  runModelValidation,
  listModelValidation,
  createCertification,
  listSnapshots,
  listSynonyms,
} from '@/api/semantic'
import { useSemanticStore } from '@/stores/semantic'
import StatusBadge from '../components/StatusBadge.vue'
import ValidationPanel from '../components/ValidationPanel.vue'

export default {
  name: 'SemanticModelDetail',
  components: { StatusBadge, ValidationPanel },
  beforeRouteLeave(to, from, next) {
    if (!this.hasOpenEditor()) {
      next()
      return
    }
    this.$confirm('当前有未保存的编辑，确定离开？', '提示', { type: 'warning' })
      .then(() => next())
      .catch(() => next(false))
  },
  data(): any {
    return {
      loading: false,
      saving: false,
      validating: false,
      error: '',
      model: {},
      activeTab: 'basic',
      targetModels: [],
      targetFields: [],
      synonymOptions: [],
      validationRuns: [],
      latestIssues: [],
      snapshots: [],
      snapshotLoading: false,
      fieldVisible: false,
      dimensionVisible: false,
      measureVisible: false,
      relationshipVisible: false,
      bindingVisible: false,
      grainVisible: false,
      suggestionVisible: false,
      suggestions: [],
      grainFields: [],
      fieldForm: this.emptyField(),
      dimensionForm: this.emptyDimension(),
      measureForm: this.emptyMeasure(),
      relationshipForm: this.emptyRelationship(),
      bindingForm: this.emptyBinding(),
    }
  },
  computed: {
    modelId() {
      return Number(this.$route.params.id)
    },
  },
  created() {
    this.load()
    this.loadTargetModels()
    this.loadSynonymOptions()
  },
  methods: {
    hasOpenEditor() {
      return [
        this.fieldVisible,
        this.dimensionVisible,
        this.measureVisible,
        this.relationshipVisible,
        this.bindingVisible,
        this.grainVisible,
      ].some(Boolean)
    },
    emptyField() {
      return { field_id: null, name: '', business_name: '', semantic_type: 'dimension', data_type: 'string', synonyms: [], expression: '', is_hidden: false, description: '' }
    },
    emptyDimension() {
      return { dimension_id: null, name: '', field_id: null, dimension_type: 'categorical', time_granularity: 'day', verified: false }
    },
    emptyMeasure() {
      return { measure_id: null, name: '', field_id: null, expr: '', agg: 'sum', additivity: 'additive', window_choice: '', unit: '' }
    },
    emptyRelationship() {
      return { edge_id: null, name: '', from_field_id: null, to_model_id: null, to_field_id: null, cardinality: 'N:1', join_type: 'inner', verified: false }
    },
    emptyBinding() {
      return { binding_type: 'dataset', query_ref: '', source_system: 'chatbi_dataset', external_dataset_id: '', is_primary: false, row_filter: '' }
    },
    async load() {
      this.loading = true
      this.error = ''
      try {
        this.model = await getModel(this.modelId)
        this.grainFields = (this.model.grain || []).map(item => item.field_id)
        this.validationRuns = await listModelValidation(this.modelId)
        this.latestIssues = (this.validationRuns[0] && this.validationRuns[0].issues) || []
        this.loadSnapshots()
      } catch (error) {
        this.error = (error && error.message) || '加载模型失败'
      } finally {
        this.loading = false
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
    async loadSnapshots() {
      this.snapshotLoading = true
      try {
        this.snapshots = await listSnapshots({ limit: 20 })
      } catch (error) {
        this.snapshots = []
      } finally {
        this.snapshotLoading = false
      }
    },
    openRelease(row) {
      this.$router.push({ path: '/release', query: { version: row.version } })
    },
    async loadTargetModels() {
      try {
        const models = await useSemanticStore().fetchModels()
        this.targetModels = models.filter(item => item.model_id !== this.modelId)
      } catch (error) {
        // ignore
      }
    },
    openField(row?: any) {
      this.fieldForm = row ? { ...this.emptyField(), ...row } : this.emptyField()
      this.fieldVisible = true
    },
    async saveField() {
      if (!this.fieldForm.name) return this.$message.warning('字段名不能为空')
      this.saving = true
      try {
        const payload = { ...this.fieldForm }
        delete payload.field_id
        delete payload.model_id
        if (this.fieldForm.field_id) await updateField(this.fieldForm.field_id, payload)
        else await createField(this.modelId, payload)
        this.fieldVisible = false
        this.$message.success('保存成功')
        this.load()
      } catch (error) {
        this.$message.error((error && error.message) || '保存失败')
      } finally {
        this.saving = false
      }
    },
    async handleDeleteField(row) {
      try {
        await this.$confirm(`删除字段「${row.name}」？`, '提示', { type: 'warning' })
        await deleteField(row.field_id)
        this.load()
      } catch (error) {
        if (error !== 'cancel') this.$message.error((error && error.message) || '删除失败')
      }
    },
    openDimension(row?: any) {
      this.dimensionForm = row ? { ...this.emptyDimension(), ...row } : this.emptyDimension()
      this.dimensionVisible = true
    },
    async saveDimension() {
      if (!this.dimensionForm.name || !this.dimensionForm.field_id) return this.$message.warning('维度名和来源字段必填')
      this.saving = true
      try {
        const payload = { ...this.dimensionForm }
        delete payload.dimension_id
        delete payload.model_id
        delete payload.field_name
        if (this.dimensionForm.dimension_id) await updateDimension(this.dimensionForm.dimension_id, payload)
        else await createDimension(this.modelId, payload)
        this.dimensionVisible = false
        this.$message.success('保存成功')
        this.load()
      } catch (error) {
        this.$message.error((error && error.message) || '保存失败')
      } finally {
        this.saving = false
      }
    },
    async handleDeleteDimension(row) {
      try {
        await this.$confirm(`删除维度「${row.name}」？`, '提示', { type: 'warning' })
        await deleteDimension(row.dimension_id)
        this.load()
      } catch (error) {
        if (error !== 'cancel') this.$message.error((error && error.message) || '删除失败')
      }
    },
    openMeasure(row?: any) {
      this.measureForm = row ? { ...this.emptyMeasure(), ...row } : this.emptyMeasure()
      this.measureVisible = true
    },
    async saveMeasure() {
      if (!this.measureForm.name) return this.$message.warning('度量名不能为空')
      this.saving = true
      try {
        const payload = { ...this.measureForm }
        delete payload.measure_id
        delete payload.model_id
        delete payload.field_name
        delete payload.field_business_name
        if (payload.additivity !== 'semi_additive') delete payload.window_choice
        if (this.measureForm.measure_id) await updateMeasure(this.measureForm.measure_id, payload)
        else await createMeasure(this.modelId, payload)
        this.measureVisible = false
        this.$message.success('保存成功')
        this.load()
      } catch (error) {
        this.$message.error((error && error.message) || '保存失败')
      } finally {
        this.saving = false
      }
    },
    async handleDeleteMeasure(row) {
      try {
        await this.$confirm(`删除度量「${row.name}」？`, '提示', { type: 'warning' })
        await deleteMeasure(row.measure_id)
        this.load()
      } catch (error) {
        if (error !== 'cancel') this.$message.error((error && error.message) || '删除失败')
      }
    },
    openRelationship(row?: any) {
      this.relationshipForm = row ? { ...this.emptyRelationship(), ...row, edge_id: row.edge_id } : this.emptyRelationship()
      this.relationshipVisible = true
      if (this.relationshipForm.to_model_id) this.handleTargetModelChange(this.relationshipForm.to_model_id)
    },
    async handleTargetModelChange(modelId) {
      this.targetFields = []
      this.relationshipForm.to_field_id = null
      if (!modelId) return
      try {
        const target = await getModel(modelId)
        this.targetFields = target.fields || []
      } catch (error) {
        this.$message.error('加载目标模型字段失败')
      }
    },
    async saveRelationship() {
      if (!this.relationshipForm.name || !this.relationshipForm.from_field_id || !this.relationshipForm.to_model_id || !this.relationshipForm.to_field_id) {
        return this.$message.warning('关系名、起点字段、目标模型、目标字段必填')
      }
      this.saving = true
      try {
        const payload = { ...this.relationshipForm }
        delete payload.edge_id
        delete payload.from_model_id
        delete payload.to_model_name
        delete payload.from_model_name
        delete payload.from_field_name
        delete payload.to_field_name
        if (this.relationshipForm.edge_id) await updateRelationship(this.relationshipForm.edge_id, payload)
        else await createRelationship(this.modelId, payload)
        this.relationshipVisible = false
        this.$message.success('保存成功')
        this.load()
      } catch (error) {
        this.$message.error((error && error.message) || '保存失败')
      } finally {
        this.saving = false
      }
    },
    async handleDeleteRelationship(row) {
      try {
        await this.$confirm(`删除关系「${row.name}」？`, '提示', { type: 'warning' })
        await deleteRelationship(row.edge_id)
        this.load()
      } catch (error) {
        if (error !== 'cancel') this.$message.error((error && error.message) || '删除失败')
      }
    },
    async handleSuggestions() {
      try {
        this.suggestions = await relationshipSuggestions(this.modelId)
        this.suggestionVisible = true
      } catch (error) {
        this.$message.error('加载候选关系失败')
      }
    },
    adoptSuggestion(row) {
      this.relationshipForm = {
        ...this.emptyRelationship(),
        name: `${row.from_model_name}_${row.to_model_name}`,
        from_field_id: row.from_field_id,
        to_model_id: row.to_model_id,
        to_field_id: row.to_field_id,
        cardinality: row.suggested_cardinality,
      }
      this.suggestionVisible = false
      this.relationshipVisible = true
      this.handleTargetModelChange(row.to_model_id)
    },
    openBinding() {
      this.bindingForm = this.emptyBinding()
      this.bindingVisible = true
    },
    async saveBinding() {
      if (!this.bindingForm.query_ref) return this.$message.warning('查询引用不能为空')
      this.saving = true
      try {
        const binding = await createBinding(this.modelId, { ...this.bindingForm, status: 'draft' })
        this.bindingVisible = false
        this.$message.success('绑定已创建')
        this.$router.push(`/bindings/${binding.binding_id}/mapping`)
      } catch (error) {
        this.$message.error((error && error.message) || '创建绑定失败')
      } finally {
        this.saving = false
      }
    },
    openMapping(row) {
      this.$router.push(`/bindings/${row.binding_id}/mapping`)
    },
    async handleSetPrimary(row) {
      try {
        await setPrimaryBinding(row.binding_id)
        this.$message.success('已设为主绑定')
        this.load()
      } catch (error) {
        this.$message.error((error && error.message) || '设置失败')
      }
    },
    openGrain() {
      this.grainFields = (this.model.grain || []).map(item => item.field_id)
      this.grainVisible = true
    },
    async saveGrain() {
      if (!this.grainFields.length) return this.$message.warning('粒度不能为空')
      this.saving = true
      try {
        await setGrain(this.modelId, this.grainFields)
        this.grainVisible = false
        this.$message.success('粒度已保存')
        this.load()
      } catch (error) {
        this.$message.error((error && error.message) || '保存失败')
      } finally {
        this.saving = false
      }
    },
    async handleValidate(level) {
      this.validating = true
      try {
        const result = await runModelValidation(this.modelId, level)
        this.latestIssues = result.issues || []
        this.activeTab = 'validation'
        this.$message[result.status === 'passed' ? 'success' : 'warning'](
          result.status === 'passed' ? '校验通过' : '校验未通过'
        )
        this.load()
      } catch (error) {
        this.$message.error((error && error.message) || '校验失败')
      } finally {
        this.validating = false
      }
    },
    async handleSubmitCertification() {
      try {
        await this.$confirm('提交模型认证？认证通过后才能发布快照。', '提示', { type: 'warning' })
        await createCertification({ asset_type: 'model', asset_id: this.modelId })
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

.status-gap {
  margin-left: 4px;
}

.header-actions {
  display: flex;
  gap: 8px;
}

.info-grid {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 12px;
}

.info-item {
  border: 1px solid #ebeef5;
  border-radius: 4px;
  padding: 10px 12px;
  background: #fafafa;
}

.info-item span {
  display: block;
  color: #909399;
  font-size: 12px;
  margin-bottom: 4px;
}

.info-item strong {
  color: #303133;
  font-weight: 500;
  word-break: break-all;
}

.section {
  margin-top: 18px;
}

.section__header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 8px;
  font-weight: 600;
  color: #303133;
}

.tag-list {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}

.tab-toolbar {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 12px;
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
</style>
