import asyncio
from concurrent.futures import ThreadPoolExecutor

from fastapi import APIRouter, Request
from app.schema.models import RAGQueryRequest, RAGQueryResponse, DocumentUploadRequest, DocumentUploadResponse
from app.core.knowledge_agent import KnowledgeAgent
from app.services.web_search_service import WebSearchService

router = APIRouter(prefix="/api/rag", tags=["rag"])

_executor = ThreadPoolExecutor(max_workers=2)


def _get_knowledge_agent(request: Request) -> KnowledgeAgent:
    """使用应用级 LLM 和本地检索服务创建一次请求级 KnowledgeAgent。"""
    return KnowledgeAgent(
        llm_service=request.app.state.llm_service,
        web_search_service=WebSearchService(),
        retrieval_service=getattr(request.app.state, "retrieval_service", None),
    )


@router.post("/query", response_model=RAGQueryResponse)
async def rag_query(request: Request, body: RAGQueryRequest):
    """兼容旧 RAG 查询入口，执行完整 KnowledgeAgent 问答流程。"""
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
    """把指定文档路径写入本地 RAG 索引，供后续知识检索使用。"""
    try:
        rs = getattr(request.app.state, "retrieval_service", None)
        if rs is None:
            return DocumentUploadResponse(
                success=False,
                doc_id="",
                message="本地知识库未初始化，请检查 sentence-transformers 与 config 中的 rag_persist_dir、rag_embedding_model",
            )
        # 与 app/rag/demo.py 一致：用 batch_ingest（单文件也传列表）
        # CPU-heavy embedding work → run in thread to avoid blocking event loop
        loop = asyncio.get_running_loop()
        reports = await loop.run_in_executor(_executor, rs.batch_ingest, [body.file_path])
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


@router.post("/clear")
async def clear_rag_index(request: Request):
    """清空本地 RAG 索引中的所有文档。"""
    try:
        rs = getattr(request.app.state, "retrieval_service", None)
        if rs is None:
            return {"success": False, "message": "本地知识库未初始化"}
        docs = rs.list_documents()
        removed = 0
        for doc in docs:
            doc_id = doc.get("doc_id", "")
            if doc_id:
                rs.delete_document(doc_id)
                removed += 1
        return {"success": True, "message": f"已清除 {removed} 个文档"}
    except Exception as e:
        return {"success": False, "message": f"清除失败: {str(e)}"}
