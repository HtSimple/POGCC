import json
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

        return PageContentProtocol.model_validate(data)
