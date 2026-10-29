<template>
  <div class="semantic-page">
    <div class="semantic-page__header">
      <div>
        <h2 class="semantic-page__title">知识上下文</h2>
        <p class="semantic-page__subtitle">术语、同义词、业务规则、资产 Context 与召回测试</p>
      </div>
    </div>

    <el-tabs v-model="activeTab" type="border-card">
      <el-tab-pane label="术语表" name="terms">
        <div class="tab-toolbar">
          <el-button type="primary" size="small" @click="openTerm()">新建术语</el-button>
        </div>
        <el-table :data="terms" size="small" border empty-text="暂无术语">
          <el-table-column prop="name" label="术语" min-width="140" />
          <el-table-column label="同义词" min-width="200">
            <template #default="{ row }">{{ (row.synonyms || []).join('、') || '-' }}</template>
          </el-table-column>
          <el-table-column prop="definition" label="定义" min-width="240" show-overflow-tooltip />
          <el-table-column prop="scope_type" label="范围" width="100" />
          <el-table-column prop="owner" label="负责人" width="110" />
          <el-table-column label="操作" width="130">
            <template #default="{ row }">
              <el-button link @click="openTerm(row)">编辑</el-button>
              <el-button link class="danger-text" @click="deleteTermRow(row)">删除</el-button>
            </template>
          </el-table-column>
        </el-table>
      </el-tab-pane>

      <el-tab-pane label="同义词" name="synonyms">
        <div class="tab-toolbar">
          <el-input v-model.trim="synonymQuery" placeholder="搜索同义词 / 标准词" clearable size="small"
            class="synonym-search" />
          <el-button type="primary" size="small" @click="openSynonym()">新建同义词</el-button>
        </div>
        <el-table :data="filteredSynonyms" size="small" border empty-text="暂未维护同义词">
          <el-table-column prop="synonym" label="同义词" min-width="160" />
          <el-table-column prop="standard_name" label="标准词" min-width="160" />
          <el-table-column label="作用对象" width="120">
            <template #default="{ row }">{{ targetLabel(row.target_type) }}</template>
          </el-table-column>
          <el-table-column label="操作" width="130">
            <template #default="{ row }">
              <el-button link @click="openSynonym(row)">编辑</el-button>
              <el-button link class="danger-text" @click="deleteSynonymRow(row)">删除</el-button>
            </template>
          </el-table-column>
        </el-table>
      </el-tab-pane>

      <el-tab-pane label="业务规则" name="rules">
        <div class="tab-toolbar">
          <el-button type="primary" size="small" @click="openRule()">新建规则</el-button>
        </div>
        <el-table :data="rules" size="small" border empty-text="暂无规则">
          <el-table-column prop="name" label="规则名" min-width="150" />
          <el-table-column prop="rule_type" label="类型" width="100" />
          <el-table-column prop="target_type" label="作用对象" width="110" />
          <el-table-column prop="condition" label="条件" min-width="220" show-overflow-tooltip />
          <el-table-column prop="action" label="动作" width="100" />
          <el-table-column prop="priority" label="优先级" width="90" />
          <el-table-column label="操作" width="130">
            <template #default="{ row }">
              <el-button link @click="openRule(row)">编辑</el-button>
              <el-button link class="danger-text" @click="deleteRuleRow(row)">删除</el-button>
            </template>
          </el-table-column>
        </el-table>
      </el-tab-pane>

      <el-tab-pane label="资产 Context" name="context">
        <el-form label-width="100px" class="context-form">
          <el-form-item label="资产类型">
            <el-select v-model="contextAssetType" class="form-block">
              <el-option label="模型" value="model" />
              <el-option label="指标" value="metric" />
              <el-option label="维度" value="dimension" />
              <el-option label="绑定" value="binding" />
            </el-select>
          </el-form-item>
          <el-form-item label="资产 ID">
            <el-input v-model.number="contextAssetId" />
          </el-form-item>
          <el-form-item label="业务名"><el-input v-model.trim="context.business_name" /></el-form-item>
          <el-form-item label="同义词">
            <el-select v-model="context.synonyms" multiple filterable allow-create default-first-option
              class="form-block">
              <el-option v-for="item in synonymOptions" :key="item" :label="item" :value="item" />
            </el-select>
          </el-form-item>
          <el-form-item label="说明"><el-input v-model.trim="context.definition" type="textarea"
              :rows="4" /></el-form-item>
          <el-form-item>
            <el-button type="primary" :loading="saving" @click="saveContextData">保存 Context</el-button>
            <el-button @click="loadContextData">读取</el-button>
          </el-form-item>
        </el-form>
      </el-tab-pane>

      <el-tab-pane label="召回测试" name="recall">
        <div class="recall-box">
          <el-input v-model.trim="question" placeholder="输入问题，例如：上月华东各渠道 GMV" @keyup.enter="runRecall">
            <template #append>
              <el-button @click="runRecall">测试</el-button>
            </template>
          </el-input>
        </div>
        <el-row v-if="recall" :gutter="16" class="recall-result">
          <el-col :span="8">
            <div class="panel">
              <div class="panel__header">命中指标</div>
              <div class="panel__body">
                <div v-for="item in recall.metrics || []" :key="item.metric_id" class="recall-item">
                  {{ item.business_name || item.name }}
                </div>
                <span v-if="!(recall.metrics || []).length" class="muted-text">无</span>
              </div>
            </div>
          </el-col>
          <el-col :span="8">
            <div class="panel">
              <div class="panel__header">命中维度</div>
              <div class="panel__body">
                <div v-for="item in recall.dimensions || []" :key="item.dimension_id" class="recall-item">{{ item.name
                  }}
                </div>
                <span v-if="!(recall.dimensions || []).length" class="muted-text">无</span>
              </div>
            </div>
          </el-col>
          <el-col :span="8">
            <div class="panel">
              <div class="panel__header">命中术语</div>
              <div class="panel__body">
                <div v-for="item in recall.terms || []" :key="item.term_id" class="recall-item">{{ item.name }}</div>
                <span v-if="!(recall.terms || []).length" class="muted-text">无</span>
              </div>
            </div>
          </el-col>
        </el-row>
      </el-tab-pane>
    </el-tabs>

    <el-dialog :title="termForm.term_id ? '编辑术语' : '新建术语'" v-model="termVisible" width="560px">
      <el-form label-width="90px">
        <el-form-item label="术语" required><el-input v-model.trim="termForm.name" /></el-form-item>
        <el-form-item label="同义词">
          <el-select v-model="termForm.synonyms" multiple filterable allow-create default-first-option
            class="form-block">
            <el-option v-for="item in synonymOptions" :key="item" :label="item" :value="item" />
          </el-select>
        </el-form-item>
        <el-form-item label="定义"><el-input v-model.trim="termForm.definition" type="textarea"
            :rows="3" /></el-form-item>
        <el-form-item label="范围">
          <el-select v-model="termForm.scope_type" class="form-block">
            <el-option label="global" value="global" />
            <el-option label="domain" value="domain" />
            <el-option label="model" value="model" />
          </el-select>
        </el-form-item>
        <el-form-item label="负责人"><el-input v-model.trim="termForm.owner" /></el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="termVisible = false">取消</el-button>
        <el-button type="primary" :loading="saving" @click="saveTerm">保存</el-button>
      </template>
    </el-dialog>

    <el-dialog :title="synonymForm.synonym_id ? '编辑同义词' : '新建同义词'" v-model="synonymVisible" width="520px">
      <el-form label-width="90px">
        <el-form-item label="同义词" required>
          <el-input v-model.trim="synonymForm.synonym" placeholder="成交额" />
        </el-form-item>
        <el-form-item label="标准词" required>
          <el-input v-model.trim="synonymForm.standard_name" placeholder="GMV" />
        </el-form-item>
        <el-form-item label="作用对象">
          <el-select v-model="synonymForm.target_type" class="form-block">
            <el-option v-for="(label, value) in targetLabels" :key="value" :label="label" :value="value" />
          </el-select>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="synonymVisible = false">取消</el-button>
        <el-button type="primary" :loading="saving" @click="saveSynonym">保存</el-button>
      </template>
    </el-dialog>

    <el-dialog :title="ruleForm.rule_id ? '编辑规则' : '新建规则'" v-model="ruleVisible" width="600px">
      <el-form label-width="90px">
        <el-form-item label="规则名" required><el-input v-model.trim="ruleForm.name" /></el-form-item>
        <el-form-item label="类型">
          <el-select v-model="ruleForm.rule_type" class="form-block">
            <el-option label="filter" value="filter" />
            <el-option label="exclude" value="exclude" />
            <el-option label="alias" value="alias" />
          </el-select>
        </el-form-item>
        <el-form-item label="作用对象">
          <el-select v-model="ruleForm.target_type" class="form-block">
            <el-option label="global" value="global" />
            <el-option label="model" value="model" />
            <el-option label="metric" value="metric" />
            <el-option label="domain" value="domain" />
          </el-select>
        </el-form-item>
        <el-form-item label="对象 ID"><el-input v-model.number="ruleForm.target_id" /></el-form-item>
        <el-form-item label="条件" required><el-input v-model.trim="ruleForm.condition"
            placeholder="status <> 'test'" /></el-form-item>
        <el-form-item label="动作">
          <el-select v-model="ruleForm.action" class="form-block">
            <el-option label="exclude" value="exclude" />
            <el-option label="include" value="include" />
            <el-option label="warn" value="warn" />
          </el-select>
        </el-form-item>
        <el-form-item label="优先级"><el-input-number v-model="ruleForm.priority" :min="1" :max="1000" /></el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="ruleVisible = false">取消</el-button>
        <el-button type="primary" :loading="saving" @click="saveRule">保存</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script lang="ts">
/* eslint-disable camelcase */
import {
  listTerms,
  createTerm,
  updateTerm,
  deleteTerm,
  listSynonyms,
  createSynonym,
  updateSynonym,
  deleteSynonym,
  listRules,
  createRule,
  updateRule,
  deleteRule,
  getContext,
  saveContext,
  recallTest,
} from '@/api/semantic'

export default {
  name: 'SemanticKnowledge',
  data(): any {
    return {
      activeTab: 'terms',
      saving: false,
      terms: [],
      synonyms: [],
      synonymQuery: '',
      rules: [],
      question: '',
      recall: null,
      contextAssetType: 'model',
      contextAssetId: null,
      context: { business_name: '', synonyms: [], definition: '' },
      termVisible: false,
      synonymVisible: false,
      ruleVisible: false,
      termForm: this.emptyTerm(),
      synonymForm: this.emptySynonym(),
      ruleForm: this.emptyRule(),
      targetLabels: {
        global: '全局',
        metric: '指标',
        term: '术语',
        dimension: '维度',
        model: '模型',
        field: '字段',
      },
    }
  },
  computed: {
    synonymOptions() {
      return Array.from(new Set(this.synonyms.map(item => item.synonym).filter(Boolean)))
    },
    filteredSynonyms() {
      const q = this.synonymQuery.trim().toLowerCase()
      if (!q) return this.synonyms
      return this.synonyms.filter(
        item => (item.synonym || '').toLowerCase().includes(q) || (item.standard_name || '').toLowerCase().includes(q)
      )
    },
  },
  created() {
    this.loadTerms()
    this.loadSynonyms()
    this.loadRules()
  },
  methods: {
    emptyTerm() {
      return { term_id: null, name: '', synonyms: [], definition: '', scope_type: 'global', owner: '' }
    },
    emptyRule() {
      return { rule_id: null, name: '', rule_type: 'filter', target_type: 'global', target_id: null, condition: '', action: 'exclude', priority: 100 }
    },
    emptySynonym() {
      return { synonym_id: null, synonym: '', standard_name: '', target_type: 'global' }
    },
    targetLabel(type) {
      return this.targetLabels[type] || type || '-'
    },
    async loadTerms() {
      try {
        this.terms = await listTerms()
      } catch (error) {
        this.terms = []
      }
    },
    async loadSynonyms() {
      try {
        this.synonyms = (await listSynonyms()) || []
      } catch (error) {
        this.synonyms = []
      }
    },
    openSynonym(row?: any) {
      this.synonymForm = row ? { ...this.emptySynonym(), ...row } : this.emptySynonym()
      this.synonymVisible = true
    },
    async saveSynonym() {
      if (!this.synonymForm.synonym || !this.synonymForm.standard_name) {
        return this.$message.warning('同义词和标准词不能为空')
      }
      this.saving = true
      try {
        const payload = { ...this.synonymForm }
        delete payload.synonym_id
        if (this.synonymForm.synonym_id) await updateSynonym(this.synonymForm.synonym_id, payload)
        else await createSynonym(payload)
        this.synonymVisible = false
        this.$message.success('保存成功')
        this.loadSynonyms()
      } catch (error) {
        this.$message.error((error && error.message) || '保存失败')
      } finally {
        this.saving = false
      }
    },
    async deleteSynonymRow(row) {
      try {
        await this.$confirm(`删除同义词「${row.synonym}」？`, '提示', { type: 'warning' })
        await deleteSynonym(row.synonym_id)
        this.loadSynonyms()
      } catch (error) {
        if (error !== 'cancel') this.$message.error((error && error.message) || '删除失败')
      }
    },
    async loadRules() {
      try {
        this.rules = await listRules()
      } catch (error) {
        this.rules = []
      }
    },
    openTerm(row?: any) {
      this.termForm = row ? { ...this.emptyTerm(), ...row } : this.emptyTerm()
      this.termVisible = true
    },
    async saveTerm() {
      if (!this.termForm.name) return this.$message.warning('术语名不能为空')
      this.saving = true
      try {
        const payload = { ...this.termForm }
        delete payload.term_id
        if (this.termForm.term_id) await updateTerm(this.termForm.term_id, payload)
        else await createTerm(payload)
        this.termVisible = false
        this.$message.success('保存成功')
        this.loadTerms()
      } catch (error) {
        this.$message.error((error && error.message) || '保存失败')
      } finally {
        this.saving = false
      }
    },
    async deleteTermRow(row) {
      try {
        await this.$confirm(`删除术语「${row.name}」？`, '提示', { type: 'warning' })
        await deleteTerm(row.term_id)
        this.loadTerms()
      } catch (error) {
        if (error !== 'cancel') this.$message.error((error && error.message) || '删除失败')
      }
    },
    openRule(row?: any) {
      this.ruleForm = row ? { ...this.emptyRule(), ...row } : this.emptyRule()
      this.ruleVisible = true
    },
    async saveRule() {
      if (!this.ruleForm.name || !this.ruleForm.condition) return this.$message.warning('规则名和条件必填')
      this.saving = true
      try {
        const payload = { ...this.ruleForm }
        delete payload.rule_id
        if (this.ruleForm.rule_id) await updateRule(this.ruleForm.rule_id, payload)
        else await createRule(payload)
        this.ruleVisible = false
        this.$message.success('保存成功')
        this.loadRules()
      } catch (error) {
        this.$message.error((error && error.message) || '保存失败')
      } finally {
        this.saving = false
      }
    },
    async deleteRuleRow(row) {
      try {
        await this.$confirm(`删除规则「${row.name}」？`, '提示', { type: 'warning' })
        await deleteRule(row.rule_id)
        this.loadRules()
      } catch (error) {
        if (error !== 'cancel') this.$message.error((error && error.message) || '删除失败')
      }
    },
    async loadContextData() {
      if (!this.contextAssetId) return this.$message.warning('请填写资产 ID')
      try {
        this.context = await getContext(this.contextAssetType, this.contextAssetId)
      } catch (error) {
        this.$message.error((error && error.message) || '读取失败')
      }
    },
    async saveContextData() {
      if (!this.contextAssetId) return this.$message.warning('请填写资产 ID')
      this.saving = true
      try {
        await saveContext(this.contextAssetType, this.contextAssetId, this.context)
        this.$message.success('Context 已保存')
      } catch (error) {
        this.$message.error((error && error.message) || '保存失败')
      } finally {
        this.saving = false
      }
    },
    async runRecall() {
      if (!this.question) return
      try {
        this.recall = await recallTest(this.question)
      } catch (error) {
        this.$message.error((error && error.message) || '召回测试失败')
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

.tab-toolbar {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 12px;
}

.synonym-search {
  width: 240px;
}

.form-block {
  width: 100%;
}

.danger-text {
  color: #f56c6c;
}

.context-form {
  max-width: 680px;
}

.recall-box {
  display: flex;
  gap: 8px;
  max-width: 680px;
  margin-bottom: 16px;
}

.panel {
  border: 1px solid #ebeef5;
  border-radius: 4px;
  background: #fff;
}

.panel__header {
  padding: 10px 12px;
  border-bottom: 1px solid #ebeef5;
  font-weight: 600;
}

.panel__body {
  padding: 12px;
  min-height: 80px;
}

.recall-item {
  padding: 4px 0;
}

.muted-text {
  color: #909399;
  font-size: 13px;
}
</style>