import axios from 'axios'
import type { HealthResponse, ModelInfoResponse, OutlineResponse } from './types'
import {
  mockExpandContent,
  mockExpandContentBatch,
  mockGenerateOutline,
  mockGetHealth,
  mockGetModelInfo,
  mockQueryRag,
  mockSearchKnowledge,
  mockSearchKnowledgeBatch,
  mockSwitchModel,
  mockUploadDocument
} from './mockApi'

const baseURL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000'
const useMock = (import.meta.env.VITE_USE_MOCK ?? 'true') === 'true'

export const api = axios.create({
  baseURL,
  timeout: 200000
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

export async function uploadDocument(filePath: string) {
  if (useMock) {
    return mockUploadDocument(filePath)
  }
  const { data } = await api.post('/api/rag/upload', { file_path: filePath })
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
    return mockExpandContent(outlineNode, context)
  }
  const { data } = await api.post('/api/generator/content', {
    outline_node: outlineNode,
    context
  })
  return data as { success: boolean; content: string; message?: string }
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
  message?: string
}

export async function expandContentBatch(
  items: BatchContentItemPayload[],
  context?: string,
  maxWorkers?: number
) {
  if (useMock) {
    return mockExpandContentBatch(items, context)
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
