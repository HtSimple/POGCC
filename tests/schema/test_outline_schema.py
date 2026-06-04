from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest

# Make repository imports work no matter where pytest is launched.
CURRENT = Path(__file__).resolve()
TESTING_DIR = CURRENT.parents[1]
if str(TESTING_DIR) not in sys.path:
    sys.path.insert(0, str(TESTING_DIR))

from _test_utils import add_project_root_to_path, flatten_outline_slides

ROOT = add_project_root_to_path(CURRENT)

from app.schema.models import NarrativeOutline


def build_valid_outline(slide_count: int = 5) -> dict:
    slides = []
    for i in range(1, slide_count + 1):
        role = "cover" if i == 1 else ("summary" if i == slide_count else "content")
        slides.append(
            {
                "slideId": f"slide-{i:03d}",
                "slideNumber": i,
                "slideRole": role,
                "slideTitle": f"测试页面{i}",
                "keyPoints": [f"要点{i}-1", f"要点{i}-2", f"要点{i}-3"],
                "notes": "用于测试大纲结构。",
            }
        )
    return {
        "protocolVersion": "ppt-narrative-outline.v1",
        "language": "zh-CN",
        "presentationTitle": "测试PPT",
        "targetSlideCount": slide_count,
        "sections": [
            {
                "sectionId": "sec-01",
                "sectionTitle": "测试章节",
                "sectionObjective": "验证结构化大纲的字段完整性和页码连续性",
                "slideRange": {"start": 1, "end": slide_count},
                "slides": slides,
            }
        ],
    }


def test_valid_outline_schema_passes():
    outline = NarrativeOutline(**build_valid_outline(5))
    assert outline.targetSlideCount == 5
    slides = flatten_outline_slides(outline.model_dump())
    assert len(slides) == 5
    assert slides[0]["slideId"] == "slide-001"


def test_outline_rejects_non_continuous_slide_numbers():
    data = build_valid_outline(5)
    data["sections"][0]["slides"][2]["slideNumber"] = 9
    with pytest.raises(Exception):
        NarrativeOutline(**data)


def test_outline_rejects_mismatched_slide_id():
    data = build_valid_outline(4)
    data["sections"][0]["slides"][1]["slideId"] = "slide-999"
    with pytest.raises(Exception):
        NarrativeOutline(**data)


def test_outline_rejects_bad_section_range():
    data = build_valid_outline(4)
    data["sections"][0]["slideRange"] = {"start": 1, "end": 3}
    with pytest.raises(Exception):
        NarrativeOutline(**data)


def test_outline_has_required_ppt_fields():
    outline = NarrativeOutline(**build_valid_outline(6)).model_dump()
    assert outline["protocolVersion"] == "ppt-narrative-outline.v1"
    assert outline["presentationTitle"]
    assert outline["sections"]
    for section in outline["sections"]:
        assert section["sectionId"].startswith("sec-")
        assert section["sectionObjective"]
        for slide in section["slides"]:
            assert slide["slideTitle"]
            assert len(slide["keyPoints"]) >= 2
