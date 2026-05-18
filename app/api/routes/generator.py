import asyncio
import re

from fastapi import APIRouter, Request

from app.core.generator.batch_content import expand_content_batch, is_llm_error_content
from app.core.generator.content_expander import ContentExpander
from app.core.generator.outline_maker import OutlineMaker
from app.schema.models import (
    BatchContentResultItem,
    ExpandContentBatchRequest,
    ExpandContentBatchResponse,
    ExpandContentRequest,
    ExpandContentResponse,
    GenerateOutlineRequest,
    GenerateOutlineResponse,
)

router = APIRouter(prefix="/api/generator", tags=["generator"])


def _get_outline_maker(request: Request) -> OutlineMaker:
    return OutlineMaker(llm_service=request.app.state.llm_service)


def _get_content_expander(request: Request) -> ContentExpander:
    return ContentExpander(llm_service=request.app.state.llm_service)


@router.post("/outline", response_model=GenerateOutlineResponse)
async def generate_outline(request: Request, body: GenerateOutlineRequest):
    try:
        outline_maker = _get_outline_maker(request)
        reference_context = await asyncio.to_thread(_build_outline_reference_context, request, body)
        outline = await asyncio.to_thread(
            outline_maker.generate_outline,
            body.topic,
            body.requirements,
            reference_context,
        )

        has_reference_context = bool(reference_context.strip())
        return GenerateOutlineResponse(
            success=True,
            outline=outline,
            message=(
                "outline generated with legacy fallback"
                if outline_maker.last_used_fallback
                else ("outline generated with reference context" if has_reference_context else "outline generated")
            ),
        )
    except Exception as exc:
        return GenerateOutlineResponse(
            success=False,
            outline=_fallback_outline(body.topic),
            message=f"outline generation failed: {exc}",
        )


def _build_outline_reference_context(request: Request, body: GenerateOutlineRequest) -> str:
    retrieval_service = getattr(request.app.state, "retrieval_service", None)
    if retrieval_service is None:
        return ""

    query = "\n".join(part for part in [body.topic, body.requirements or ""] if part.strip())
    if not query.strip():
        return ""

    try:
        response = retrieval_service.search(query=query, top_k=5)
    except Exception as exc:
        return f"Reference retrieval failed: {exc}"

    if not response.results:
        return ""

    blocks = []
    for index, item in enumerate(response.results, start=1):
        text = _repair_mojibake(item.text or "").strip()
        if len(text) > 1200:
            text = text[:1200] + "..."
        if text:
            blocks.append(f"[参考资料 {index}]\n{text}")
    return "\n\n".join(blocks)


def _repair_mojibake(text: str) -> str:
    """Repair common UTF-8 text decoded as latin-1/cp1252 before prompting."""
    if not text:
        return ""

    suspicious_chars = sum(text.count(ch) for ch in ["Ã", "Â", "ä", "å", "æ", "é", "ç", "è", "ã"])
    if suspicious_chars < 3:
        return text

    for encoding in ("latin-1", "cp1252"):
        try:
            repaired = text.encode(encoding).decode("utf-8")
        except UnicodeError:
            continue
        if _count_cjk(repaired) > _count_cjk(text):
            return repaired
    return text


def _count_cjk(text: str) -> int:
    return len(re.findall(r"[\u4e00-\u9fff]", text or ""))


@router.post("/content", response_model=ExpandContentResponse)
async def expand_content(request: Request, body: ExpandContentRequest):
    try:
        content_expander = _get_content_expander(request)
        result = await asyncio.to_thread(
            content_expander.expand_page_content,
            body.outline_node,
            body.context,
        )
        content = result.get("content") or ""

        if is_llm_error_content(content):
            return ExpandContentResponse(
                success=False,
                content=content,
                page_content=result.get("page_content"),
                message=content or "content generation failed",
            )

        return ExpandContentResponse(
            success=True,
            content=content,
            page_content=result.get("page_content"),
            message=result.get("message") or "content generated",
        )
    except Exception as exc:
        return ExpandContentResponse(
            success=False,
            content="",
            page_content=None,
            message=f"content generation failed: {exc}",
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
    except Exception as exc:
        return ExpandContentBatchResponse(
            success=False,
            results=[],
            message=f"batch content generation failed: {exc}",
            elapsed_sec=None,
        )


def _fallback_outline(topic: str) -> dict:
    title = topic or "PPT Generation Task"
    return {
        "protocolVersion": "ppt-narrative-outline.v1",
        "language": "zh-CN",
        "presentationTitle": title,
        "targetSlideCount": 3,
        "sections": [
            {
                "sectionId": "sec-01",
                "sectionTitle": "主题概览",
                "sectionObjective": "说明演示主题的背景、目标和核心内容",
                "slideRange": {"start": 1, "end": 3},
                "slides": [
                    {
                        "slideId": "slide-001",
                        "slideNumber": 1,
                        "slideRole": "cover",
                        "slideTitle": title,
                        "keyPoints": ["介绍演示主题", "说明演示目标"],
                        "notes": "",
                    },
                    {
                        "slideId": "slide-002",
                        "slideNumber": 2,
                        "slideRole": "content",
                        "slideTitle": "核心内容",
                        "keyPoints": ["概括核心问题", "呈现主要思路"],
                        "notes": "",
                    },
                    {
                        "slideId": "slide-003",
                        "slideNumber": 3,
                        "slideRole": "summary",
                        "slideTitle": "总结与展望",
                        "keyPoints": ["总结主要结论", "提出后续方向"],
                        "notes": "",
                    },
                ],
            }
        ],
    }
