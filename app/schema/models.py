from typing import Literal, Optional

from pydantic import BaseModel, Field


SlideRole = Literal[
    "cover",
    "toc",
    "transition",
    "content",
    "case-study",
    "summary",
    "qa",
    "appendix",
]


class SlideRange(BaseModel):
    start: int = Field(..., ge=1, le=50)
    end: int = Field(..., ge=1, le=50)


class OutlineSlide(BaseModel):
    slideId: str = Field(..., pattern=r"^slide-[0-9]{3}$")
    slideNumber: int = Field(..., ge=1, le=50)
    slideRole: SlideRole
    slideTitle: str = Field(..., min_length=2, max_length=80)
    keyPoints: list[str] = Field(..., min_length=2, max_length=5)
    notes: str = Field("", max_length=300)


class OutlineSection(BaseModel):
    sectionId: str = Field(..., pattern=r"^sec-[0-9]{2}$")
    sectionTitle: str = Field(..., min_length=2, max_length=80)
    sectionObjective: str = Field(..., min_length=8, max_length=200)
    slideRange: SlideRange
    slides: list[OutlineSlide] = Field(..., min_length=1, max_length=20)


class NarrativeOutline(BaseModel):
    protocolVersion: Literal["ppt-narrative-outline.v1"]
    language: str = Field(..., min_length=2, max_length=20)
    presentationTitle: str = Field(..., min_length=4, max_length=120)
    targetSlideCount: int = Field(..., ge=3, le=50)
    sections: list[OutlineSection] = Field(..., min_length=1, max_length=12)


class ResearchPolicy(BaseModel):
    triggerReason: Literal["user_requested", "insufficient_input", "fact_verification"]
    depthLevel: Literal["light", "standard", "deep"]
    sourcePriority: list[
        Literal[
            "official_sites",
            "government_reports",
            "academic_sources",
            "authoritative_media",
            "industry_reports",
        ]
    ] = Field(..., min_length=1, max_length=5)
    maxSourcesPerSlide: Optional[int] = Field(None, ge=1, le=8)


class KeyDataItem(BaseModel):
    label: str = Field(..., min_length=2, max_length=60)
    value: float
    unit: str = Field(..., min_length=1, max_length=20)
    year: int = Field(..., ge=1990, le=2100)
    sourceRefId: str = Field(..., pattern=r"^src-[0-9]{3}$")


class EvidenceItem(BaseModel):
    sourceRefId: str = Field(..., pattern=r"^src-[0-9]{3}$")
    claim: str = Field(..., min_length=2, max_length=180)
    sourceTitle: str = Field(..., min_length=2, max_length=120)
    sourceType: Literal[
        "official_sites",
        "government_reports",
        "academic_sources",
        "authoritative_media",
        "industry_reports",
    ]
    url: str = Field(..., max_length=300)
    publishDate: str = Field(..., pattern=r"^\d{4}-\d{2}-\d{2}$")
    credibility: Literal["high", "medium"]
    quote: str = Field("", max_length=220)


class PageContentSlide(BaseModel):
    slideId: str = Field(..., pattern=r"^slide-[0-9]{3}$")
    slideNumber: int = Field(..., ge=1, le=50)
    slideRole: SlideRole
    pageGoal: str = Field(..., min_length=8, max_length=120)
    slideTitle: str = Field(..., min_length=2, max_length=80)
    coreMessage: str = Field(..., min_length=12, max_length=140)
    displayBullets: list[str] = Field(..., min_length=3, max_length=5)
    keyData: list[KeyDataItem] = Field(default_factory=list, max_length=4)
    evidencePack: list[EvidenceItem] = Field(default_factory=list, max_length=5)
    actionableTakeaway: str = Field("", max_length=120)
    speakerNotes: str = Field(..., min_length=10, max_length=300)


class PageContentProtocol(BaseModel):
    protocolVersion: Literal["ppt-page-content.v1"]
    language: str = Field(..., min_length=2, max_length=20)
    presentationTitle: str = Field(..., min_length=4, max_length=120)
    researchPolicy: ResearchPolicy
    slides: list[PageContentSlide] = Field(..., min_length=1, max_length=50)


class GenerateOutlineRequest(BaseModel):
    topic: str = Field(..., description="PPT topic")
    requirements: Optional[str] = Field(None, description="Generation requirements")


class ExpandContentRequest(BaseModel):
    outline_node: dict = Field(..., description="Outline node")
    context: Optional[str] = Field(None, description="Reference context")


class BatchContentItem(BaseModel):
    index: int = Field(..., description="Item index")
    id: Optional[str] = Field(None, description="Client item id")
    outline_node: dict = Field(..., description="Outline node")
    context: Optional[str] = Field(None, description="Item-specific context")


class ExpandContentBatchRequest(BaseModel):
    items: list[BatchContentItem] = Field(..., description="Items to expand")
    context: Optional[str] = Field(None, description="Shared context")
    max_workers: Optional[int] = Field(None, ge=1, le=8, description="Worker count")


class BatchContentResultItem(BaseModel):
    index: int = Field(..., description="Item index")
    id: Optional[str] = Field(None, description="Client item id")
    success: bool = Field(..., description="Whether generation succeeded")
    content: str = Field(..., description="Legacy text content")
    page_content: Optional[PageContentProtocol] = None
    message: Optional[str] = Field(None, description="Result message")


class ExpandContentBatchResponse(BaseModel):
    success: bool = Field(..., description="Whether any item succeeded")
    results: list[BatchContentResultItem] = Field(..., description="Batch results")
    message: Optional[str] = Field(None, description="Result message")
    elapsed_sec: Optional[float] = Field(None, description="Elapsed seconds")


class RAGQueryRequest(BaseModel):
    query: str = Field(..., description="RAG query")


class DocumentUploadRequest(BaseModel):
    file_path: str = Field(..., description="Document file path")


class GenerateOutlineResponse(BaseModel):
    success: bool = Field(..., description="Whether generation succeeded")
    outline: NarrativeOutline = Field(..., description="Narrative outline protocol")
    message: Optional[str] = Field(None, description="Result message")


class ExpandContentResponse(BaseModel):
    success: bool = Field(..., description="Whether generation succeeded")
    content: str = Field(..., description="Legacy text content")
    page_content: Optional[PageContentProtocol] = None
    message: Optional[str] = Field(None, description="Result message")


class RAGQueryResponse(BaseModel):
    success: bool = Field(..., description="Whether query succeeded")
    answer: str = Field(..., description="Generated answer")
    message: Optional[str] = Field(None, description="Result message")


class DocumentUploadResponse(BaseModel):
    success: bool = Field(..., description="Whether upload succeeded")
    doc_id: str = Field(..., description="Document id")
    message: Optional[str] = Field(None, description="Result message")


class DocumentMetadata(BaseModel):
    doc_id: int = Field(..., description="Document id")
    title: str = Field(..., description="Document title")
    file_path: str = Field(..., description="Document file path")
    created_at: str = Field(..., description="Created timestamp")


class Document(BaseModel):
    metadata: DocumentMetadata = Field(..., description="Document metadata")
    content: str = Field(..., description="Document content")


class HealthResponse(BaseModel):
    status: str = Field(..., description="Service status")
    version: str = Field(..., description="Service version")


class ModelInfoResponse(BaseModel):
    current_provider: str = Field(..., description="Current LLM provider")
    available_providers: list[str] = Field(..., description="Available providers")


class SwitchModelRequest(BaseModel):
    provider: str = Field(..., description="Target LLM provider")


class SwitchModelResponse(BaseModel):
    success: bool = Field(..., description="Whether switch succeeded")
    current_provider: str = Field(..., description="Current LLM provider")
    message: Optional[str] = Field(None, description="Result message")


class SearchKnowledgeRequest(BaseModel):
    topic: str = Field(..., description="Knowledge search topic")
    refine_knowledge: bool = Field(False, description="Whether to refine knowledge")


class SearchKnowledgeResponse(BaseModel):
    success: bool = Field(..., description="Whether search succeeded")
    knowledge: str = Field(..., description="Retrieved knowledge")
    message: Optional[str] = Field(None, description="Result message")


class BatchKnowledgeItem(BaseModel):
    index: int = Field(..., description="Item index")
    id: Optional[str] = Field(None, description="Client item id")
    query: str = Field(..., description="Knowledge query")


class SearchKnowledgeBatchRequest(BaseModel):
    items: list[BatchKnowledgeItem] = Field(..., description="Items to search")
    refine_knowledge: bool = Field(False, description="Whether to refine knowledge")
    max_workers: Optional[int] = Field(None, ge=1, le=8, description="Worker count")


class BatchKnowledgeResultItem(BaseModel):
    index: int
    id: Optional[str] = None
    success: bool
    knowledge: str
    has_sources: bool = False
    message: Optional[str] = None


class SearchKnowledgeBatchResponse(BaseModel):
    success: bool
    results: list[BatchKnowledgeResultItem]
    message: Optional[str] = None
    elapsed_sec: Optional[float] = None
