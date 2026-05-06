from fastapi import APIRouter, Request
from app.schema.models import RAGQueryRequest, RAGQueryResponse, DocumentUploadRequest, DocumentUploadResponse
from app.core.knowledge_agent import KnowledgeAgent
from app.core.faiss_db import FAISSDB
from app.core.document_parser import DocumentParser
from app.services.web_search_service import WebSearchService

router = APIRouter(prefix="/api/rag", tags=["rag"])

vector_db = FAISSDB()
document_parser = DocumentParser()


def _get_knowledge_agent(request: Request) -> KnowledgeAgent:
    return KnowledgeAgent(
        llm_service=request.app.state.llm_service,
        web_search_service=WebSearchService(),
    )


@router.post("/query", response_model=RAGQueryResponse)
async def rag_query(request: Request, body: RAGQueryRequest):
    try:
        agent = _get_knowledge_agent(request)
        answer = agent.process_query(body.query)

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
    try:
        content = document_parser.parse(request.file_path)
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
