from pydantic import BaseModel, Field
from typing import List, Optional

# 请求模型
class GenerateOutlineRequest(BaseModel):
    """生成大纲请求模型"""
    topic: str = Field(..., description="PPT主题")
    requirements: Optional[str] = Field(None, description="额外需求")

class ExpandContentRequest(BaseModel):
    """补全内容请求模型"""
    outline_node: dict = Field(..., description="大纲节点")
    context: Optional[str] = Field(None, description="上下文信息")

class BatchContentItem(BaseModel):
    """批量正文生成单项"""
    index: int = Field(..., description="页面序号，从 0 开始")
    id: Optional[str] = Field(None, description="前端页面 ID，原样回传")
    outline_node: dict = Field(..., description="大纲节点")
    context: Optional[str] = Field(None, description="该项上下文，可覆盖批次级 context")

class ExpandContentBatchRequest(BaseModel):
    """批量补全内容请求"""
    items: List[BatchContentItem] = Field(..., description="待生成页面列表")
    context: Optional[str] = Field(None, description="批次共享上下文")
    max_workers: Optional[int] = Field(None, ge=1, le=8, description="并行线程数，默认读 config")

class BatchContentResultItem(BaseModel):
    """批量正文生成单项结果"""
    index: int = Field(..., description="页面序号")
    id: Optional[str] = Field(None, description="前端页面 ID")
    success: bool = Field(..., description="该项是否成功")
    content: str = Field(..., description="生成的正文")
    message: Optional[str] = Field(None, description="失败原因等")

class ExpandContentBatchResponse(BaseModel):
    """批量补全内容响应"""
    success: bool = Field(..., description="是否至少有一项成功")
    results: List[BatchContentResultItem] = Field(..., description="各页结果")
    message: Optional[str] = Field(None, description="汇总消息")
    elapsed_sec: Optional[float] = Field(None, description="总耗时（秒）")

class RAGQueryRequest(BaseModel):
    """RAG查询请求模型"""
    query: str = Field(..., description="查询文本")

class DocumentUploadRequest(BaseModel):
    """文档上传请求模型"""
    file_path: str = Field(..., description="文档文件路径")

# 响应模型
class GenerateOutlineResponse(BaseModel):
    """生成大纲响应模型"""
    success: bool = Field(..., description="是否成功")
    outline: dict = Field(..., description="生成的大纲")
    message: Optional[str] = Field(None, description="消息")

class ExpandContentResponse(BaseModel):
    """补全内容响应模型"""
    success: bool = Field(..., description="是否成功")
    content: str = Field(..., description="补全的内容")
    message: Optional[str] = Field(None, description="消息")

class RAGQueryResponse(BaseModel):
    """RAG查询响应模型"""
    success: bool = Field(..., description="是否成功")
    answer: str = Field(..., description="生成的回答")
    message: Optional[str] = Field(None, description="消息")

class DocumentUploadResponse(BaseModel):
    """文档上传响应模型"""
    success: bool = Field(..., description="是否成功")
    doc_id: str = Field(..., description="文档ID（本地 RAG 为字符串 doc_id）")
    message: Optional[str] = Field(None, description="消息")

# 文档模型
class DocumentMetadata(BaseModel):
    """文档元数据模型"""
    doc_id: int = Field(..., description="文档ID")
    title: str = Field(..., description="文档标题")
    file_path: str = Field(..., description="文件路径")
    created_at: str = Field(..., description="创建时间")

class Document(BaseModel):
    """文档模型"""
    metadata: DocumentMetadata = Field(..., description="文档元数据")
    content: str = Field(..., description="文档内容")

# 健康检查响应模型
class HealthResponse(BaseModel):
    """健康检查响应模型"""
    status: str = Field(..., description="服务状态")
    version: str = Field(..., description="服务版本")

class ModelInfoResponse(BaseModel):
    """模型信息响应模型"""
    current_provider: str = Field(..., description="当前使用的LLM提供者")
    available_providers: List[str] = Field(..., description="可用的LLM提供者列表")

class SwitchModelRequest(BaseModel):
    """切换模型请求模型"""
    provider: str = Field(..., description="要切换的LLM提供者名称，如 deepseek 或 qwen")

class SwitchModelResponse(BaseModel):
    """切换模型响应模型"""
    success: bool = Field(..., description="是否切换成功")
    current_provider: str = Field(..., description="切换后使用的LLM提供者")
    message: Optional[str] = Field(None, description="消息")

class SearchKnowledgeRequest(BaseModel):
    topic: str = Field(..., description="需要搜索知识的查询文本（可与前端补充知识 query 一致）")
    refine_knowledge: bool = Field(
        False,
        description="True=评估+整理 LLM；False=快路径，仅检索并拼接来源",
    )

class SearchKnowledgeResponse(BaseModel):
    success: bool = Field(..., description="是否成功")
    knowledge: str = Field(..., description="检索摘要与来源（或整理后的知识摘要）")
    message: Optional[str] = Field(None, description="消息")

class BatchKnowledgeItem(BaseModel):
    index: int = Field(..., description="页面序号，从 0 开始")
    id: Optional[str] = Field(None, description="前端页面 ID")
    query: str = Field(..., description="该页检索 query")

class SearchKnowledgeBatchRequest(BaseModel):
    items: List[BatchKnowledgeItem] = Field(..., description="待检索页面列表")
    refine_knowledge: bool = Field(False, description="是否走完整整理流程")
    max_workers: Optional[int] = Field(None, ge=1, le=8, description="并行线程数")

class BatchKnowledgeResultItem(BaseModel):
    index: int
    id: Optional[str] = None
    success: bool
    knowledge: str
    has_sources: bool = False
    message: Optional[str] = None

class SearchKnowledgeBatchResponse(BaseModel):
    success: bool
    results: List[BatchKnowledgeResultItem]
    message: Optional[str] = None
    elapsed_sec: Optional[float] = None