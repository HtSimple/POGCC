import re
from typing import Any

from pydantic import ValidationError

from app.prompts.templates import OUTLINE_JSON_TEMPLATE, OUTLINE_TEMPLATE
from app.schema.models import NarrativeOutline
from app.schema.protocol_schemas import OUTLINE_RESPONSE_SCHEMA
from app.utils.json_protocol import parse_json_object


_SECTION_RE = re.compile(r"^(\d+)[\.\u3001]\s*(.+)$")
_SUBSECTION_RE = re.compile(r"^([a-zA-Z])[\.\u3001]\s*(.+)$")


def _clean_text(value: Any, fallback: str = "") -> str:
    text = str(value or "").strip()
    return text or fallback


def _slide_id(number: int) -> str:
    return f"slide-{number:03d}"


def _section_id(number: int) -> str:
    return f"sec-{number:02d}"


def _default_key_points(title: str) -> list[str]:
    title = _clean_text(title, "Slide topic")
    return [
        f"Explain the core background of {title}",
        f"Summarize the key points of {title}",
        f"Clarify the action takeaway of {title}",
    ]


class OutlineMaker:
    def __init__(self, llm_service=None):
        self.llm_service = llm_service
        self.last_used_fallback = False
        self.last_validation_error: str | None = None
        self.last_raw_output: str | None = None
        self.last_schema_error: str | None = None

    def generate_outline(self, topic, requirements=None, reference_context=None, max_tokens=8192):
        self.last_used_fallback = False
        self.last_validation_error = None
        self.last_raw_output = None
        self.last_schema_error = None

        prompt = self._build_json_prompt(topic, requirements, reference_context)
        outline_text = self._generate_protocol_json(prompt, max_tokens=max_tokens)
        self.last_raw_output = outline_text

        try:
            outline = self._parse_protocol_outline(outline_text)
            return outline.model_dump()
        except (ValueError, ValidationError) as exc:
            self.last_used_fallback = True
            self.last_validation_error = str(exc)

        if _clean_text(reference_context):
            fallback = self._reference_context_to_protocol(topic, requirements, reference_context)
            return fallback.model_dump()

        legacy_prompt = self._build_legacy_prompt(topic, requirements)
        legacy_text = self.llm_service.generate(legacy_prompt, max_tokens=max_tokens)
        legacy_outline = self._parse_legacy_outline(legacy_text)
        fallback = self._legacy_to_protocol(legacy_outline, topic)
        return fallback.model_dump()

    def _build_json_prompt(self, topic, requirements, reference_context=None):
        prompt = OUTLINE_JSON_TEMPLATE.replace("{topic}", _clean_text(topic))
        prompt = prompt.replace("{requirements}", _clean_text(requirements, "No extra requirements."))
        prompt = prompt.replace("{reference_context}", _clean_text(reference_context, "No reference context."))
        return prompt

    def _generate_protocol_json(self, prompt: str, max_tokens: int) -> str:
        if hasattr(self.llm_service, "generate_json_schema"):
            raw = self.llm_service.generate_json_schema(
                prompt,
                schema_name="ppt_narrative_outline",
                schema=OUTLINE_RESPONSE_SCHEMA,
                max_tokens=max_tokens,
            )
            if raw and not raw.startswith("["):
                return raw
            self.last_schema_error = raw or "empty json_schema response"

        if hasattr(self.llm_service, "generate_json_object"):
            json_prompt = (
                prompt
                + "\n\nReturn a single valid JSON object only. "
                + "Do not wrap it in Markdown fences. "
                + "All slides must be continuous from slide-001 / slideNumber 1 "
                + "through targetSlideCount."
            )
            raw = self.llm_service.generate_json_object(json_prompt, temperature=0.2, max_tokens=max_tokens)
            if raw and not raw.startswith("["):
                return raw
            self.last_schema_error = (self.last_schema_error or "") + "\njson_object fallback failed: " + (raw or "empty response")

        return self.llm_service.generate(prompt, temperature=0.2, max_tokens=max_tokens)

    def _build_legacy_prompt(self, topic, requirements):
        prompt = OUTLINE_TEMPLATE.replace("{topic}", _clean_text(topic))
        return prompt.replace("{requirements}", _clean_text(requirements))

    @staticmethod
    def _merge_requirements(requirements, reference_context) -> str:
        parts = [_clean_text(requirements), _clean_text(reference_context)]
        return "\n\n".join(part for part in parts if part)

    @staticmethod
    def _parse_protocol_outline(outline_text: str) -> NarrativeOutline:
        data = parse_json_object(outline_text)
        return NarrativeOutline.model_validate(data)

    @staticmethod
    def _parse_legacy_outline(outline_text: str) -> dict[str, Any]:
        lines = [line.strip().lstrip("-").strip() for line in (outline_text or "").splitlines() if line.strip()]
        if not lines:
            return {"title": "", "sections": []}

        outline: dict[str, Any] = {"title": lines[0], "sections": []}
        current_section: dict[str, Any] | None = None

        for line in lines[1:]:
            section_match = _SECTION_RE.match(line)
            if section_match:
                current_section = {"title": section_match.group(2).strip(), "subsections": []}
                outline["sections"].append(current_section)
                continue

            subsection_match = _SUBSECTION_RE.match(line)
            if subsection_match:
                if current_section is None:
                    current_section = {"title": "Ungrouped", "subsections": []}
                    outline["sections"].append(current_section)
                current_section["subsections"].append({
                    "title": subsection_match.group(2).strip(),
                    "goal": "",
                    "bullets": [],
                })

        return outline

    @staticmethod
    def _legacy_to_protocol(legacy_outline: dict[str, Any], topic: str) -> NarrativeOutline:
        title = _clean_text(legacy_outline.get("title"), _clean_text(topic, "PPT Generation Task"))
        sections_input = legacy_outline.get("sections") or []

        protocol_sections = []
        slide_number = 1

        if not sections_input:
            sections_input = [
                {"title": "Background and Goals", "subsections": ["Topic Background", "Task Goals"]},
                {"title": "Plan and Content", "subsections": ["Core Plan", "Key Content"]},
                {"title": "Summary and Outlook", "subsections": ["Summary", "Next Steps"]},
            ]

        for section_index, section in enumerate(sections_input, start=1):
            section_title = _clean_text(section.get("title"), f"Section {section_index}")
            subsections = section.get("subsections") or [section_title]
            section_slides = []
            start = slide_number

            for subsection in subsections:
                if isinstance(subsection, dict):
                    slide_title = _clean_text(subsection.get("title"), section_title)
                    key_points = subsection.get("bullets") or _default_key_points(slide_title)
                else:
                    slide_title = _clean_text(subsection, section_title)
                    key_points = _default_key_points(slide_title)

                key_points = [_clean_text(item) for item in key_points if _clean_text(item)]
                if len(key_points) < 2:
                    key_points = _default_key_points(slide_title)

                section_slides.append({
                    "slideId": _slide_id(slide_number),
                    "slideNumber": slide_number,
                    "slideRole": "cover" if slide_number == 1 else "content",
                    "slideTitle": slide_title,
                    "keyPoints": key_points[:5],
                    "notes": "",
                })
                slide_number += 1

            protocol_sections.append({
                "sectionId": _section_id(section_index),
                "sectionTitle": section_title,
                "sectionObjective": f"Explain the core content and value of {section_title}",
                "slideRange": {"start": start, "end": slide_number - 1},
                "slides": section_slides,
            })

        while slide_number <= 3:
            if not protocol_sections:
                protocol_sections.append({
                    "sectionId": "sec-01",
                    "sectionTitle": "Task Overview",
                    "sectionObjective": "Explain the task background, goals, and core content",
                    "slideRange": {"start": 1, "end": 1},
                    "slides": [],
                })
            protocol_sections[-1]["slides"].append({
                "slideId": _slide_id(slide_number),
                "slideNumber": slide_number,
                "slideRole": "summary" if slide_number == 3 else "content",
                "slideTitle": "Supplementary Slide",
                "keyPoints": ["Add core content details", "Complete the narrative structure"],
                "notes": "",
            })
            protocol_sections[-1]["slideRange"]["end"] = slide_number
            slide_number += 1

        return NarrativeOutline.model_validate({
            "protocolVersion": "ppt-narrative-outline.v1",
            "language": "zh-CN",
            "presentationTitle": title,
            "targetSlideCount": slide_number - 1,
            "sections": protocol_sections,
        })

    @staticmethod
    def _reference_context_to_protocol(topic: str, requirements: str | None, reference_context: str) -> NarrativeOutline:
        title = _clean_text(topic, "Reference-based PPT")
        target_slide_count = OutlineMaker._extract_target_slide_count(requirements, default=6)
        keywords = OutlineMaker._extract_reference_keywords(reference_context)
        if not keywords:
            keywords = ["Reference Background", "Key Concepts", "Application Scenarios", "Challenges", "Trends", "Summary"]

        slides = []
        for number in range(1, target_slide_count + 1):
            keyword = keywords[(number - 1) % len(keywords)]
            slides.append({
                "slideId": _slide_id(number),
                "slideNumber": number,
                "slideRole": "cover" if number == 1 else ("summary" if number == target_slide_count else "content"),
                "slideTitle": keyword,
                "keyPoints": [
                    f"Summarize reference material about {keyword}",
                    f"Explain why {keyword} matters to {title}",
                    f"Connect {keyword} with the presentation goal",
                ],
                "notes": "Generated from uploaded reference context because JSON validation failed.",
            })

        midpoint = max(1, target_slide_count // 2)
        sections = [
            {
                "sectionId": "sec-01",
                "sectionTitle": "Reference Overview",
                "sectionObjective": "Organize the uploaded reference material into opening context",
                "slideRange": {"start": 1, "end": midpoint},
                "slides": slides[:midpoint],
            },
            {
                "sectionId": "sec-02",
                "sectionTitle": "Reference Insights",
                "sectionObjective": "Develop the key insights extracted from the uploaded reference material",
                "slideRange": {"start": midpoint + 1, "end": target_slide_count},
                "slides": slides[midpoint:],
            },
        ]
        sections = [section for section in sections if section["slides"]]

        return NarrativeOutline.model_validate({
            "protocolVersion": "ppt-narrative-outline.v1",
            "language": "zh-CN",
            "presentationTitle": title,
            "targetSlideCount": target_slide_count,
            "sections": sections,
        })

    @staticmethod
    def _extract_target_slide_count(requirements: str | None, default: int) -> int:
        match = re.search(r"(\d+)", requirements or "")
        if not match:
            return default
        return max(3, min(int(match.group(1)), 50))

    @staticmethod
    def _extract_reference_keywords(reference_context: str) -> list[str]:
        candidates = []
        for raw in re.split(r"[\n。；;:：,.，]", reference_context):
            text = raw.strip()
            if not text or text.startswith("[Reference") or text.startswith("source_file") or text.startswith("score"):
                continue
            text = re.sub(r"^text:\s*", "", text).strip()
            if 4 <= len(text) <= 40:
                candidates.append(text)

        seen = set()
        keywords = []
        for item in candidates:
            if item not in seen:
                seen.add(item)
                keywords.append(item)
            if len(keywords) >= 12:
                break
        return keywords
