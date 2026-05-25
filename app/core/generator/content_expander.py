import json
from datetime import date
from typing import Any

from pydantic import ValidationError

from app.prompts.templates import CONTENT_TEMPLATE, PAGE_CONTENT_JSON_TEMPLATE
from app.schema.models import PageContentProtocol
from app.schema.protocol_schemas import PAGE_CONTENT_RESPONSE_SCHEMA
from app.utils.json_protocol import page_content_to_text, parse_json_object


def _clean_text(value: Any, fallback: str = "") -> str:
    text = str(value or "").strip()
    return text or fallback


def _normalize_slide_id(value: Any) -> str:
    text = _clean_text(value)
    if text.startswith("slide-") and len(text) == 9:
        return text
    return "slide-001"


def _normalize_slide_number(value: Any) -> int:
    try:
        number = int(value)
    except (TypeError, ValueError):
        number = 1
    return max(1, min(number, 50))


def _normalize_source_type(value: Any) -> str:
    text = _clean_text(value, "local_document")
    allowed = {
        "local_document",
        "official_sites",
        "government_reports",
        "academic_sources",
        "authoritative_media",
        "industry_reports",
    }
    return text if text in allowed else "local_document"


def _compact_text(value: Any) -> str:
    return "".join(ch for ch in _clean_text(value) if ch.isalnum())


def _is_duplicate_text(candidate: str, existing: list[str]) -> bool:
    compact_candidate = _compact_text(candidate)
    if not compact_candidate:
        return True
    for item in existing:
        compact_item = _compact_text(item)
        if compact_candidate == compact_item:
            return True
        if len(compact_candidate) >= 18 and compact_candidate in compact_item:
            return True
        if len(compact_item) >= 18 and compact_item in compact_candidate:
            return True
    return False


def _normalize_evidence_pack(items: Any) -> list[dict[str, Any]]:
    if not isinstance(items, list):
        return []

    normalized = []
    today = date.today().isoformat()
    for index, item in enumerate(items, start=1):
        if not isinstance(item, dict):
            continue

        source_ref_id = _clean_text(item.get("sourceRefId"), f"src-{index:03d}")
        if not source_ref_id.startswith("src-") or len(source_ref_id) != 7:
            source_ref_id = f"src-{index:03d}"

        normalized.append({
            "sourceRefId": source_ref_id,
            "claim": _clean_text(item.get("claim") or item.get("keyClaim"), "本地资料支持该页面观点"),
            "sourceTitle": _clean_text(
                item.get("sourceTitle") or item.get("sourceDescription"),
                "本地参考资料",
            ),
            "sourceType": _normalize_source_type(item.get("sourceType")),
            "url": _clean_text(item.get("url"), ""),
            "publishDate": _clean_text(item.get("publishDate") or item.get("retrievedAt"), today),
            "credibility": _clean_text(item.get("credibility"), "medium"),
            "quote": _clean_text(item.get("quote"), ""),
        })

    return normalized


def _normalize_display_bullets(items: Any, node: dict[str, Any], slide: dict[str, Any]) -> list[str]:
    raw_items = items if isinstance(items, list) else []
    blocked = {
        "",
        "学术汇报",
        "课程汇报",
        "课堂汇报",
        "课程讲师",
        "项目评委",
        "企业客户",
        "目标受众",
        "受众对象",
    }

    bullets: list[str] = []
    core_message = _clean_text(slide.get("coreMessage"))
    takeaway = _clean_text(slide.get("actionableTakeaway"))
    reserved = [core_message, takeaway]
    for item in raw_items:
        text = _clean_text(item)
        if not text or text in blocked or text.startswith("目标受众") or text.startswith("受众对象"):
            continue
        if not _is_duplicate_text(text, bullets + reserved):
            bullets.append(text)

    for item in node.get("bullets") or []:
        text = _clean_text(item)
        if text and text not in blocked and not _is_duplicate_text(text, bullets + reserved):
            bullets.append(text)

    while len(bullets) < 3:
        fallback = [
            f"围绕“{node['title']}”展开核心说明",
            f"结合“{node['section']}”明确页面重点",
            "承接后续内容形成完整叙事",
        ][len(bullets)]
        if fallback not in bullets:
            bullets.append(fallback)

    return bullets[:5]


class ContentExpander:
    def __init__(self, llm_service=None):
        self.llm_service = llm_service
        self.last_validation_error: str | None = None

    def expand_content(self, outline_node, context=None, max_tokens=4096):
        prompt = self._build_legacy_prompt(outline_node, context)
        return self.llm_service.generate(prompt, max_tokens=max_tokens)

    def expand_page_content(self, outline_node, context=None, max_tokens=4096) -> dict[str, Any]:
        self.last_validation_error = None
        prompt = self._build_json_prompt(outline_node, context)
        raw = self._generate_protocol_json(prompt, max_tokens=max_tokens)

        try:
            page_content = self._parse_page_content(raw, outline_node)
            page_content_dict = page_content.model_dump()
            return {
                "content": page_content_to_text(page_content_dict),
                "page_content": page_content_dict,
                "raw": raw,
                "message": None,
            }
        except (ValueError, ValidationError) as exc:
            self.last_validation_error = str(exc)
            return {
                "content": raw or "",
                "page_content": None,
                "raw": raw,
                "message": f"structured content validation failed: {exc}",
            }

    def _build_json_prompt(self, outline_node, context):
        return (
            PAGE_CONTENT_JSON_TEMPLATE
            .replace("{outline_node}", json.dumps(self._normalize_outline_node(outline_node), ensure_ascii=False))
            .replace("{context}", _clean_text(context, "No reference context."))
        )

    def _generate_protocol_json(self, prompt: str, max_tokens: int) -> str:
        if hasattr(self.llm_service, "generate_json_schema"):
            raw = self.llm_service.generate_json_schema(
                prompt,
                schema_name="ppt_page_content",
                schema=PAGE_CONTENT_RESPONSE_SCHEMA,
                max_tokens=max_tokens,
            )
            if raw and not raw.startswith("["):
                return raw

        return self.llm_service.generate(prompt, temperature=0.2, max_tokens=max_tokens)

    def _build_legacy_prompt(self, outline_node, context):
        prompt = CONTENT_TEMPLATE
        node = self._normalize_outline_node(outline_node)
        bullets = "\n".join(f"- {item}" for item in node["bullets"]) or "none"

        prompt = prompt.replace("{node_title}", node["title"])
        prompt = prompt.replace("{section}", node["section"])
        prompt = prompt.replace("{goal}", node["goal"])
        prompt = prompt.replace("{bullets}", bullets)
        prompt = prompt.replace("{context}", _clean_text(context, "none"))
        return prompt

    @staticmethod
    def _normalize_outline_node(outline_node) -> dict[str, Any]:
        if isinstance(outline_node, dict):
            bullets_raw = outline_node.get("bullets") or outline_node.get("keyPoints") or []
            if isinstance(bullets_raw, list):
                bullets = [_clean_text(item) for item in bullets_raw if _clean_text(item)]
            else:
                bullets = [_clean_text(bullets_raw)] if _clean_text(bullets_raw) else []

            return {
                "id": _normalize_slide_id(outline_node.get("id") or outline_node.get("slideId")),
                "number": _normalize_slide_number(outline_node.get("number") or outline_node.get("slideNumber")),
                "role": _clean_text(outline_node.get("role") or outline_node.get("slideRole"), "content"),
                "title": _clean_text(outline_node.get("title") or outline_node.get("slideTitle"), "Untitled Slide"),
                "section": _clean_text(outline_node.get("section") or outline_node.get("sectionTitle"), "Ungrouped"),
                "goal": _clean_text(outline_node.get("goal") or outline_node.get("pageGoal"), "Explain the core content of this slide"),
                "bullets": bullets,
            }

        title = _clean_text(outline_node, "Untitled Slide")
        return {
            "id": "slide-001",
            "number": 1,
            "role": "content",
            "title": title,
            "section": "Ungrouped",
            "goal": "Explain the core content of this slide",
            "bullets": [title],
        }

    @staticmethod
    def _parse_page_content(raw: str, outline_node) -> PageContentProtocol:
        data = parse_json_object(raw)
        node = ContentExpander._normalize_outline_node(outline_node)

        data.setdefault("protocolVersion", "ppt-page-content.v1")
        data.setdefault("language", "zh-CN")
        data.setdefault("presentationTitle", node["title"])
        data.setdefault(
            "researchPolicy",
            {
                "triggerReason": "user_requested",
                "depthLevel": "standard",
                "sourcePriority": ["official_sites"],
                "maxSourcesPerSlide": 3,
            },
        )

        slides = data.get("slides") or []
        if slides:
            slide = slides[0]
            slide.setdefault("slideId", node["id"])
            slide.setdefault("slideNumber", node["number"])
            slide.setdefault("slideRole", node["role"])
            slide.setdefault("slideTitle", node["title"])
            slide.setdefault("pageGoal", node["goal"])
            slide.setdefault("keyData", [])
            slide.setdefault("evidencePack", [])
            slide["displayBullets"] = _normalize_display_bullets(slide.get("displayBullets"), node, slide)
            slide["evidencePack"] = _normalize_evidence_pack(slide.get("evidencePack"))

        return PageContentProtocol.model_validate(data)
