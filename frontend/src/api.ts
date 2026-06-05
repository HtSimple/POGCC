import axios from 'axios'
import type {
  ApiLimitUpdate,
  ApiUsageSummary,
  HealthResponse,
  ModelInfoResponse,
  OutlineResponse,
  PageContentProtocol
} from './types'
import {
  mockExpandContent,
  mockExpandContentBatch,
  mockGenerateNotes,
  mockGenerateOutline,
  mockGetHealth,
  mockGetModelInfo,
  mockQueryRag,
  mockReviseContent,
  mockSearchKnowledge,
  mockSearchKnowledgeBatch,
  mockSwitchModel,
  mockUploadDocument
} from './mockApi'

const baseURL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000'
const useMock = (import.meta.env.VITE_USE_MOCK ?? 'true') === 'true'

export const api = axios.create({
  baseURL,
  timeout: 300000
})

export function getApiBaseUrl() {
  return useMock ? 'Mock 数据模式' : baseURL
}

export function isUsingMockApi() {
  return useMock
}

export async function getHealth() {
  if (useMock) {
    return mockGetHealth()
  }
  const { data } = await api.get<HealthResponse>('/health')
  return data
}

export async function getModelInfo() {
  if (useMock) {
    return mockGetModelInfo()
  }
  const { data } = await api.get<ModelInfoResponse>('/api/model/info')
  return data
}

export async function switchModel(provider: string) {
  if (useMock) {
    return mockSwitchModel(provider)
  }
  const { data } = await api.post('/api/model/switch', { provider })
  return data as { success: boolean; current_provider: string; message?: string }
}

export async function getApiUsage() {
  const { data } = await api.get<ApiUsageSummary>('/api/cost/usage')
  return data
}

export async function updateApiLimits(provider: string, limits: ApiLimitUpdate) {
  const { data } = await api.put(`/api/cost/limits/${provider}`, limits)
  return data as { success: boolean; message?: string }
}

export async function resetApiUsage(provider?: string) {
  const { data } = await api.post('/api/cost/reset', { provider: provider || null })
  return data as { success: boolean; message?: string }
}

export async function uploadDocument(filePath: string) {
  if (useMock) {
    return mockUploadDocument(filePath)
  }
  const { data } = await api.post('/api/rag/upload', { file_path: filePath })
  return data as { success: boolean; doc_id: string; message?: string }
}

export async function uploadDocumentFile(file: File) {
  if (useMock) {
    return mockUploadDocument(file.name)
  }
  const formData = new FormData()
  formData.append('file', file)
  const { data } = await api.post('/api/rag/upload/file', formData, {
    headers: { 'Content-Type': 'multipart/form-data' }
  })
  return data as { success: boolean; doc_id: string; message?: string }
}

export async function generateOutline(topic: string, requirements: string) {
  if (useMock) {
    return mockGenerateOutline(topic, requirements)
  }
  const { data } = await api.post('/api/generator/outline', { topic, requirements })
  return data as { success: boolean; outline: OutlineResponse; message?: string }
}

export async function searchKnowledge(topic: string, refineKnowledge = false) {
  if (useMock) {
    return mockSearchKnowledge(topic)
  }
  const { data } = await api.post('/api/search/knowledge', {
    topic,
    refine_knowledge: refineKnowledge
  })
  return data as { success: boolean; knowledge: string; message?: string }
}

export interface BatchKnowledgeItemPayload {
  index: number
  id?: string
  query: string
}

export interface BatchKnowledgeResultItem {
  index: number
  id?: string
  success: boolean
  knowledge: string
  has_sources?: boolean
  message?: string
}

export async function searchKnowledgeBatch(
  items: BatchKnowledgeItemPayload[],
  refineKnowledge = false,
  maxWorkers?: number
) {
  if (useMock) {
    return mockSearchKnowledgeBatch(items, refineKnowledge)
  }
  const { data } = await api.post('/api/search/knowledge/batch', {
    items,
    refine_knowledge: refineKnowledge,
    max_workers: maxWorkers
  })
  return data as {
    success: boolean
    results: BatchKnowledgeResultItem[]
    message?: string
    elapsed_sec?: number
  }
}

export async function queryRag(query: string) {
  if (useMock) {
    return mockQueryRag(query)
  }
  const { data } = await api.post('/api/rag/query', { query })
  return data as { success: boolean; answer: string; message?: string }
}

export async function expandContent(outlineNode: Record<string, unknown>, context: string) {
  if (useMock) {
    return mockExpandContent(outlineNode, context) as Promise<{
      success: boolean
      content: string
      page_content?: PageContentProtocol | null
      message?: string
    }>
  }
  const { data } = await api.post('/api/generator/content', {
    outline_node: outlineNode,
    context
  })
  return data as { success: boolean; content: string; page_content?: PageContentProtocol | null; message?: string }
}

function clipField(value: string | undefined, max: number) {
  const text = (value ?? '').trim()
  if (!text) {
    return undefined
  }
  return text.length <= max ? text : text.slice(0, max)
}

export interface ReviseContentPayload {
  outline_node: Record<string, unknown>
  current_content: string
  revision_suggestion: string
}

const REVISE_FIELD_LIMITS = {
  current_content: 3000,
  revision_suggestion: 1000
} as const

export function normalizeRevisePayload(payload: ReviseContentPayload): ReviseContentPayload | null {
  const current_content = clipField(payload.current_content, REVISE_FIELD_LIMITS.current_content)
  const revision_suggestion = clipField(payload.revision_suggestion, REVISE_FIELD_LIMITS.revision_suggestion)
  if (!current_content || !revision_suggestion) {
    return null
  }
  return {
    outline_node: payload.outline_node,
    current_content,
    revision_suggestion
  }
}

export async function reviseContent(payload: ReviseContentPayload) {
  const body = normalizeRevisePayload(payload)
  if (!body) {
    return {
      success: false,
      content: '',
      message: '正文或修改建议不能为空'
    }
  }
  if (useMock) {
    return mockReviseContent(body)
  }
  const { data } = await api.post('/api/generator/content/revise/text', body)
  return data as { success: boolean; content: string; message?: string }
}

export interface GenerateNotesPayload {
  project_id?: string
  slide_id: string
  slide_title: string
  slide_content: string
  knowledge_evidence?: string
  style_requirement?: string
}

/** 与后端 GenerateNotesRequest 字段长度一致，避免 422 */
const NOTES_FIELD_LIMITS = {
  slide_id: 80,
  slide_title: 120,
  slide_content: 3000,
  knowledge_evidence: 6000,
  style_requirement: 1000
} as const

export function normalizeNotesPayload(payload: GenerateNotesPayload): GenerateNotesPayload | null {
  const slide_content = clipField(payload.slide_content, NOTES_FIELD_LIMITS.slide_content)
  if (!slide_content) {
    return null
  }
  const slide_id = clipField(payload.slide_id, NOTES_FIELD_LIMITS.slide_id)
  const slide_title = clipField(payload.slide_title, NOTES_FIELD_LIMITS.slide_title)
  if (!slide_id || !slide_title) {
    return null
  }
  return {
    project_id: clipField(payload.project_id, 80),
    slide_id,
    slide_title,
    slide_content,
    knowledge_evidence: clipField(payload.knowledge_evidence, NOTES_FIELD_LIMITS.knowledge_evidence),
    style_requirement: clipField(payload.style_requirement, NOTES_FIELD_LIMITS.style_requirement)
  }
}

export function formatApiError(error: unknown): string {
  if (!axios.isAxiosError(error)) {
    return error instanceof Error ? error.message : '操作失败'
  }
  const status = error.response?.status
  const detail = error.response?.data?.detail
  if (status === 422) {
    if (Array.isArray(detail) && detail.length > 0) {
      const item = detail[0] as { loc?: unknown[]; msg?: string }
      const field = Array.isArray(item.loc) ? item.loc.filter((x) => x !== 'body').join('.') : ''
      const msg = item.msg || '参数校验失败'
      return field ? `请求无效（${field}）：${msg}` : `请求无效：${msg}`
    }
    return '请求参数无效：正文不能为空，或标题/正文/检索资料超出长度限制'
  }
  const message = error.response?.data?.message
  if (typeof message === 'string' && message.trim()) {
    return message
  }
  return error.message || '操作失败'
}

export async function generateNotes(payload: GenerateNotesPayload) {
  const body = normalizeNotesPayload(payload)
  if (!body) {
    return { success: false, notes: '', message: '页面正文为空，请先生成或填写正文' }
  }
  if (useMock) {
    return mockGenerateNotes(body)
  }
  const { data } = await api.post('/api/generator/notes', body)
  return data as { success: boolean; notes: string; message?: string }
}

export interface BatchContentItemPayload {
  index: number
  id?: string
  outline_node: Record<string, unknown>
  context?: string
}

export interface BatchContentResultItem {
  index: number
  id?: string
  success: boolean
  content: string
  page_content?: PageContentProtocol | null
  message?: string
}

export async function expandContentBatch(
  items: BatchContentItemPayload[],
  context?: string,
  maxWorkers?: number
) {
  if (useMock) {
    return mockExpandContentBatch(items, context) as Promise<{
      success: boolean
      results: BatchContentResultItem[]
      message?: string
      elapsed_sec?: number
    }>
  }
  const { data } = await api.post('/api/generator/content/batch', {
    items,
    context,
    max_workers: maxWorkers
  })
  return data as {
    success: boolean
    results: BatchContentResultItem[]
    message?: string
    elapsed_sec?: number
  }
}
