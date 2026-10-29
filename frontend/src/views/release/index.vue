<template>
  <div class="semantic-page">
    <div class="semantic-page__header">
      <div>
        <h2 class="semantic-page__title">校验与发布</h2>
        <p class="semantic-page__subtitle">两级校验、认证、快照冻结与回滚</p>
      </div>
      <el-button :loading="loading" @click="loadAll">刷新</el-button>
    </div>

    <el-alert v-if="error" type="error" show-icon :title="error" @close="error = ''" />

    <el-tabs v-model="activeTab" type="border-card">
      <el-tab-pane label="校验中心" name="validation">
        <el-table :data="validationRuns" size="small" border empty-text="暂无校验记录">
          <el-table-column prop="object_type" label="对象" width="100" />
          <el-table-column prop="object_id" label="ID" width="80" />
          <el-table-column prop="level" label="级别" width="110" />
          <el-table-column label="结果" width="100">
            <template #default="{ row }"><StatusBadge :status="row.status" /></template>
          </el-table-column>
          <el-table-column label="问题数" width="90">
            <template #default="{ row }">{{ (row.issues || []).length }}</template>
          </el-table-column>
          <el-table-column prop="created_by" label="执行人" width="120" />
          <el-table-column prop="created_at" label="时间" width="190" />
          <el-table-column label="操作" width="100">
            <template #default="{ row }">
              <el-button link @click="openIssues(row)">查看问题</el-button>
            </template>
          </el-table-column>
        </el-table>
      </el-tab-pane>

      <el-tab-pane label="认证工作台" name="certifications">
        <el-table :data="certifications" size="small" border empty-text="暂无认证单">
          <el-table-column prop="certification_id" label="ID" width="80" />
          <el-table-column prop="asset_type" label="资产类型" width="110" />
          <el-table-column prop="asset_id" label="资产 ID" width="90" />
          <el-table-column prop="requested_by" label="申请人" width="120" />
          <el-table-column label="状态" width="100">
            <template #default="{ row }"><StatusBadge :status="row.status" /></template>
          </el-table-column>
          <el-table-column prop="created_at" label="提交时间" width="190" />
          <el-table-column label="操作" width="160" fixed="right">
            <template #default="{ row }">
              <template v-if="row.status === 'pending'">
                <el-button link @click="decide(row, true)">通过</el-button>
                <el-button link class="danger-text" @click="decide(row, false)">驳回</el-button>
              </template>
              <span v-else class="muted-text">已处理</span>
            </template>
          </el-table-column>
        </el-table>
      </el-tab-pane>

      <el-tab-pane label="语义快照" name="snapshots">
        <div class="tab-toolbar">
          <el-button type="primary" size="small" :loading="publishing" @click="handlePublish">发布新快照</el-button>
        </div>
        <el-table :data="snapshots" size="small" border empty-text="暂无快照">
          <el-table-column prop="version" label="版本" width="160" />
          <el-table-column prop="fingerprint" label="认证指纹" min-width="220" show-overflow-tooltip />
          <el-table-column label="状态" width="100">
            <template #default="{ row }"><StatusBadge :status="row.status" /></template>
          </el-table-column>
          <el-table-column prop="published_by" label="发布人" width="120" />
          <el-table-column prop="published_at" label="发布时间" width="190" />
          <el-table-column label="操作" width="180" fixed="right">
            <template #default="{ row }">
              <el-button link :disabled="row.status === 'active'" @click="handleRollback(row)">回滚</el-button>
            </template>
          </el-table-column>
        </el-table>
        <div class="section">
          <div class="section__header">快照对比</div>
          <div class="diff-bar">
            <el-input v-model.trim="leftVersion" placeholder="左版本，如 v20261027090000" />
            <el-input v-model.trim="rightVersion" placeholder="右版本" />
            <el-button @click="handleDiff">对比</el-button>
          </div>
          <div v-if="diff.changed" class="section">
            <div v-for="item in diff.changed" :key="item.table" class="muted-text">
              {{ item.table }}：{{ item.left }} → {{ item.right }}
            </div>
          </div>
        </div>
      </el-tab-pane>

      <el-tab-pane label="影响分析" name="impact">
        <el-form :inline="true" class="impact-form">
          <el-form-item label="资产类型">
            <el-select v-model="impactAssetType">
              <el-option label="模型" value="model" />
              <el-option label="指标" value="metric" />
            </el-select>
          </el-form-item>
          <el-form-item label="资产 ID">
            <el-input v-model.number="impactAssetId" />
          </el-form-item>
          <el-form-item>
            <el-button type="primary" @click="handleImpact">分析</el-button>
          </el-form-item>
        </el-form>
        <el-row v-if="impact.asset_type" :gutter="16">
          <el-col :span="12">
            <div class="panel">
              <div class="panel__header">关联指标</div>
              <div class="panel__body">
                <div v-for="item in impact.metrics || []" :key="item.metric_id">{{ item.name }}</div>
                <span v-if="!(impact.metrics || []).length" class="muted-text">无</span>
              </div>
            </div>
          </el-col>
          <el-col :span="12">
            <div class="panel">
              <div class="panel__header">下游依赖</div>
              <div class="panel__body">
                <div v-for="item in impact.dependents || []" :key="item.metric_id">{{ item.name }}</div>
                <span v-if="!(impact.dependents || []).length" class="muted-text">无</span>
              </div>
            </div>
          </el-col>
        </el-row>
      </el-tab-pane>
    </el-tabs>

    <el-dialog title="校验问题" v-model="issuesVisible" width="680px">
      <ValidationPanel :issues="currentIssues" />
    </el-dialog>
  </div>
</template>

<script lang="ts">
/* eslint-disable camelcase */
import {
  listValidationRuns,
  listCertifications,
  decideCertification,
  listSnapshots,
  buildSnapshot,
  diffSnapshots,
  rollbackSnapshot,
  impactAnalysis,
} from '@/api/semantic'
import StatusBadge from '../components/StatusBadge.vue'
import ValidationPanel from '../components/ValidationPanel.vue'

export default {
  name: 'SemanticRelease',
  components: { StatusBadge, ValidationPanel },
  data(): any {
    return {
      loading: false,
      publishing: false,
      error: '',
      activeTab: 'validation',
      validationRuns: [],
      certifications: [],
      snapshots: [],
      leftVersion: '',
      rightVersion: '',
      diff: {},
      issuesVisible: false,
      currentIssues: [],
      impactAssetType: 'model',
      impactAssetId: null,
      impact: {},
    }
  },
  created() {
    this.loadAll()
  },
  methods: {
    async loadAll() {
      this.loading = true
      this.error = ''
      try {
        const [runs, certifications, snapshots] = await Promise.all([
          listValidationRuns({ limit: 100 }),
          listCertifications({ limit: 100 }),
          listSnapshots({ limit: 100 }),
        ])
        this.validationRuns = runs || []
        this.certifications = certifications || []
        this.snapshots = snapshots || []
      } catch (error) {
        this.error = (error && error.message) || '加载发布数据失败'
      } finally {
        this.loading = false
      }
    },
    openIssues(row) {
      this.currentIssues = row.issues || []
      this.issuesVisible = true
    },
    async decide(row, approve) {
      try {
        await this.$confirm(approve ? '通过该认证？' : '驳回该认证？', '提示', { type: 'warning' })
        await decideCertification(row.certification_id, { approve })
        this.$message.success('已处理')
        this.loadAll()
      } catch (error) {
        if (error !== 'cancel') this.$message.error((error && error.message) || '操作失败')
      }
    },
    async handlePublish() {
      this.publishing = true
      try {
        const snapshot = await buildSnapshot()
        this.$message.success(`快照 ${snapshot.version} 已发布`)
        this.loadAll()
      } catch (error) {
        this.$message.error((error && error.message) || '发布失败')
      } finally {
        this.publishing = false
      }
    },
    async handleRollback(row) {
      try {
        await this.$confirm(`回滚到 ${row.version}？`, '提示', { type: 'warning' })
        await rollbackSnapshot(row.version)
        this.$message.success('已回滚')
        this.loadAll()
      } catch (error) {
        if (error !== 'cancel') this.$message.error((error && error.message) || '回滚失败')
      }
    },
    async handleDiff() {
      if (!this.leftVersion || !this.rightVersion) return this.$message.warning('请填写两个版本')
      try {
        this.diff = await diffSnapshots(this.leftVersion, this.rightVersion)
      } catch (error) {
        this.$message.error((error && error.message) || '对比失败')
      }
    },
    async handleImpact() {
      if (!this.impactAssetId) return this.$message.warning('请填写资产 ID')
      try {
        this.impact = await impactAnalysis(this.impactAssetType, this.impactAssetId)
      } catch (error) {
        this.$message.error((error && error.message) || '分析失败')
      }
    },
  },
}
</script>

<style scoped>
.semantic-page { padding: 16px; }
.semantic-page__header { display: flex; align-items: flex-start; justify-content: space-between; margin-bottom: 16px; }
.semantic-page__title { margin: 0; font-size: 20px; font-weight: 600; color: #303133; }
.semantic-page__subtitle { margin: 6px 0 0; color: #909399; font-size: 13px; }
.tab-toolbar { margin-bottom: 12px; }
.danger-text { color: #f56c6c; }
.section { margin-top: 16px; }
.section__header { font-weight: 600; margin-bottom: 8px; }
.diff-bar { display: flex; gap: 8px; max-width: 720px; }
.panel { border: 1px solid #ebeef5; border-radius: 4px; background: #fff; }
.panel__header { padding: 10px 12px; border-bottom: 1px solid #ebeef5; font-weight: 600; }
.panel__body { padding: 12px; min-height: 80px; }
.muted-text { color: #909399; font-size: 13px; }
.impact-form { margin-bottom: 12px; }
</style>