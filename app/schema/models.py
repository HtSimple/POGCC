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
    doc_id: int = Field(..., description="文档ID")
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