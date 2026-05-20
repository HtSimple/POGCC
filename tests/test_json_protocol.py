import asyncio
import json
from types import SimpleNamespace

import pytest
from pydantic import ValidationError

from app.api.routes.generator import expand_content, generate_notes, generate_outline
from app.core.generator.notes_generator import NotesGenerator
from app.core.generator.outline_maker import OutlineMaker
from app.schema.models import (
    ExpandContentRequest,
    GenerateNotesRequest,
    GenerateOutlineRequest,
    NarrativeOutline,
    PageContentProtocol,
)
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


def test_invalid_outline_schema_rejects_non_continuous_slide_numbers():
    broken = json.loads(json.dumps(VALID_OUTLINE))
    broken["sections"][0]["slides"][0]["slideId"] = "slide-003"
    broken["sections"][0]["slides"][0]["slideNumber"] = 3
    broken["sections"][0]["slideRange"] = {"start": 3, "end": 3}
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


def test_generator_notes_api_returns_speaker_notes():
    notes_payload = {
        "notes": "这一页可以先说明页面结论，再结合已有证据解释原因，最后自然过渡到下一页，不添加没有来源的新事实。"
    }
    request = SimpleNamespace(
        app=SimpleNamespace(
            state=SimpleNamespace(llm_service=FakeLLM([json.dumps(notes_payload, ensure_ascii=False)]))
        )
    )

    response = asyncio.run(
        generate_notes(
            request,
            GenerateNotesRequest(
                project_id="project-001",
                slide_id="slide-001",
                slide_title="环境保护的意义",
                slide_content="环境保护能够降低污染影响，并推动资源节约。",
                knowledge_evidence="参考资料说明城市垃圾分类和节能减排有助于改善环境质量。",
                style_requirement="口语化、适合课堂展示",
            ),
        )
    )

    body = response.model_dump()
    assert body["success"] is True
    assert body["notes"] == notes_payload["notes"]


def test_notes_generator_accepts_plain_text_notes():
    raw_notes = "这一页可以用更口语化的方式说明环境保护为什么需要公众参与，并结合页面正文解释垃圾分类、节能减排和绿色出行之间的关系。"
    generator = NotesGenerator(llm_service=FakeLLM([raw_notes]))

    result = generator.generate_notes(
        project_id="project-001",
        slide_id="slide-001",
        slide_title="公众参与环境保护",
        slide_content="公众可以通过垃圾分类、节能减排和绿色出行参与环境保护。",
        knowledge_evidence="参考资料强调环境保护需要政府监管、企业责任和公众参与。",
        style_requirement="口语化",
    )

    assert result["notes"] == raw_notes


def test_notes_generator_retries_provider_truncation_error():
    raw_notes = "这一页可以先概括环境保护与绿色生活的关系，再提醒听众关注个人行动、企业责任和制度约束之间的配合。"
    generator = NotesGenerator(llm_service=FakeLLM(["[DeepSeek] 回复被截断，请增加 max_tokens 后重试", raw_notes]))

    result = generator.generate_notes(
        project_id="project-001",
        slide_id="slide-001",
        slide_title="环境保护与绿色生活",
        slide_content="环境保护需要个人、企业和政府共同参与。",
        knowledge_evidence="参考资料强调环境保护不是单一部门的工作。",
        style_requirement="口语化",
    )

    assert result["notes"] == raw_notes


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
