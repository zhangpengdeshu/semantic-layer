<template>
  <el-container class="app-shell">
    <el-aside class="app-aside" width="220px">
      <div class="app-brand">
        <div class="app-brand__logo">SL</div>
        <div>
          <div class="app-brand__title">语义层</div>
          <div class="app-brand__sub">Semantic Layer</div>
        </div>
      </div>

      <el-menu :default-active="activeMenu" router class="app-menu">
        <el-menu-item index="/workbench">
          <el-icon><DataBoard /></el-icon>
          <span>{{ $t('semanticLayer.workbench') }}</span>
        </el-menu-item>
        <el-menu-item index="/domains">
          <el-icon><Grid /></el-icon>
          <span>{{ $t('semanticLayer.domains') }}</span>
        </el-menu-item>
        <el-menu-item index="/models">
          <el-icon><Document /></el-icon>
          <span>{{ $t('semanticLayer.models') }}</span>
        </el-menu-item>
        <el-menu-item index="/metrics">
          <el-icon><TrendCharts /></el-icon>
          <span>{{ $t('semanticLayer.metrics') }}</span>
        </el-menu-item>
        <el-menu-item index="/bindings">
          <el-icon><Connection /></el-icon>
          <span>{{ $t('semanticLayer.bindings') }}</span>
        </el-menu-item>
        <el-menu-item index="/knowledge">
          <el-icon><Reading /></el-icon>
          <span>{{ $t('semanticLayer.knowledge') }}</span>
        </el-menu-item>
        <el-menu-item index="/release">
          <el-icon><CircleCheck /></el-icon>
          <span>{{ $t('semanticLayer.release') }}</span>
        </el-menu-item>
        <el-menu-item index="/admin">
          <el-icon><Setting /></el-icon>
          <span>{{ $t('semanticLayer.admin') }}</span>
        </el-menu-item>
      </el-menu>

      <div class="app-aside__footer">v0.1.0</div>
    </el-aside>

    <el-container>
      <el-header class="app-header">
        <div class="app-header__title">{{ pageTitle }}</div>
        <div class="app-header__right">
          <el-select v-model="locale" size="small" class="app-header__locale" @change="changeLocale">
            <el-option label="简体中文" value="zh-CN" />
            <el-option label="English" value="en" />
          </el-select>
        </div>
      </el-header>

      <el-main class="app-main">
        <router-view />
      </el-main>
    </el-container>
  </el-container>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { useRoute } from 'vue-router'
import { useI18n } from 'vue-i18n'

const route = useRoute()
const { t, locale } = useI18n()

const activeMenu = computed(() => {
  const path = route.path
  if (path.startsWith('/models')) return '/models'
  if (path.startsWith('/bindings')) return '/bindings'
  return path
})

const pageTitle = computed(() => {
  const key = route.meta && (route.meta.title as string | undefined)
  return key ? t(key) : ''
})

function changeLocale(value: string) {
  locale.value = value
  localStorage.setItem('semantic-layer.locale', value)
  document.documentElement.lang = value
}
</script>

<style scoped>
.app-shell {
  min-height: 100vh;
}

.app-aside {
  display: flex;
  flex-direction: column;
  background: #1f2d3d;
  color: #c0c4cc;
}

.app-brand {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 18px 16px;
  border-bottom: 1px solid rgba(255, 255, 255, 0.08);
}

.app-brand__logo {
  width: 36px;
  height: 36px;
  border-radius: 8px;
  background: linear-gradient(135deg, #409eff, #36cfc9);
  color: #fff;
  font-weight: 700;
  display: flex;
  align-items: center;
  justify-content: center;
}

.app-brand__title {
  color: #fff;
  font-size: 16px;
  font-weight: 600;
  line-height: 1.2;
}

.app-brand__sub {
  color: #909399;
  font-size: 12px;
  margin-top: 2px;
}

.app-menu {
  flex: 1;
  border-right: none;
  background: transparent;
  padding-top: 8px;
}

.app-menu :deep(.el-menu-item) {
  color: #c0c4cc;
}

.app-menu :deep(.el-menu-item:hover) {
  background: rgba(255, 255, 255, 0.06);
  color: #fff;
}

.app-menu :deep(.el-menu-item.is-active) {
  background: rgba(64, 158, 255, 0.18);
  color: #fff;
}

.app-aside__footer {
  padding: 12px 16px;
  font-size: 12px;
  color: #606266;
  border-top: 1px solid rgba(255, 255, 255, 0.08);
}

.app-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  background: #fff;
  border-bottom: 1px solid #ebeef5;
  height: 56px;
}

.app-header__title {
  font-size: 15px;
  font-weight: 600;
  color: #303133;
}

.app-header__right {
  display: flex;
  align-items: center;
  gap: 12px;
}

.app-header__locale {
  width: 120px;
}

.app-main {
  padding: 0;
  background: #f5f7fa;
}
</style>