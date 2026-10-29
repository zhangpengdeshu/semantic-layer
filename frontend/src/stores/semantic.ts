/**
 * 语义层共享状态：主题域 / 模型等跨页面引用数据缓存。
 * 页面通过 useSemanticStore().fetchModels() 获取，避免重复请求。
 */
/* eslint-disable camelcase */
import { defineStore } from 'pinia'

import { listDomains, listModels } from '@/api/semantic'

const CACHE_TTL = 60 * 1000

function expired(loadedAt: number) {
  return !loadedAt || Date.now() - loadedAt > CACHE_TTL
}

export const useSemanticStore = defineStore('semantic', {
  state: () => ({
    domains: [] as any[],
    domainsLoadedAt: 0,
    models: [] as any[],
    modelsLoadedAt: 0,
    loading: { domains: false, models: false },
    error: '',
  }),
  getters: {
    domainOptions: (state) => state.domains.map((item) => ({ value: item.domain_id, label: item.name })),
    modelOptions: (state) =>
      state.models.map((item) => ({ value: item.model_id, label: item.business_name || item.name })),
    domainNameById: (state) => (id: number) => {
      const match = state.domains.find((item) => item.domain_id === id)
      return match ? match.name : '-'
    },
  },
  actions: {
    async fetchDomains(options: { force?: boolean } = {}) {
      if (!options.force && !expired(this.domainsLoadedAt)) return this.domains
      this.loading.domains = true
      try {
        const data = await listDomains({ page: 1, page_size: 200 })
        this.domains = data.items || []
        this.domainsLoadedAt = Date.now()
        return this.domains
      } catch (error: any) {
        this.error = (error && error.message) || '加载主题域失败'
        throw error
      } finally {
        this.loading.domains = false
      }
    },
    async fetchModels(options: { force?: boolean } = {}) {
      if (!options.force && !expired(this.modelsLoadedAt)) return this.models
      this.loading.models = true
      try {
        const data = await listModels({ page: 1, page_size: 200 })
        this.models = data.items || []
        this.modelsLoadedAt = Date.now()
        return this.models
      } catch (error: any) {
        this.error = (error && error.message) || '加载模型失败'
        throw error
      } finally {
        this.loading.models = false
      }
    },
  },
})