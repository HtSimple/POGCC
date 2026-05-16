export type FlowKey = 'task' | 'references' | 'outline' | 'pages' | 'markdown' | 'history'

export type ReferenceStatus = 'pending' | 'parsing' | 'stored' | 'failed'

export type FactCheckStatus = 'pending' | 'passed' | 'review' | 'risk'

export interface ProjectForm {
  topic: string
  scene: string
  pageCount: number
  audience: string
  requirements: string
}

export interface ReferenceDoc {
  id: string
  filePath: string
  status: ReferenceStatus
  docId?: string
  message?: string
}

export interface SlidePage {
  id: string
  sectionTitle: string
  title: string
  goal: string
  bullets: string[]
  knowledge: string
  content: string
  notes: string
  factCheckStatus: FactCheckStatus
  factCheckMessage: string
}

export interface ProjectRecord {
  id: string
  title: string
  createdAt: string
  updatedAt: string
  form: ProjectForm
  references: ReferenceDoc[]
  slides: SlidePage[]
  markdown: string
}

export interface OutlineSection {
  title?: string
  subsections?: string[]
}

export interface OutlineResponse {
  title?: string
  sections?: OutlineSection[]
}

export interface HealthResponse {
  status: string
  version: string
}

export interface ModelInfoResponse {
  current_provider: string
  available_providers: string[]
}
