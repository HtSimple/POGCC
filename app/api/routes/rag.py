import asyncio
import uuid
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from fastapi import APIRouter, File, Request, UploadFile
from app.schema.models import RAGQueryRequest, RAGQueryResponse, DocumentUploadRequest, DocumentUploadResponse
from app.core.knowledge_agent import KnowledgeAgent
from app.services.web_search_service import WebSearchService

router = APIRouter(prefix="/api/rag", tags=["rag"])

_executor = ThreadPoolExecutor(max_workers=2)
_UPLOAD_DIR = Path("app/rag/uploads")
_ALLOWED_SUFFIXES = {".pdf", ".docx", ".doc", ".txt", ".md"}


async def _run_batch_ingest(request: Request, file_paths: list[str]) -> DocumentUploadResponse:
    rs = getattr(request.app.state, "retrieval_service", None)
    if rs is None:
        return DocumentUploadResponse(
            success=False,
            doc_id="",
            message="本地知识库未初始化，请检查 sentence-transformers 与 config 中的 rag_persist_dir、rag_embedding_model",
        )
    loop = asyncio.get_running_loop()
    reports = await loop.run_in_executor(_executor, rs.batch_ingest, file_paths)
    report = reports[0]
    ok = report.status in ("success", "skipped")
    return DocumentUploadResponse(
        success=ok,
        doc_id=report.doc_id if ok else "",
        message=report.message,
    )


async def _save_upload_file(file: UploadFile) -> Path:
    original_name = Path(file.filename or "").name
    if not original_name:
        raise ValueError("未收到文件名")
    suffix = Path(original_name).suffix.lower()
    if suffix not in _ALLOWED_SUFFIXES:
        allowed = "、".join(sorted(_ALLOWED_SUFFIXES))
        raise ValueError(f"不支持的文件类型：{suffix or '未知'}，请上传 {allowed}")

    _UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    dest = _UPLOAD_DIR / f"{uuid.uuid4().hex[:8]}_{original_name}"
    content = await file.read()
    if not content:
        raise ValueError("文件内容为空")
    dest.write_bytes(content)
    return dest


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
        return await _run_batch_ingest(request, [body.file_path])
    except Exception as e:
        return DocumentUploadResponse(
            success=False,
            doc_id="",
            message=f"文档上传失败: {str(e)}",
        )


@router.post("/upload/file", response_model=DocumentUploadResponse)
async def upload_document_file(request: Request, file: UploadFile = File(...)):
    """接收浏览器上传的文件，保存到本地后写入 RAG 索引。"""
    try:
        saved_path = await _save_upload_file(file)
        return await _run_batch_ingest(request, [str(saved_path.resolve())])
    except ValueError as e:
        return DocumentUploadResponse(success=False, doc_id="", message=str(e))
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
