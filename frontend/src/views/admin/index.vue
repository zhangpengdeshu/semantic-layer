<template>
  <div class="semantic-page">
    <div class="semantic-page__header">
      <div>
        <h2 class="semantic-page__title">系统管理</h2>
        <p class="semantic-page__subtitle">语义层成员、权限、审计与问数监控</p>
      </div>
      <el-button :loading="loading" @click="loadAll">刷新</el-button>
    </div>

    <el-alert v-if="error" type="error" show-icon :title="error" @close="error = ''" />

    <el-tabs v-model="activeTab" type="border-card">
      <el-tab-pane label="成员与角色" name="members">
        <el-row :gutter="16">
          <el-col :span="12">
            <div class="panel">
              <div class="panel__header">用户</div>
              <el-table :data="users" size="small" border empty-text="暂无用户">
                <el-table-column prop="user_id" label="用户 ID" min-width="140" />
                <el-table-column prop="name" label="姓名" min-width="120" />
                <el-table-column prop="status" label="状态" width="100" />
              </el-table>
            </div>
          </el-col>
          <el-col :span="12">
            <div class="panel">
              <div class="panel__header">角色</div>
              <el-table :data="roles" size="small" border empty-text="暂无角色">
                <el-table-column prop="code" label="编码" width="130" />
                <el-table-column prop="name" label="名称" min-width="130" />
                <el-table-column prop="description" label="说明" min-width="180" show-overflow-tooltip />
              </el-table>
            </div>
          </el-col>
        </el-row>
      </el-tab-pane>

      <el-tab-pane label="权限策略" name="permissions">
        <el-table :data="permissions" size="small" border empty-text="暂无自定义权限">
          <el-table-column prop="subject_type" label="主体类型" width="110" />
          <el-table-column prop="subject_id" label="主体" width="130" />
          <el-table-column prop="asset_type" label="资产类型" width="110" />
          <el-table-column prop="asset_id" label="资产 ID" width="100" />
          <el-table-column prop="effect" label="效果" width="90" />
          <el-table-column prop="row_filter" label="行过滤" min-width="200" show-overflow-tooltip />
          <el-table-column prop="created_at" label="创建时间" width="190" />
        </el-table>
      </el-tab-pane>

      <el-tab-pane label="审计日志" name="audit">
        <el-table :data="audit" size="small" border empty-text="暂无审计记录">
          <el-table-column prop="actor" label="操作人" width="120" />
          <el-table-column prop="action" label="动作" min-width="160" />
          <el-table-column prop="object_type" label="对象类型" width="110" />
          <el-table-column prop="object_id" label="对象 ID" width="90" />
          <el-table-column prop="created_at" label="时间" width="190" />
        </el-table>
      </el-tab-pane>

      <el-tab-pane label="问数监控" name="queries">
        <el-table :data="queries" size="small" border empty-text="暂无问数记录">
          <el-table-column prop="question" label="问题" min-width="260" show-overflow-tooltip />
          <el-table-column prop="user_id" label="用户" width="120" />
          <el-table-column prop="status" label="状态" width="110">
            <template #default="{ row }"><StatusBadge :status="row.status" /></template>
          </el-table-column>
          <el-table-column prop="error_code" label="错误码" width="140" />
          <el-table-column prop="row_count" label="行数" width="80" />
          <el-table-column prop="elapsed_ms" label="耗时(ms)" width="100" />
          <el-table-column prop="created_at" label="时间" width="190" />
        </el-table>
      </el-tab-pane>
    </el-tabs>
  </div>
</template>

<script lang="ts">
/* eslint-disable camelcase */
import { listUsers, listRoles, listPermissions, listAudit, listQueries } from '@/api/semantic'
import StatusBadge from '../components/StatusBadge.vue'

export default {
  name: 'SemanticAdmin',
  components: { StatusBadge },
  data(): any {
    return {
      loading: false,
      error: '',
      activeTab: 'members',
      users: [],
      roles: [],
      permissions: [],
      audit: [],
      queries: [],
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
        const [users, roles, permissions, audit, queries] = await Promise.all([
          listUsers(),
          listRoles(),
          listPermissions(),
          listAudit({ limit: 100 }),
          listQueries({ limit: 100 }),
        ])
        this.users = users || []
        this.roles = roles || []
        this.permissions = permissions || []
        this.audit = audit || []
        this.queries = queries || []
      } catch (error) {
        this.error = (error && error.message) || '加载系统管理数据失败'
      } finally {
        this.loading = false
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
.panel { border: 1px solid #ebeef5; border-radius: 4px; background: #fff; }
.panel__header { padding: 10px 12px; border-bottom: 1px solid #ebeef5; font-weight: 600; }
</style>