import json
import logging
from datetime import date
from typing import Any

from pydantic import ValidationError


logger = logging.getLogger(__name__)

from app.prompts.templates import (
    CONTENT_REVISE_TEXT_TEMPLATE,
    CONTENT_TEMPLATE,
    PAGE_CONTENT_JSON_TEMPLATE,
    PAGE_CONTENT_REVISE_JSON_TEMPLATE,
)
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


_RESEARCH_TRIGGER_REASONS = frozenset({"user_requested", "insufficient_input", "fact_verification"})
_RESEARCH_DEPTH_LEVELS = frozenset({"light", "standard", "deep"})
_RESEARCH_SOURCE_PRIORITY = frozenset({
    "local_document",
    "official_sites",
    "government_reports",
    "academic_sources",
    "authoritative_media",
    "industry_reports",
})


def _normalize_research_policy(policy: Any) -> dict[str, Any]:
    """将 LLM 可能返回的非协议 researchPolicy 字段修正为 ppt-page-content.v1 要求。"""
    default: dict[str, Any] = {
        "triggerReason": "user_requested",
        "depthLevel": "standard",
        "sourcePriority": ["local_document", "official_sites"],
        "maxSourcesPerSlide": 3,
    }
    if isinstance(policy, str):
        try:
            policy = json.loads(policy)
        except Exception:
            return dict(default)
    if not isinstance(policy, dict):
        return dict(default)

    merged = dict(policy)
    merged.setdefault("triggerReason", merged.get("trigger_reason"))
    merged.setdefault("depthLevel", merged.get("depth_level"))
    merged.setdefault("sourcePriority", merged.get("source_priority"))
    if merged.get("preferLocal") is None:
        merged["preferLocal"] = merged.get("prefer_local")
    if merged.get("allowedSources") is None:
        merged["allowedSources"] = merged.get("allowed_sources")

    result = dict(default)
    trigger = _clean_text(merged.get("triggerReason"))
    if trigger in _RESEARCH_TRIGGER_REASONS:
        result["triggerReason"] = trigger

    depth = _clean_text(merged.get("depthLevel"))
    if depth in _RESEARCH_DEPTH_LEVELS:
        result["depthLevel"] = depth

    source_priority = merged.get("sourcePriority")
    cleaned_priority: list[str] = []
    if isinstance(source_priority, list):
        raw_priority = [
            item for item in (_normalize_source_type(entry) for entry in source_priority)
            if item in _RESEARCH_SOURCE_PRIORITY
        ]
        seen: set[str] = set()
        cleaned_priority = []
        for item in raw_priority:
            if item not in seen:
                seen.add(item)
                cleaned_priority.append(item)
    if cleaned_priority:
        if len(cleaned_priority) > 6:
            logger.warning(
                "sourcePriority truncated: LLM generated %d items (%s), keeping first 6",
                len(cleaned_priority), cleaned_priority,
            )
        result["sourcePriority"] = cleaned_priority[:6]
    elif merged.get("preferLocal") in (True, "true", "True", 1, "1"):
        result["sourcePriority"] = ["local_document", "official_sites"]
    elif merged.get("allowedSources"):
        result["sourcePriority"] = ["local_document", "official_sites"]

    try:
        max_sources = int(merged.get("maxSourcesPerSlide"))
        if 1 <= max_sources <= 6:
            result["maxSourcesPerSlide"] = max_sources
    except (TypeError, ValueError):
        pass

    return {
        "triggerReason": result["triggerReason"],
        "depthLevel": result["depthLevel"],
        "sourcePriority": list(result["sourcePriority"]),
        "maxSourcesPerSlide": result["maxSourcesPerSlide"],
    }


def _extract_research_policy(data: dict[str, Any]) -> Any:
    policy = data.get("researchPolicy")
    if isinstance(policy, dict) and policy:
        return policy
    hoisted: dict[str, Any] = {}
    for key in (
        "preferLocal",
        "prefer_local",
        "allowedSources",
        "allowed_sources",
        "triggerReason",
        "trigger_reason",
        "depthLevel",
        "depth_level",
        "sourcePriority",
        "source_priority",
        "maxSourcesPerSlide",
    ):
        if key in data:
            hoisted[key] = data[key]
    return hoisted or policy


_SLIDE_HOIST_KEYS = (
    "slideId",
    "slideNumber",
    "slideRole",
    "pageGoal",
    "slideTitle",
    "coreMessage",
    "displayBullets",
    "keyData",
    "evidencePack",
    "actionableTakeaway",
    "speakerNotes",
)


def _lines_from_content_text(text: str) -> list[str]:
    items: list[str] = []
    for line in (text or "").splitlines():
        stripped = _clean_text(line.lstrip("-•·*\t "))
        if stripped:
            items.append(stripped[:120])
    return items


def _ensure_core_message(text: str, node: dict[str, Any]) -> str:
    cleaned = _clean_text(text)
    if len(cleaned) >= 12:
        return cleaned[:140]
    combined = f"{node['title']}：{node['goal']}"
    if len(combined) >= 12:
        return combined[:140]
    return f"本页围绕{node['title']}展开核心说明"[:140]


def _ensure_speaker_notes(text: str, node: dict[str, Any], core_message: str) -> str:
    cleaned = _clean_text(text)
    if len(cleaned) >= 10:
        return cleaned[:600]
    fallback = f"各位好，接下来我们来看{node['title']}。{core_message}"
    return fallback[:600] if len(fallback) >= 10 else f"各位好，本页介绍{node['title']}的相关内容。"[:600]


def _extract_partial_slide(data: dict[str, Any]) -> dict[str, Any]:
    partial: dict[str, Any] = {}
    for key in _SLIDE_HOIST_KEYS:
        if key in data and data[key] is not None:
            partial[key] = data[key]
    return partial


def _build_fallback_slide(
    node: dict[str, Any],
    source_text: str = "",
    partial: dict[str, Any] | None = None,
) -> dict[str, Any]:
    partial = dict(partial or {})
    content_lines = _lines_from_content_text(source_text)
    core_message = _ensure_core_message(
        _clean_text(partial.get("coreMessage")) or (content_lines[0] if content_lines else ""),
        node,
    )
    raw_bullets = partial.get("displayBullets")
    if not isinstance(raw_bullets, list) or not raw_bullets:
        raw_bullets = content_lines[1:] or content_lines or list(node.get("bullets") or [])

    slide: dict[str, Any] = {
        "slideId": _normalize_slide_id(partial.get("slideId") or node["id"]),
        "slideNumber": _normalize_slide_number(partial.get("slideNumber") or node["number"]),
        "slideRole": _clean_text(partial.get("slideRole") or node["role"], "content"),
        "pageGoal": _clean_text(partial.get("pageGoal") or node["goal"], "Explain the core content of this slide"),
        "slideTitle": _clean_text(partial.get("slideTitle") or node["title"], "Untitled Slide"),
        "coreMessage": core_message,
        "displayBullets": raw_bullets,
        "keyData": partial.get("keyData") if isinstance(partial.get("keyData"), list) else [],
        "evidencePack": partial.get("evidencePack") if isinstance(partial.get("evidencePack"), list) else [],
        "actionableTakeaway": _clean_text(partial.get("actionableTakeaway"), ""),
        "speakerNotes": _ensure_speaker_notes(
            _clean_text(partial.get("speakerNotes")) or source_text,
            node,
            core_message,
        ),
    }
    slide["keyData"] = _normalize_key_data(slide.get("keyData"))
    slide["displayBullets"] = _normalize_display_bullets(slide.get("displayBullets"), node, slide)
    slide["evidencePack"] = _normalize_evidence_pack(slide.get("evidencePack"))
    slide["speakerNotes"] = _ensure_speaker_notes(slide.get("speakerNotes"), node, core_message)
    return slide


def _prepare_page_content_data(
    data: dict[str, Any],
    node: dict[str, Any],
    *,
    fallback_content: str = "",
) -> dict[str, Any]:
    data.setdefault("protocolVersion", "ppt-page-content.v1")
    data.setdefault("language", "zh-CN")
    data.setdefault("presentationTitle", node["title"])
    data["researchPolicy"] = _normalize_research_policy(_extract_research_policy(data))

    slides = data.get("slides")
    if not isinstance(slides, list):
        slides = []
    partial = _extract_partial_slide(data)
    if slides and isinstance(slides[0], dict):
        partial = {**partial, **slides[0]}
        slides = [slides[0]]
    elif not slides:
        slides = [_build_fallback_slide(node, fallback_content, partial)]
    else:
        slides = [_build_fallback_slide(node, fallback_content, partial)]

    slide = slides[0]
    slide.setdefault("slideId", node["id"])
    slide.setdefault("slideNumber", node["number"])
    slide.setdefault("slideRole", node["role"])
    slide.setdefault("slideTitle", node["title"])
    slide.setdefault("pageGoal", node["goal"])
    slide.setdefault("keyData", [])
    slide.setdefault("evidencePack", [])
    slide.setdefault("coreMessage", _ensure_core_message(slide.get("coreMessage"), node))
    slide["keyData"] = _normalize_key_data(slide.get("keyData"))
    slide["displayBullets"] = _normalize_display_bullets(slide.get("displayBullets"), node, slide)
    slide["evidencePack"] = _normalize_evidence_pack(slide.get("evidencePack"))
    slide["speakerNotes"] = _ensure_speaker_notes(slide.get("speakerNotes"), node, slide["coreMessage"])
    data["slides"] = [slide]
    return data


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


def _normalize_key_data(items: Any) -> list[dict[str, Any]]:
    if not isinstance(items, list):
        return []

    normalized: list[dict[str, Any]] = []
    today = date.today().year
    for index, item in enumerate(items, start=1):
        if not isinstance(item, dict):
            continue

        label = _clean_text(item.get("label"))
        if len(label) < 2:
            continue

        raw_value = item.get("value")
        value: float | None = None
        if isinstance(raw_value, (int, float)) and not isinstance(raw_value, bool):
            value = float(raw_value)
        elif isinstance(raw_value, str):
            stripped = raw_value.strip()
            if stripped.replace(".", "", 1).isdigit():
                value = float(stripped)

        if value is None:
            continue

        unit = _clean_text(item.get("unit"))
        if not unit:
            continue

        year_raw = item.get("year")
        year: int | None = None
        if isinstance(year_raw, int) and not isinstance(year_raw, bool):
            year = year_raw
        elif isinstance(year_raw, str) and year_raw.strip().isdigit():
            year = int(year_raw.strip())

        if year is None or year < 1990 or year > 2100:
            year = today

        source_ref_id = _clean_text(item.get("sourceRefId"), f"src-{index:03d}")
        if not source_ref_id.startswith("src-") or len(source_ref_id) != 7:
            source_ref_id = f"src-{index:03d}"

        normalized.append({
            "label": label[:60],
            "value": value,
            "unit": unit[:20],
            "year": year,
            "sourceRefId": source_ref_id,
        })

    return normalized[:4]


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

    if len(normalized) > 6:
        logger.warning(
            "evidencePack truncated: LLM generated %d items, keeping first 6. "
            "Dropped refs: %s",
            len(normalized),
            [item.get("sourceRefId", "?") for item in normalized[6:]],
        )
        normalized = normalized[:6]

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


def _is_llm_error_text(text: str | None) -> bool:
    if not text:
        return True
    stripped = text.strip()
    return stripped.startswith("[") and "]" in stripped[:40]


def _clean_revised_text(raw: str) -> str:
    text = str(raw or "").strip()
    if not text:
        return ""
    if "```" in text:
        parts = text.split("```")
        if len(parts) >= 3:
            text = parts[1]
            if text.lstrip().lower().startswith("markdown"):
                text = text.split("\n", 1)[-1]
        text = text.strip()
    for marker in ("【最终回答】", "【最终答案】", "修订后的正文：", "修订后正文："):
        if marker in text:
            text = text.split(marker)[-1].strip()
    return text.strip()


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
        return self._generate_page_content(outline_node, prompt, max_tokens=max_tokens)

    def revise_page_content(
        self,
        outline_node,
        context=None,
        current_content: str = "",
        revision_suggestion: str = "",
        max_tokens=4096,
    ) -> dict[str, Any]:
        self.last_validation_error = None
        prompt = self._build_revise_json_prompt(
            outline_node,
            context,
            current_content,
            revision_suggestion,
        )
        return self._generate_page_content(
            outline_node,
            prompt,
            max_tokens=max_tokens,
            prefer_json_object=True,
            fallback_content=current_content,
        )

    def revise_page_content_text(
        self,
        outline_node,
        current_content: str,
        revision_suggestion: str,
        max_tokens: int = 1536,
    ) -> dict[str, Any]:
        node = self._normalize_outline_node(outline_node)
        bullet_lines = node.get("bullets") or []
        bullets_text = "\n".join(f"- {item}" for item in bullet_lines[:4] if _clean_text(item)) or "- 无"
        prompt = (
            CONTENT_REVISE_TEXT_TEMPLATE.replace("{slide_title}", _clean_text(node["title"], "未命名页面"))
            .replace("{bullets}", bullets_text)
            .replace("{current_content}", _clean_text(current_content, "无正文内容"))
            .replace("{revision_suggestion}", _clean_text(revision_suggestion, "无修改建议"))
        )
        raw = self.llm_service.generate(prompt, temperature=0.3, max_tokens=max_tokens)
        content = _clean_revised_text(raw)
        if _is_llm_error_text(raw) or not content:
            message = raw if _is_llm_error_text(raw) else "模型未返回有效正文"
            return {"success": False, "content": "", "message": message}
        return {"success": True, "content": content[:3000], "message": "content revised"}

    def _generate_page_content(
        self,
        outline_node,
        prompt: str,
        max_tokens: int,
        *,
        prefer_json_object: bool = False,
        fallback_content: str = "",
    ) -> dict[str, Any]:
        raw = self._generate_protocol_json(
            prompt,
            max_tokens=max_tokens,
            prefer_json_object=prefer_json_object,
        )
        try:
            page_content = self._parse_page_content(
                raw,
                outline_node,
                fallback_content=fallback_content,
            )
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

    def _build_revise_json_prompt(
        self,
        outline_node,
        context,
        current_content: str,
        revision_suggestion: str,
    ) -> str:
        return (
            PAGE_CONTENT_REVISE_JSON_TEMPLATE.replace(
                "{outline_node}",
                json.dumps(self._normalize_outline_node(outline_node), ensure_ascii=False),
            )
            .replace("{context}", _clean_text(context, "No reference context."))
            .replace("{current_content}", _clean_text(current_content, "无正文内容"))
            .replace("{revision_suggestion}", _clean_text(revision_suggestion, "无修改建议"))
        )

    def _generate_protocol_json(
        self,
        prompt: str,
        max_tokens: int,
        *,
        prefer_json_object: bool = False,
    ) -> str:
        if not prefer_json_object and hasattr(self.llm_service, "generate_json_schema"):
            raw = self.llm_service.generate_json_schema(
                prompt,
                schema_name="ppt_page_content",
                schema=PAGE_CONTENT_RESPONSE_SCHEMA,
                max_tokens=max_tokens,
            )
            if raw and not raw.startswith("["):
                return raw

        if hasattr(self.llm_service, "generate_json_object"):
            raw = self.llm_service.generate_json_object(prompt, max_tokens=max_tokens, temperature=0.2)
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
    def _parse_page_content(
        raw: str,
        outline_node,
        *,
        fallback_content: str = "",
    ) -> PageContentProtocol:
        data = parse_json_object(raw)
        node = ContentExpander._normalize_outline_node(outline_node)
        prepared = _prepare_page_content_data(data, node, fallback_content=fallback_content)
        try:
            return PageContentProtocol.model_validate(prepared)
        except ValidationError:
            prepared = _prepare_page_content_data(data, node, fallback_content=fallback_content)
            prepared["researchPolicy"] = _normalize_research_policy(_extract_research_policy(prepared))
            return PageContentProtocol.model_validate(prepared)
