from __future__ import annotations

import sys
from pathlib import Path

import pytest

CURRENT = Path(__file__).resolve()
TESTING_DIR = CURRENT.parents[1]
if str(TESTING_DIR) not in sys.path:
    sys.path.insert(0, str(TESTING_DIR))

from _test_utils import add_project_root_to_path

ROOT = add_project_root_to_path(CURRENT)

from app.schema.models import PageContentProtocol


def build_valid_page_content(slide_count: int = 3) -> dict:
    slides = []
    for i in range(1, slide_count + 1):
        slides.append(
            {
                "slideId": f"slide-{i:03d}",
                "slideNumber": i,
                "slideRole": "content" if i > 1 else "cover",
                "pageGoal": "说明本页需要表达的核心目标",
                "slideTitle": f"内容页{i}",
                "coreMessage": "本页围绕主题形成一个清晰、可讲述的核心观点。",
                "displayBullets": [
                    "第一条页面展示要点",
                    "第二条页面展示要点",
                    "第三条页面展示要点",
                ],
                "keyData": [],
                "evidencePack": [
                    {
                        "sourceRefId": "src-001",
                        "claim": "测试证据用于支撑页面核心观点",
                        "sourceTitle": "测试来源",
                        "sourceType": "official_sites",
                        "url": "https://example.com",
                        "publishDate": "2026-05-23",
                        "credibility": "high",
                        "quote": "测试引用内容",
                    }
                ],
                "actionableTakeaway": "本页可直接用于PPT展示。",
                "speakerNotes": "这里是演讲备注，用于辅助讲述该页面内容。",
            }
        )
    return {
        "protocolVersion": "ppt-page-content.v1",
        "language": "zh-CN",
        "presentationTitle": "测试PPT",
        "researchPolicy": {
            "triggerReason": "user_requested",
            "depthLevel": "standard",
            "sourcePriority": ["official_sites", "academic_sources"],
            "maxSourcesPerSlide": 3,
        },
        "slides": slides,
    }


def test_valid_page_content_schema_passes():
    content = PageContentProtocol(**build_valid_page_content(3))
    assert len(content.slides) == 3
    assert content.slides[0].speakerNotes


def test_page_content_rejects_too_few_bullets():
    data = build_valid_page_content(1)
    data["slides"][0]["displayBullets"] = ["太少", "不够"]
    with pytest.raises(Exception):
        PageContentProtocol(**data)


def test_page_content_requires_speaker_notes():
    data = build_valid_page_content(1)
    data["slides"][0]["speakerNotes"] = ""
    with pytest.raises(Exception):
        PageContentProtocol(**data)


def test_page_content_evidence_shape():
    content = PageContentProtocol(**build_valid_page_content(2)).model_dump()
    for slide in content["slides"]:
        assert "evidencePack" in slide
        for ev in slide["evidencePack"]:
            assert ev["sourceRefId"].startswith("src-")
            assert ev["claim"]
            assert ev["credibility"] in {"high", "medium"}
