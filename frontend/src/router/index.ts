import { createRouter, createWebHistory, type RouteRecordRaw } from 'vue-router'

import DefaultLayout from '@/layouts/DefaultLayout.vue'

const routes: RouteRecordRaw[] = [
  {
    path: '/',
    component: DefaultLayout,
    redirect: '/workbench',
    children: [
      {
        path: 'workbench',
        name: 'SemanticWorkbench',
        component: () => import('@/views/workbench/index.vue'),
        meta: { title: 'semanticLayer.workbench' },
      },
      {
        path: 'domains',
        name: 'SemanticDomains',
        component: () => import('@/views/domains/index.vue'),
        meta: { title: 'semanticLayer.domains' },
      },
      {
        path: 'models',
        name: 'SemanticModels',
        component: () => import('@/views/models/index.vue'),
        meta: { title: 'semanticLayer.models' },
      },
      {
        path: 'models/create',
        name: 'SemanticModelCreate',
        component: () => import('@/views/models/create.vue'),
        meta: { title: 'semanticLayer.modelCreate' },
      },
      {
        path: 'models/:id',
        name: 'SemanticModelDetail',
        component: () => import('@/views/models/detail.vue'),
        meta: { title: 'semanticLayer.modelDetail' },
      },
      {
        path: 'metrics',
        name: 'SemanticMetrics',
        component: () => import('@/views/metrics/index.vue'),
        meta: { title: 'semanticLayer.metrics' },
      },
      {
        path: 'bindings',
        name: 'SemanticBindings',
        component: () => import('@/views/bindings/index.vue'),
        meta: { title: 'semanticLayer.bindings' },
      },
      {
        path: 'bindings/create',
        name: 'SemanticBindingCreate',
        component: () => import('@/views/bindings/create.vue'),
        meta: { title: 'semanticLayer.bindingCreate' },
      },
      {
        path: 'bindings/:id/mapping',
        name: 'SemanticBindingMapping',
        component: () => import('@/views/bindings/mapping.vue'),
        meta: { title: 'semanticLayer.bindingMapping' },
      },
      {
        path: 'knowledge',
        name: 'SemanticKnowledge',
        component: () => import('@/views/knowledge/index.vue'),
        meta: { title: 'semanticLayer.knowledge' },
      },
      {
        path: 'release',
        name: 'SemanticRelease',
        component: () => import('@/views/release/index.vue'),
        meta: { title: 'semanticLayer.release' },
      },
      {
        path: 'admin',
        name: 'SemanticAdmin',
        component: () => import('@/views/admin/index.vue'),
        meta: { title: 'semanticLayer.admin' },
      },
    ],
  },
  {
    path: '/:pathMatch(.*)*',
    redirect: '/workbench',
  },
]

const router = createRouter({
  history: createWebHistory(import.meta.env.BASE_URL),
  routes,
})

router.afterEach((to) => {
  const key = to.meta && (to.meta.title as string | undefined)
  document.title = key ? `语义层 · ${key}` : '语义层 · Semantic Layer'
})

export default router