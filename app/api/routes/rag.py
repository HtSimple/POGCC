from fastapi import APIRouter
from app.schema.models import RAGQueryRequest, RAGQueryResponse, DocumentUploadRequest, DocumentUploadResponse
from app.core.rag_agent.agent import RAGAgent
from app.core.faiss_db import FAISSDB
from app.core.document_parser import DocumentParser

router = APIRouter(prefix="/api/rag", tags=["rag"])

# 创建RAG Agent实例
vector_db = FAISSDB()
document_parser = DocumentParser()
rag_agent = RAGAgent(document_parser=document_parser, vector_db=vector_db)

@router.post("/query", response_model=RAGQueryResponse)
async def rag_query(request: RAGQueryRequest):
    """查询知识库"""
    try:
        # 处理查询
        answer = rag_agent.process_query(request.query)
        
        return RAGQueryResponse(
            success=True,
            answer=answer,
            message="查询成功"
        )
    except Exception as e:
        return RAGQueryResponse(
            success=False,
            answer="",
            message=f"查询失败: {str(e)}"
        )

@router.post("/upload", response_model=DocumentUploadResponse)
async def upload_document(request: DocumentUploadRequest):
    """上传文档到知识库"""
    try:
        # 解析文档
        content = document_parser.parse(request.file_path)
        
        # 添加到向量数据库
        doc_id = vector_db.add_document(content)
        
        return DocumentUploadResponse(
            success=True,
            doc_id=doc_id,
            message="文档上传成功"
        )
    except Exception as e:
        return DocumentUploadResponse(
            success=False,
            doc_id=-1,
            message=f"文档上传失败: {str(e)}"
        )