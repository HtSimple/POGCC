from fastapi import APIRouter, Request
from app.schema.models import SearchKnowledgeRequest, SearchKnowledgeResponse
from app.core.knowledge_agent import KnowledgeAgent
from app.services.web_search_service import WebSearchService

router = APIRouter(prefix="/api/search", tags=["search"])


@router.post("/knowledge", response_model=SearchKnowledgeResponse)
async def search_knowledge(request: Request, body: SearchKnowledgeRequest):
    try:
        agent = KnowledgeAgent(
            llm_service=request.app.state.llm_service,
            web_search_service=WebSearchService(),
        )
        knowledge = agent.process_query(body.topic)
        return SearchKnowledgeResponse(
            success=True,
            knowledge=knowledge,
            message="知识搜索完成"
        )
    except Exception as e:
        return SearchKnowledgeResponse(
            success=False,
            knowledge="",
            message=f"知识搜索失败: {str(e)}"
        )
