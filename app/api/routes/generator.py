import asyncio

from fastapi import APIRouter, Request
from app.schema.models import (
    GenerateOutlineRequest,
    GenerateOutlineResponse,
    ExpandContentRequest,
    ExpandContentResponse,
    ExpandContentBatchRequest,
    ExpandContentBatchResponse,
    BatchContentResultItem,
)
from app.core.generator.outline_maker import OutlineMaker
from app.core.generator.content_expander import ContentExpander
from app.core.generator.batch_content import expand_content_batch, is_llm_error_content

router = APIRouter(prefix="/api/generator", tags=["generator"])


def _get_outline_maker(request: Request) -> OutlineMaker:
    return OutlineMaker(llm_service=request.app.state.llm_service)


def _get_content_expander(request: Request) -> ContentExpander:
    return ContentExpander(llm_service=request.app.state.llm_service)


@router.post("/outline", response_model=GenerateOutlineResponse)
async def generate_outline(request: Request, body: GenerateOutlineRequest):
    try:
        outline_maker = _get_outline_maker(request)
        outline = await asyncio.to_thread(
            outline_maker.generate_outline,
            body.topic,
            body.requirements,
        )

        return GenerateOutlineResponse(
            success=True,
            outline=outline,
            message="大纲生成成功"
        )
    except Exception as e:
        return GenerateOutlineResponse(
            success=False,
            outline={"title": "", "sections": []},
            message=f"大纲生成失败: {str(e)}"
        )


@router.post("/content", response_model=ExpandContentResponse)
async def expand_content(request: Request, body: ExpandContentRequest):
    try:
        content_expander = _get_content_expander(request)
        content = await asyncio.to_thread(
            content_expander.expand_content,
            body.outline_node,
            body.context,
        )

        if is_llm_error_content(content):
            return ExpandContentResponse(
                success=False,
                content=content or "",
                message=content or "内容补全失败",
            )

        return ExpandContentResponse(
            success=True,
            content=content,
            message="内容补全成功"
        )
    except Exception as e:
        return ExpandContentResponse(
            success=False,
            content="",
            message=f"内容补全失败: {str(e)}"
        )


@router.post("/content/batch", response_model=ExpandContentBatchResponse)
async def expand_content_batch_route(request: Request, body: ExpandContentBatchRequest):
    try:
        payload = [item.model_dump() for item in body.items]
        report = await asyncio.to_thread(
            expand_content_batch,
            payload,
            body.context,
            body.max_workers,
        )

        results = [BatchContentResultItem(**item) for item in report["results"]]
        return ExpandContentBatchResponse(
            success=report["success"],
            results=results,
            message=report.get("message"),
            elapsed_sec=report.get("elapsed_sec"),
        )
    except Exception as e:
        return ExpandContentBatchResponse(
            success=False,
            results=[],
            message=f"批量内容补全失败: {str(e)}",
            elapsed_sec=None,
        )
