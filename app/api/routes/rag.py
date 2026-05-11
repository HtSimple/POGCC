from fastapi import APIRouter, Request
from app.schema.models import RAGQueryRequest, RAGQueryResponse, DocumentUploadRequest, DocumentUploadResponse
from app.core.knowledge_agent import KnowledgeAgent
from app.services.web_search_service import WebSearchService

router = APIRouter(prefix="/api/rag", tags=["rag"])


def _get_knowledge_agent(request: Request) -> KnowledgeAgent:
    return KnowledgeAgent(
        llm_service=request.app.state.llm_service,
        web_search_service=WebSearchService(),
        retrieval_service=getattr(request.app.state, "retrieval_service", None),
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
async def upload_document(request: Request, body: DocumentUploadRequest):
    try:
        rs = getattr(request.app.state, "retrieval_service", None)
        if rs is None:
            return DocumentUploadResponse(
                success=False,
                doc_id="",
                message="本地知识库未初始化，请检查 sentence-transformers 与 config 中的 rag_persist_dir、rag_embedding_model",
            )
        # 与 app/rag/demo.py 一致：用 batch_ingest（单文件也传列表）
        reports = rs.batch_ingest([body.file_path])
        report = reports[0]
        ok = report.status in ("success", "skipped")
        return DocumentUploadResponse(
            success=ok,
            doc_id=report.doc_id if ok else "",
            message=report.message,
        )
    except Exception as e:
        return DocumentUploadResponse(
            success=False,
            doc_id="",
            message=f"文档上传失败: {str(e)}",
        )
