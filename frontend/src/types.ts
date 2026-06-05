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
  protocolSlideId?: string
  slideNumber?: number
  slideRole?: SlideRole
  sectionId?: string
  slideRange?: SlideRange
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

export type SlideRole = 'cover' | 'toc' | 'transition' | 'content' | 'case-study' | 'summary' | 'qa' | 'appendix'

export interface SlideRange {
  start: number
  end: number
}

export interface OutlineProtocolSlide {
  slideId: string
  slideNumber: number
  slideRole: SlideRole
  slideTitle: string
  keyPoints: string[]
  notes?: string
}

export interface NarrativeOutlineSection {
  sectionId: string
  sectionTitle: string
  sectionObjective: string
  slideRange: SlideRange
  slides: OutlineProtocolSlide[]
}

export interface NarrativeOutline {
  protocolVersion: 'ppt-narrative-outline.v1'
  language: string
  presentationTitle: string
  targetSlideCount: number
  sections: NarrativeOutlineSection[]
}

export interface ResearchPolicy {
  triggerReason: 'user_requested' | 'insufficient_input' | 'fact_verification'
  depthLevel: 'light' | 'standard' | 'deep'
  sourcePriority: string[]
  maxSourcesPerSlide?: number
}

export interface KeyDataItem {
  label: string
  value: number
  unit: string
  year: number
  sourceRefId: string
}

export interface EvidenceItem {
  sourceRefId: string
  claim: string
  sourceTitle: string
  sourceType: string
  url: string
  publishDate: string
  credibility: 'high' | 'medium'
  quote?: string
}

export interface PageContentSlide {
  slideId: string
  slideNumber: number
  slideRole: SlideRole
  pageGoal: string
  slideTitle: string
  coreMessage: string
  displayBullets: string[]
  keyData: KeyDataItem[]
  evidencePack: EvidenceItem[]
  actionableTakeaway?: string
  speakerNotes: string
}

export interface PageContentProtocol {
  protocolVersion: 'ppt-page-content.v1'
  language: string
  presentationTitle: string
  researchPolicy: ResearchPolicy
  slides: PageContentSlide[]
}

export interface OutlineSubsection {
  title?: string
  goal?: string
  bullets?: string[]
}

export interface OutlineSection {
  title?: string
  subsections?: Array<string | OutlineSubsection>
}

export type OutlineResponse = NarrativeOutline | {
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

export interface ApiProviderUsage {
  call_limit: number | null
  token_limit: number | null
  cost_limit: number | null
  calls: number
  input_tokens: number
  output_tokens: number
  total_tokens: number
  estimated_cost: number
  currency: string
  total_duration_ms: number
  average_duration_ms: number
  failed_calls: number
  blocked_calls: number
  actual_token_calls: number
  estimated_token_calls: number
  last_called_at: string | null
}

export interface ApiCallRecord {
  provider: string
  model?: string | null
  retry_count: number
  token_source: 'actual' | 'estimated'
  success: boolean
  input_tokens: number
  output_tokens: number
  duration_ms: number
  estimated_cost: number
  currency: string
  error?: string | null
  called_at: string
}

export interface ApiUsageSummary {
  providers: Record<string, ApiProviderUsage>
  recent_calls: ApiCallRecord[]
  daily_usage: Record<string, Record<string, ApiDailyUsage>>
}

export interface ApiDailyUsage {
  calls: number
  input_tokens: number
  output_tokens: number
  total_tokens: number
  estimated_cost: number
  currency: string
}

export interface ApiLimitUpdate {
  call_limit: number | null
  token_limit: number | null
  cost_limit: number | null
}
