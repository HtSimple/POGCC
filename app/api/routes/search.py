import asyncio

from fastapi import APIRouter, Request
from app.schema.models import (
    SearchKnowledgeRequest,
    SearchKnowledgeResponse,
    SearchKnowledgeBatchRequest,
    SearchKnowledgeBatchResponse,
    BatchKnowledgeResultItem,
)
from app.core.knowledge_agent.search_agent import SearchAgent
from app.core.knowledge_agent.batch_retrieval import retrieve_knowledge_batch, is_retrieval_error
from app.services.llm_service import LLMService
from app.services.web_search_service import WebSearchService

router = APIRouter(prefix="/api/search", tags=["search"])


def _get_retrieval_service(request: Request):
    return getattr(request.app.state, "retrieval_service", None)


def _run_search(query: str, refine_knowledge: bool, retrieval_service) -> str:
    agent = SearchAgent(
        llm_service=LLMService(),
        web_search_service=WebSearchService(),
        retrieval_service=retrieval_service,
    )
    return agent.search(query, refine_knowledge=refine_knowledge)


@router.post("/knowledge", response_model=SearchKnowledgeResponse)
async def search_knowledge(request: Request, body: SearchKnowledgeRequest):
    try:
        knowledge = await asyncio.to_thread(
            _run_search,
            body.topic,
            body.refine_knowledge,
            _get_retrieval_service(request),
        )
        if is_retrieval_error(knowledge):
            return SearchKnowledgeResponse(
                success=False,
                knowledge=knowledge or "",
                message=knowledge or "知识检索失败",
            )
        return SearchKnowledgeResponse(
            success=True,
            knowledge=knowledge,
            message="知识检索完成",
        )
    except Exception as e:
        return SearchKnowledgeResponse(
            success=False,
            knowledge="",
            message=f"知识搜索失败: {str(e)}",
        )


@router.post("/knowledge/batch", response_model=SearchKnowledgeBatchResponse)
async def search_knowledge_batch(request: Request, body: SearchKnowledgeBatchRequest):
    try:
        payload = [item.model_dump() for item in body.items]
        report = await asyncio.to_thread(
            retrieve_knowledge_batch,
            payload,
            body.refine_knowledge,
            body.max_workers,
            _get_retrieval_service(request),
        )
        results = [BatchKnowledgeResultItem(**item) for item in report["results"]]
        return SearchKnowledgeBatchResponse(
            success=report["success"],
            results=results,
            message=report.get("message"),
            elapsed_sec=report.get("elapsed_sec"),
        )
    except Exception as e:
        return SearchKnowledgeBatchResponse(
            success=False,
            results=[],
            message=f"批量知识检索失败: {str(e)}",
            elapsed_sec=None,
        )
