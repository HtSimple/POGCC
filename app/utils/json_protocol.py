import json
import re
from typing import Any


_JSON_BLOCK_RE = re.compile(r"```(?:json)?\s*(.*?)```", re.DOTALL | re.IGNORECASE)


def extract_json_text(text: str) -> str:
    """Return the most likely JSON object text from an LLM response."""
    if not text:
        raise ValueError("empty response")

    match = _JSON_BLOCK_RE.search(text)
    if match:
        return match.group(1).strip()

    stripped = text.strip()
    start = stripped.find("{")
    end = stripped.rfind("}")
    if start == -1 or end == -1 or end <= start:
        raise ValueError("no JSON object found")
    return stripped[start : end + 1]


def parse_json_object(text: str) -> dict[str, Any]:
    data = json.loads(extract_json_text(text))
    if not isinstance(data, dict):
        raise ValueError("JSON root must be an object")
    return data


def page_content_to_text(page_content: dict[str, Any]) -> str:
    """Flatten the first protocol slide into the legacy text content field."""
    slides = page_content.get("slides") or []
    if not slides:
        return ""

    slide = slides[0]
    lines = [
        str(slide.get("coreMessage") or "").strip(),
        "",
        *[f"- {item}" for item in slide.get("displayBullets", []) if str(item).strip()],
    ]
    takeaway = str(slide.get("actionableTakeaway") or "").strip()
    if takeaway:
        lines.extend(["", takeaway])
    return "\n".join(line for line in lines if line is not None).strip()
