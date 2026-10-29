<template>
  <div class="semantic-page">
    <div class="semantic-page__header">
      <div>
        <h2 class="semantic-page__title">主题域</h2>
        <p class="semantic-page__subtitle">按业务主题组织语义模型，统一负责人与协作成员</p>
      </div>
      <div class="semantic-page__actions">
        <el-button :loading="loading" @click="load">刷新</el-button>
        <el-button type="primary" @click="openCreate">新建主题域</el-button>
      </div>
    </div>

    <div class="filter-bar">
      <el-input
        v-model.trim="filters.q" placeholder="搜索主题域" clearable class="filter-item filter-item--md"
        @keyup.enter="load" @clear="load" />
      <el-button type="primary" @click="load">查询</el-button>
    </div>

    <el-alert v-if="error" type="error" show-icon :title="error" @close="error = ''" />

    <div class="table-card">
      <div class="table-card__header">
        <span class="table-card__title">主题域列表</span>
        <span class="muted-text">共 {{ total }} 个</span>
      </div>
      <div class="table-card__body">
        <el-table v-loading="loading" :data="items" size="small" row-key="domain_id" empty-text="暂无主题域">
          <el-table-column prop="name" label="名称" min-width="160" show-overflow-tooltip />
          <el-table-column prop="description" label="描述" min-width="240" show-overflow-tooltip />
          <el-table-column prop="owner" label="负责人" width="120" />
          <el-table-column prop="model_count" label="模型数" width="90" align="center" />
          <el-table-column label="状态" width="110">
            <template #default="{ row }">
              <StatusBadge :status="row.status" />
            </template>
          </el-table-column>
          <el-table-column label="操作" width="140" fixed="right">
            <template #default="{ row }">
              <el-button link @click="openEdit(row)">编辑</el-button>
              <el-button link class="danger-text" @click="handleDelete(row)">删除</el-button>
            </template>
          </el-table-column>
        </el-table>
      </div>
      <div class="table-card__footer">
        <el-pagination
          background v-model:current-page="page" :page-size="pageSize" :page-sizes="[10, 20, 50]"
          :total="total" layout="total, sizes, prev, pager, next" @size-change="handleSizeChange"
          @current-change="load" />
      </div>
    </div>

    <el-dialog :title="form.domain_id ? '编辑主题域' : '新建主题域'" v-model="dialogVisible" width="520px">
      <el-form ref="form" :model="form" label-width="90px">
        <el-form-item label="名称" required>
          <el-input v-model.trim="form.name" placeholder="如：零售经营" />
        </el-form-item>
        <el-form-item label="描述">
          <el-input v-model.trim="form.description" type="textarea" :rows="3" />
        </el-form-item>
        <el-form-item label="负责人">
          <el-input v-model.trim="form.owner" placeholder="工号或邮箱" />
        </el-form-item>
        <el-form-item label="成员">
          <el-select
            v-model="form.members" multiple filterable allow-create default-first-option
            placeholder="输入用户 ID 后回车" class="form-block" />
        </el-form-item>
      </el-form>
      <template #footer>
        <span>
          <el-button @click="dialogVisible = false">取消</el-button>
          <el-button type="primary" :loading="saving" @click="handleSave">保存</el-button>
        </span>
      </template>
    </el-dialog>
  </div>
</template>

<script lang="ts">
/* eslint-disable camelcase */
import { listDomains, createDomain, updateDomain, deleteDomain } from '@/api/semantic'
import StatusBadge from '../components/StatusBadge.vue'

export default {
  name: 'SemanticDomains',
  components: { StatusBadge },
  data(): any {
    return {
      loading: false,
      saving: false,
      error: '',
      items: [],
      total: 0,
      page: 1,
      pageSize: 20,
      filters: { q: '' },
      dialogVisible: false,
      form: this.emptyForm(),
    }
  },
  created() {
    this.load()
  },
  methods: {
    emptyForm() {
      return { domain_id: null, name: '', description: '', owner: '', members: [] }
    },
    async load() {
      this.loading = true
      this.error = ''
      try {
        const data = await listDomains({ q: this.filters.q, page: this.page, page_size: this.pageSize })
        this.items = data.items || []
        this.total = data.total || 0
      } catch (error) {
        this.error = (error && error.message) || '加载主题域失败'
      } finally {
        this.loading = false
      }
    },
    handleSizeChange(size) {
      this.pageSize = size
      this.page = 1
      this.load()
    },
    openCreate() {
      this.form = this.emptyForm()
      this.dialogVisible = true
    },
    openEdit(row) {
      this.form = {
        domain_id: row.domain_id,
        name: row.name,
        description: row.description,
        owner: row.owner,
        members: (row.members || []).map(item => item.user_id),
      }
      this.dialogVisible = true
    },
    async handleSave() {
      if (!this.form.name) {
        this.$message.warning('名称不能为空')
        return
      }
      this.saving = true
      try {
        const payload = {
          name: this.form.name,
          description: this.form.description,
          owner: this.form.owner,
          members: (this.form.members || []).map(userId => ({ user_id: userId, role: 'modeler' })),
        }
        if (this.form.domain_id) {
          await updateDomain(this.form.domain_id, payload)
        } else {
          await createDomain(payload)
        }
        this.dialogVisible = false
        this.$message.success('保存成功')
        this.load()
      } catch (error) {
        this.$message.error((error && error.message) || '保存失败')
      } finally {
        this.saving = false
      }
    },
    async handleDelete(row) {
      try {
        await this.$confirm(`确定删除主题域「${row.name}」？`, '提示', { type: 'warning' })
        await deleteDomain(row.domain_id)
        this.$message.success('删除成功')
        this.load()
      } catch (error) {
        if (error !== 'cancel') this.$message.error((error && error.message) || '删除失败')
      }
    },
  },
}
</script>