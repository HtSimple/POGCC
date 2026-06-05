import asyncio
import json
import re
from pathlib import Path

from fastapi import APIRouter, Request

from app.core.generator.batch_content import expand_content_batch, is_llm_error_content
from app.core.generator.content_expander import ContentExpander
from app.core.generator.notes_generator import NotesGenerator
from app.core.generator.outline_maker import OutlineMaker
from app.schema.models import (
    BatchContentResultItem,
    ExpandContentBatchRequest,
    ExpandContentBatchResponse,
    ExpandContentRequest,
    ExpandContentResponse,
    GenerateNotesRequest,
    GenerateNotesResponse,
    GenerateOutlineRequest,
    GenerateOutlineResponse,
    ReviseContentRequest,
    ReviseContentTextRequest,
    ReviseContentTextResponse,
)
from app.services.api_cost_service import ApiQuotaExceeded

router = APIRouter(prefix="/api/generator", tags=["generator"])
OUTPUT_JSON_PATH = Path(__file__).resolve().parents[3] / "output.json"


def _get_outline_maker(request: Request) -> OutlineMaker:
    return OutlineMaker(llm_service=request.app.state.llm_service)


def _get_content_expander(request: Request) -> ContentExpander:
    return ContentExpander(llm_service=request.app.state.llm_service)


def _get_notes_generator(request: Request) -> NotesGenerator:
    return NotesGenerator(llm_service=request.app.state.llm_service)


def _generation_error(prefix: str, exc: Exception) -> str:
    if isinstance(exc, ApiQuotaExceeded):
        return str(exc)
    return f"{prefix}: {exc}"


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
        response = GenerateOutlineResponse(
            success=True,
            outline=outline,
            message=(
                "outline generated with legacy fallback"
                if outline_maker.last_used_fallback
                else ("outline generated with reference context" if has_reference_context else "outline generated")
            ),
        )
        await asyncio.to_thread(_save_output_json, _outline_output_payload(response, outline_maker))
        return response
    except Exception as exc:
        response = GenerateOutlineResponse(
            success=False,
            outline=_fallback_outline(body.topic),
            message=_generation_error("outline generation failed", exc),
        )
        await asyncio.to_thread(_save_output_json, response.model_dump())
        return response


def _save_output_json(payload: dict) -> None:
    OUTPUT_JSON_PATH.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def _outline_output_payload(response: GenerateOutlineResponse, outline_maker: OutlineMaker) -> dict:
    if not outline_maker.last_used_fallback:
        return response.model_dump()

    return {
        "success": False,
        "source": "raw_llm_output",
        "message": "model output failed JSON protocol validation; fallback was returned to API caller",
        "schema_error": outline_maker.last_schema_error,
        "validation_error": outline_maker.last_validation_error,
        "raw_llm_output": outline_maker.last_raw_output,
    }


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

        if result.get("page_content") is None:
            return ExpandContentResponse(
                success=False,
                content="",
                page_content=None,
                message=result.get("message") or "structured content validation failed",
            )

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
            message=_generation_error("content generation failed", exc),
        )


@router.post("/content/revise", response_model=ExpandContentResponse)
async def revise_content(request: Request, body: ReviseContentRequest):
    try:
        content_expander = _get_content_expander(request)
        result = await asyncio.to_thread(
            content_expander.revise_page_content,
            body.outline_node,
            body.context,
            body.current_content,
            body.revision_suggestion,
        )
        content = result.get("content") or ""

        if result.get("page_content") is None:
            return ExpandContentResponse(
                success=False,
                content="",
                page_content=None,
                message=result.get("message") or "structured content validation failed",
            )

        if is_llm_error_content(content):
            return ExpandContentResponse(
                success=False,
                content=content,
                page_content=result.get("page_content"),
                message=content or "content revision failed",
            )

        return ExpandContentResponse(
            success=True,
            content=content,
            page_content=result.get("page_content"),
            message=result.get("message") or "content revised",
        )
    except Exception as exc:
        return ExpandContentResponse(
            success=False,
            content="",
            page_content=None,
            message=_generation_error("content revision failed", exc),
        )


@router.post("/content/revise/text", response_model=ReviseContentTextResponse)
async def revise_content_text(request: Request, body: ReviseContentTextRequest):
    try:
        content_expander = _get_content_expander(request)
        result = await asyncio.to_thread(
            content_expander.revise_page_content_text,
            body.outline_node,
            body.current_content,
            body.revision_suggestion,
        )
        content = result.get("content") or ""
        if not result.get("success"):
            return ReviseContentTextResponse(
                success=False,
                content="",
                message=result.get("message") or "content revision failed",
            )
        if is_llm_error_content(content):
            return ReviseContentTextResponse(
                success=False,
                content=content,
                message=content or "content revision failed",
            )
        return ReviseContentTextResponse(
            success=True,
            content=content,
            message=result.get("message") or "content revised",
        )
    except Exception as exc:
        return ReviseContentTextResponse(
            success=False,
            content="",
            message=_generation_error("content revision failed", exc),
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
            request.app.state.llm_service,
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
            message=_generation_error("batch content generation failed", exc),
            elapsed_sec=None,
        )


@router.post("/notes", response_model=GenerateNotesResponse)
async def generate_notes(request: Request, body: GenerateNotesRequest):
    try:
        notes_generator = _get_notes_generator(request)
        result = await asyncio.to_thread(
            notes_generator.generate_notes,
            body.project_id,
            body.slide_id,
            body.slide_title,
            body.slide_content,
            body.knowledge_evidence,
            body.style_requirement,
        )
        return GenerateNotesResponse(
            success=True,
            notes=result["notes"],
            message="speaker notes generated",
        )
    except Exception as exc:
        return GenerateNotesResponse(
            success=False,
            notes="",
            message=_generation_error("speaker notes generation failed", exc),
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
