/**
 * 语义层 API。
 * 统一走后端 `/api/semantic/v1` 与 `/api/ask`；兼容网关包裹体与裸 JSON。
 */
/* eslint-disable camelcase */
import { request, unwrap, unwrapPage } from './client'

const BASE = '/api/semantic/v1'

type Params = Record<string, any>

function call(method: string, url: string, payload?: unknown, params?: Params) {
  return request(method, url, payload, params)
}

// ---------------------------------------------------------------- 主题域
export function listDomains(params?: Params) {
  return call('get', `${BASE}/domains`, undefined, params).then(unwrapPage)
}
export function getDomain(domainId: number) {
  return call('get', `${BASE}/domains/${domainId}`).then(unwrap)
}
export function createDomain(data: Params) {
  return call('post', `${BASE}/domains`, data).then(unwrap)
}
export function updateDomain(domainId: number, data: Params) {
  return call('patch', `${BASE}/domains/${domainId}`, data).then(unwrap)
}
export function deleteDomain(domainId: number) {
  return call('delete', `${BASE}/domains/${domainId}`).then(unwrap)
}

// ---------------------------------------------------------------- 模型
export function listModels(params?: Params) {
  return call('get', `${BASE}/models`, undefined, params).then(unwrapPage)
}
export function getModel(modelId: number) {
  return call('get', `${BASE}/models/${modelId}`).then(unwrap)
}
export function createModel(data: Params) {
  return call('post', `${BASE}/models`, data).then(unwrap)
}
export function updateModel(modelId: number, data: Params) {
  return call('patch', `${BASE}/models/${modelId}`, data).then(unwrap)
}
export function deleteModel(modelId: number) {
  return call('delete', `${BASE}/models/${modelId}`).then(unwrap)
}
export function setGrain(modelId: number, fieldIds: number[]) {
  return call('put', `${BASE}/models/${modelId}/grain`, { field_ids: fieldIds }).then(unwrap)
}

// ---------------------------------------------------------------- 字段
export function listFields(modelId: number) {
  return call('get', `${BASE}/models/${modelId}/fields`).then(unwrap)
}
export function createField(modelId: number, data: Params) {
  return call('post', `${BASE}/models/${modelId}/fields`, data).then(unwrap)
}
export function batchCreateFields(modelId: number, fields: Params[]) {
  return call('post', `${BASE}/models/${modelId}/fields:batch`, { fields }).then(unwrap)
}
export function updateField(fieldId: number, data: Params) {
  return call('patch', `${BASE}/fields/${fieldId}`, data).then(unwrap)
}
export function deleteField(fieldId: number) {
  return call('delete', `${BASE}/fields/${fieldId}`).then(unwrap)
}

// ---------------------------------------------------------------- 维度
export function listDimensions(modelId: number) {
  return call('get', `${BASE}/models/${modelId}/dimensions`).then(unwrap)
}
export function createDimension(modelId: number, data: Params) {
  return call('post', `${BASE}/models/${modelId}/dimensions`, data).then(unwrap)
}
export function updateDimension(dimensionId: number, data: Params) {
  return call('patch', `${BASE}/dimensions/${dimensionId}`, data).then(unwrap)
}
export function deleteDimension(dimensionId: number) {
  return call('delete', `${BASE}/dimensions/${dimensionId}`).then(unwrap)
}

// ---------------------------------------------------------------- 度量
export function listMeasures(modelId: number) {
  return call('get', `${BASE}/models/${modelId}/measures`).then(unwrap)
}
export function createMeasure(modelId: number, data: Params) {
  return call('post', `${BASE}/models/${modelId}/measures`, data).then(unwrap)
}
export function updateMeasure(measureId: number, data: Params) {
  return call('patch', `${BASE}/measures/${measureId}`, data).then(unwrap)
}
export function deleteMeasure(measureId: number) {
  return call('delete', `${BASE}/measures/${measureId}`).then(unwrap)
}

// ---------------------------------------------------------------- 关系
export function listRelationships(modelId: number) {
  return call('get', `${BASE}/models/${modelId}/relationships`).then(unwrap)
}
export function createRelationship(modelId: number, data: Params) {
  return call('post', `${BASE}/models/${modelId}/relationships`, data).then(unwrap)
}
export function updateRelationship(edgeId: number, data: Params) {
  return call('patch', `${BASE}/relationships/${edgeId}`, data).then(unwrap)
}
export function deleteRelationship(edgeId: number) {
  return call('delete', `${BASE}/relationships/${edgeId}`).then(unwrap)
}
export function relationshipSuggestions(modelId: number) {
  return call('get', `${BASE}/models/${modelId}/relationship-suggestions`).then(unwrap)
}

// ---------------------------------------------------------------- 指标
export function listMetrics(params?: Params) {
  return call('get', `${BASE}/metrics`, undefined, params).then(unwrapPage)
}
export function getMetric(metricId: number) {
  return call('get', `${BASE}/metrics/${metricId}`).then(unwrap)
}
export function createMetric(data: Params) {
  return call('post', `${BASE}/metrics`, data).then(unwrap)
}
export function updateMetric(metricId: number, data: Params) {
  return call('patch', `${BASE}/metrics/${metricId}`, data).then(unwrap)
}
export function deleteMetric(metricId: number) {
  return call('delete', `${BASE}/metrics/${metricId}`).then(unwrap)
}
export function validateMetric(metricId: number) {
  return call('post', `${BASE}/metrics/${metricId}/validation`).then(unwrap)
}
export function metricDependencyGraph(metricId: number) {
  return call('get', `${BASE}/metrics/${metricId}/dependency-graph`).then(unwrap)
}

// ---------------------------------------------------------------- 目录
export function listDatasets(params?: Params) {
  return call('get', `${BASE}/catalog/datasets`, undefined, params).then(unwrapPage)
}
export function getDataset(datasetId: number | string) {
  return call('get', `${BASE}/catalog/datasets/${datasetId}`).then(unwrap)
}
export function syncDatasets(data: Params) {
  return call('post', `${BASE}/catalog/datasets:sync`, data).then(unwrap)
}
export function listTables(params?: Params) {
  return call('get', `${BASE}/catalog/tables`, undefined, params).then(unwrapPage)
}
export function getTable(tableId: number) {
  return call('get', `${BASE}/catalog/tables/${tableId}`).then(unwrap)
}

// ---------------------------------------------------------------- 绑定
export function listBindings(modelId: number) {
  return call('get', `${BASE}/models/${modelId}/bindings`).then(unwrap)
}
export function getBinding(bindingId: number) {
  return call('get', `${BASE}/bindings/${bindingId}`).then(unwrap)
}
export function createBinding(modelId: number, data: Params) {
  return call('post', `${BASE}/models/${modelId}/bindings`, data).then(unwrap)
}
export function updateBinding(bindingId: number, data: Params) {
  return call('patch', `${BASE}/bindings/${bindingId}`, data).then(unwrap)
}
export function deleteBinding(bindingId: number) {
  return call('delete', `${BASE}/bindings/${bindingId}`).then(unwrap)
}
export function setPrimaryBinding(bindingId: number) {
  return call('post', `${BASE}/bindings/${bindingId}:set-primary`).then(unwrap)
}
export function getFieldMappings(bindingId: number) {
  return call('get', `${BASE}/bindings/${bindingId}/field-mappings`).then(unwrap)
}
export function bindingColumns(bindingId: number) {
  return call('get', `${BASE}/bindings/${bindingId}/columns`).then(unwrap)
}
export function saveFieldMappings(bindingId: number, items: Params[]) {
  return call('put', `${BASE}/bindings/${bindingId}/field-mappings`, { items }).then(unwrap)
}
export function autoMapBinding(bindingId: number) {
  return call('post', `${BASE}/bindings/${bindingId}/auto-map`).then(unwrap)
}
export function bindingDrift(bindingId: number) {
  return call('get', `${BASE}/bindings/${bindingId}/drift`).then(unwrap)
}

// ---------------------------------------------------------------- 校验与发布
export function listValidationRuns(params?: Params) {
  return call('get', `${BASE}/validation`, undefined, params).then(unwrap)
}
export function runModelValidation(modelId: number, level: string) {
  return call('post', `${BASE}/models/${modelId}/validation`, { level }).then(unwrap)
}
export function listModelValidation(modelId: number) {
  return call('get', `${BASE}/models/${modelId}/validation`).then(unwrap)
}
export function batchValidation(modelIds: number[], level: string) {
  return call('post', `${BASE}/validation/batch`, { model_ids: modelIds, level }).then(unwrap)
}
export function impactAnalysis(assetType: string, assetId: number) {
  return call('get', `${BASE}/validation/impact`, undefined, { asset_type: assetType, asset_id: assetId }).then(unwrap)
}
export function listCertifications(params?: Params) {
  return call('get', `${BASE}/certifications`, undefined, params).then(unwrap)
}
export function createCertification(data: Params) {
  return call('post', `${BASE}/certifications`, data).then(unwrap)
}
export function decideCertification(certificationId: number, data: Params) {
  return call('post', `${BASE}/certifications/${certificationId}/decision`, data).then(unwrap)
}
export function listSnapshots(params?: Params) {
  return call('get', `${BASE}/snapshots`, undefined, params).then(unwrap)
}
export function buildSnapshot() {
  return call('post', `${BASE}/snapshots`).then(unwrap)
}
export function activeSnapshot() {
  return call('get', `${BASE}/snapshots/active`).then(unwrap)
}
export function diffSnapshots(left: unknown, right: unknown) {
  return call('get', `${BASE}/snapshots/diff`, undefined, { left, right }).then(unwrap)
}
export function rollbackSnapshot(version: string) {
  return call('post', `${BASE}/snapshots/${version}/rollback`).then(unwrap)
}

// ---------------------------------------------------------------- 知识
export function listTerms(params?: Params) {
  return call('get', `${BASE}/terms`, undefined, params).then(unwrap)
}
export function createTerm(data: Params) {
  return call('post', `${BASE}/terms`, data).then(unwrap)
}
export function updateTerm(termId: number, data: Params) {
  return call('patch', `${BASE}/terms/${termId}`, data).then(unwrap)
}
export function deleteTerm(termId: number) {
  return call('delete', `${BASE}/terms/${termId}`).then(unwrap)
}
export function listSynonyms(params?: Params) {
  return call('get', `${BASE}/synonyms`, undefined, params).then(unwrap)
}
export function createSynonym(data: Params) {
  return call('post', `${BASE}/synonyms`, data).then(unwrap)
}
export function updateSynonym(synonymId: number, data: Params) {
  return call('patch', `${BASE}/synonyms/${synonymId}`, data).then(unwrap)
}
export function deleteSynonym(synonymId: number) {
  return call('delete', `${BASE}/synonyms/${synonymId}`).then(unwrap)
}
export function listRules() {
  return call('get', `${BASE}/rules`).then(unwrap)
}
export function createRule(data: Params) {
  return call('post', `${BASE}/rules`, data).then(unwrap)
}
export function updateRule(ruleId: number, data: Params) {
  return call('patch', `${BASE}/rules/${ruleId}`, data).then(unwrap)
}
export function deleteRule(ruleId: number) {
  return call('delete', `${BASE}/rules/${ruleId}`).then(unwrap)
}
export function getContext(assetType: string, assetId: number) {
  return call('get', `${BASE}/context/${assetType}/${assetId}`).then(unwrap)
}
export function saveContext(assetType: string, assetId: number, data: Params) {
  return call('put', `${BASE}/context/${assetType}/${assetId}`, data).then(unwrap)
}
export function recallTest(question: string) {
  return call('post', `${BASE}/recall-test`, undefined, { question }).then(unwrap)
}

// ---------------------------------------------------------------- 管理
export function workbench() {
  return call('get', `${BASE}/admin/workbench`).then(unwrap)
}
export function listUsers() {
  return call('get', `${BASE}/admin/users`).then(unwrap)
}
export function listRoles() {
  return call('get', `${BASE}/admin/roles`).then(unwrap)
}
export function listPermissions() {
  return call('get', `${BASE}/admin/permissions`).then(unwrap)
}
export function listAudit(params?: Params) {
  return call('get', `${BASE}/admin/audit`, undefined, params).then(unwrap)
}
export function listQueries(params?: Params) {
  return call('get', `${BASE}/admin/queries`, undefined, params).then(unwrap)
}

// ---------------------------------------------------------------- 问数
export function askQuestion(data: Params) {
  return call('post', '/api/ask', data).then(unwrap)
}
export function compilePreview(data: Params) {
  return call('post', '/api/ask/compile', data).then(unwrap)
}
export function queryExplain(requestId: string) {
  return call('get', `/api/ask/${requestId}/explain`).then(unwrap)
}