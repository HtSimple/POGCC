import asyncio
import json
from types import SimpleNamespace

import pytest
from pydantic import ValidationError

from app.api.routes.generator import expand_content, generate_outline
from app.core.generator.outline_maker import OutlineMaker
from app.schema.models import ExpandContentRequest, GenerateOutlineRequest, NarrativeOutline, PageContentProtocol
from app.utils.json_protocol import parse_json_object


VALID_OUTLINE = {
    "protocolVersion": "ppt-narrative-outline.v1",
    "language": "zh-CN",
    "presentationTitle": "PPT Outline System",
    "targetSlideCount": 3,
    "sections": [
        {
            "sectionId": "sec-01",
            "sectionTitle": "Project Overview",
            "sectionObjective": "Explain the project background and goals",
            "slideRange": {"start": 1, "end": 3},
            "slides": [
                {
                    "slideId": "slide-001",
                    "slideNumber": 1,
                    "slideRole": "cover",
                    "slideTitle": "Project Overview",
                    "keyPoints": ["Introduce the background", "Clarify the goal"],
                    "notes": "",
                },
                {
                    "slideId": "slide-002",
                    "slideNumber": 2,
                    "slideRole": "content",
                    "slideTitle": "Core Features",
                    "keyPoints": ["Generate outlines", "Expand slide content"],
                    "notes": "",
                },
                {
                    "slideId": "slide-003",
                    "slideNumber": 3,
                    "slideRole": "summary",
                    "slideTitle": "Summary",
                    "keyPoints": ["Summarize results", "Plan next steps"],
                    "notes": "",
                },
            ],
        }
    ],
}


VALID_PAGE_CONTENT = {
    "protocolVersion": "ppt-page-content.v1",
    "language": "zh-CN",
    "presentationTitle": "PPT Outline System",
    "researchPolicy": {
        "triggerReason": "user_requested",
        "depthLevel": "standard",
        "sourcePriority": ["official_sites"],
        "maxSourcesPerSlide": 3,
    },
    "slides": [
        {
            "slideId": "slide-001",
            "slideNumber": 1,
            "slideRole": "content",
            "pageGoal": "Explain the core capability and value",
            "slideTitle": "Core Features",
            "coreMessage": "The system improves generation stability through structured protocols.",
            "displayBullets": ["Unified outline schema", "Unified content schema", "Backward compatibility"],
            "keyData": [],
            "evidencePack": [],
            "actionableTakeaway": "Notes and fact-check protocols can be added later.",
            "speakerNotes": "Use this slide to explain why schema alignment matters.",
        }
    ],
}


class FakeLLM:
    def __init__(self, responses):
        self.responses = list(responses)

    def generate(self, prompt, **kwargs):
        if self.responses:
            return self.responses.pop(0)
        return "{}"


class CapturingLLM(FakeLLM):
    def __init__(self, responses):
        super().__init__(responses)
        self.prompts = []

    def generate(self, prompt, **kwargs):
        self.prompts.append(prompt)
        return super().generate(prompt, **kwargs)


class SchemaCapturingLLM(FakeLLM):
    def __init__(self, responses):
        super().__init__(responses)
        self.schema_calls = []

    def generate_json_schema(self, prompt, schema_name, schema, **kwargs):
        self.schema_calls.append({
            "prompt": prompt,
            "schema_name": schema_name,
            "schema": schema,
            "kwargs": kwargs,
        })
        return super().generate(prompt, **kwargs)


class FakeRetrievalResult:
    source_file = "input_test.txt"
    score = 0.9
    text = "Artificial intelligence reference material about education and healthcare."


class FakeSearchResponse:
    results = [FakeRetrievalResult()]


class FakeRetrievalService:
    def search(self, query, top_k=5):
        return FakeSearchResponse()


def test_valid_outline_schema():
    parsed = NarrativeOutline.model_validate(VALID_OUTLINE)
    assert parsed.protocolVersion == "ppt-narrative-outline.v1"
    assert parsed.sections[0].slides[0].slideId == "slide-001"


def test_invalid_outline_schema_rejects_missing_field():
    broken = dict(VALID_OUTLINE)
    broken.pop("targetSlideCount")
    with pytest.raises(ValidationError):
        NarrativeOutline.model_validate(broken)


def test_valid_page_content_allows_empty_evidence():
    parsed = PageContentProtocol.model_validate(VALID_PAGE_CONTENT)
    assert parsed.slides[0].evidencePack == []
    assert parsed.slides[0].keyData == []


def test_extract_json_from_code_fence():
    parsed = parse_json_object('```json\n{"ok": true}\n```')
    assert parsed == {"ok": True}


def test_outline_falls_back_when_llm_returns_non_json():
    maker = OutlineMaker(llm_service=FakeLLM(["not json", "Legacy title\n1. Section\na. First slide\nb. Second slide"]))
    outline = maker.generate_outline("Test topic")
    assert maker.last_used_fallback is True
    assert outline["protocolVersion"] == "ppt-narrative-outline.v1"
    assert outline["targetSlideCount"] >= 3
    assert outline["sections"][0]["slides"][0]["slideId"] == "slide-001"


def test_outline_generation_uses_json_schema_response_format():
    llm = SchemaCapturingLLM([json.dumps(VALID_OUTLINE, ensure_ascii=False)])
    maker = OutlineMaker(llm_service=llm)

    outline = maker.generate_outline("AI presentation")

    assert outline["protocolVersion"] == "ppt-narrative-outline.v1"
    assert llm.schema_calls
    assert llm.schema_calls[0]["schema_name"] == "ppt_narrative_outline"
    assert llm.schema_calls[0]["schema"]["properties"]["protocolVersion"]["const"] == "ppt-narrative-outline.v1"


def test_generator_content_api_returns_legacy_and_protocol_fields():
    request = SimpleNamespace(
        app=SimpleNamespace(
            state=SimpleNamespace(llm_service=FakeLLM([json.dumps(VALID_PAGE_CONTENT, ensure_ascii=False)]))
        )
    )

    response = asyncio.run(
        expand_content(
            request,
            ExpandContentRequest(
                outline_node={
                    "id": "slide-001",
                    "number": 1,
                    "title": "Core Features",
                    "section": "Project Overview",
                    "goal": "Explain the core capability and value",
                    "bullets": ["Unified outline", "Unified content", "Compatibility"],
                },
                context="none",
            ),
        )
    )

    body = response.model_dump()
    assert body["success"] is True
    assert body["content"]
    assert body["page_content"]["protocolVersion"] == "ppt-page-content.v1"


def test_generator_outline_uses_retrieved_reference_context():
    llm = CapturingLLM([json.dumps(VALID_OUTLINE, ensure_ascii=False)])
    request = SimpleNamespace(
        app=SimpleNamespace(
            state=SimpleNamespace(
                llm_service=llm,
                retrieval_service=FakeRetrievalService(),
            )
        )
    )

    response = asyncio.run(
        generate_outline(
            request,
            GenerateOutlineRequest(topic="AI presentation", requirements="6 slides"),
        )
    )

    body = response.model_dump()
    assert body["success"] is True
    assert body["outline"]["protocolVersion"] == "ppt-narrative-outline.v1"
    assert "Artificial intelligence reference material" in llm.prompts[0]
