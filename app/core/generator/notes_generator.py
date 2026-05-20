import json
import re
from typing import Any

from app.prompts.templates import SPEAKER_NOTES_JSON_TEMPLATE
from app.utils.json_protocol import parse_json_object


def _clean_text(value: Any, fallback: str = "") -> str:
    text = str(value or "").strip()
    return text or fallback


def _clip_text(value: Any, limit: int, fallback: str = "") -> str:
    text = _clean_text(value, fallback)
    if len(text) <= limit:
        return text
    return text[:limit].rstrip() + "\n...[truncated for speaker notes generation]"


def _is_provider_error(text: str) -> bool:
    stripped = _clean_text(text)
    if not stripped.startswith("["):
        return False
    lower = stripped.lower()
    return any(marker in lower for marker in ["deepseek", "qwen", "api", "max_tokens", "error", "failed"])


class NotesGenerator:
    def __init__(self, llm_service=None):
        self.llm_service = llm_service
        self.last_raw_output: str | None = None
        self.last_validation_error: str | None = None

    def generate_notes(
        self,
        project_id: str | None,
        slide_id: str,
        slide_title: str,
        slide_content: str,
        knowledge_evidence: str | None = None,
        style_requirement: str | None = None,
        max_tokens: int = 4096,
    ) -> dict[str, str]:
        self.last_raw_output = None
        self.last_validation_error = None

        prompt = self._build_prompt(
            project_id=project_id,
            slide_id=slide_id,
            slide_title=slide_title,
            slide_content=slide_content,
            knowledge_evidence=knowledge_evidence,
            style_requirement=style_requirement,
        )
        raw = self._generate_json(prompt, max_tokens=max_tokens)
        if _is_provider_error(raw):
            raw = self.llm_service.generate(prompt, temperature=0.2, max_tokens=max_tokens * 2)
        self.last_raw_output = raw

        try:
            notes = self._extract_notes(raw)
            self._validate_notes(notes, slide_content)
            return {"notes": notes, "raw": raw}
        except Exception as exc:
            self.last_validation_error = str(exc)
            raise ValueError(f"speaker notes validation failed: {exc}") from exc

    def _build_prompt(
        self,
        project_id: str | None,
        slide_id: str,
        slide_title: str,
        slide_content: str,
        knowledge_evidence: str | None,
        style_requirement: str | None,
    ) -> str:
        replacements = {
            "{project_id}": _clean_text(project_id, "default"),
            "{slide_id}": _clean_text(slide_id, "slide-001"),
            "{slide_title}": _clip_text(slide_title, 120, "未命名页面"),
            "{slide_content}": _clip_text(slide_content, 1200, "无正文内容"),
            "{knowledge_evidence}": _clip_text(knowledge_evidence, 1800, "无额外证据"),
            "{style_requirement}": _clip_text(style_requirement, 800, "口语化、清晰、适合课堂或汇报场景"),
        }

        prompt = SPEAKER_NOTES_JSON_TEMPLATE
        for old, new in replacements.items():
            prompt = prompt.replace(old, new)
        return prompt

    def _generate_json(self, prompt: str, max_tokens: int) -> str:
        if hasattr(self.llm_service, "generate_json_object"):
            raw = self.llm_service.generate_json_object(prompt, max_tokens=max_tokens, temperature=0.2)
            if raw and not _is_provider_error(raw):
                return raw

        return self.llm_service.generate(prompt, temperature=0.2, max_tokens=max_tokens)

    @staticmethod
    def _extract_notes(raw: str) -> str:
        try:
            data = parse_json_object(raw)
            return _clean_text(data.get("notes"))
        except Exception as json_exc:
            notes = NotesGenerator._plain_text_notes(raw)
            if notes:
                return notes
            raise json_exc

    @staticmethod
    def _plain_text_notes(raw: str) -> str:
        text = _clean_text(raw)
        if not text:
            return ""

        if _is_provider_error(text):
            return ""

        fence_match = re.search(r"```(?:text|markdown)?\s*(.*?)```", text, re.DOTALL | re.IGNORECASE)
        if fence_match:
            text = fence_match.group(1).strip()

        text = re.sub(r"^\s*(notes|speaker notes|演讲者备注|备注)\s*[:：]\s*", "", text, flags=re.IGNORECASE)
        text = text.strip().strip('"').strip("'").strip()
        return text

    @staticmethod
    def _validate_notes(notes: str, slide_content: str) -> None:
        if len(notes) < 20:
            raise ValueError("notes must contain at least 20 characters")

        compact_notes = "".join(notes.split())
        compact_content = "".join(_clean_text(slide_content).split())
        if compact_notes and compact_notes == compact_content:
            raise ValueError("notes must not directly copy slide content")

        try:
            json.loads(notes)
        except ValueError:
            return
        raise ValueError("notes must be natural language, not nested JSON")
