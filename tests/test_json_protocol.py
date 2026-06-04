import asyncio
import json
from types import SimpleNamespace

import pytest
from pydantic import ValidationError

from app.api.routes.generator import expand_content, generate_notes, generate_outline, revise_content, revise_content_text
from app.core.generator.content_expander import ContentExpander
from app.core.generator.notes_generator import NotesGenerator
from app.core.generator.outline_maker import OutlineMaker
from app.schema.models import (
    ExpandContentRequest,
    GenerateNotesRequest,
    GenerateOutlineRequest,
    NarrativeOutline,
    PageContentProtocol,
    ReviseContentRequest,
    ReviseContentTextRequest,
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


def test_generator_content_normalizes_local_document_evidence_shape():
    malformed_content = json.loads(json.dumps(VALID_PAGE_CONTENT))
    malformed_content["researchPolicy"]["sourcePriority"] = ["local_document"]
    malformed_content["slides"][0]["evidencePack"] = [
        {
            "sourceDescription": "本地资料：环境保护与低碳生活措施",
            "sourceType": "local_document",
            "keyClaim": "垃圾分类、节能减排和绿色出行是推进低碳生活的重要措施。",
            "retrievedAt": "2025-01-01",
        }
    ]
    request = SimpleNamespace(
        app=SimpleNamespace(
            state=SimpleNamespace(llm_service=FakeLLM([json.dumps(malformed_content, ensure_ascii=False)]))
        )
    )

    response = asyncio.run(
        expand_content(
            request,
            ExpandContentRequest(
                outline_node={
                    "id": "slide-001",
                    "number": 1,
                    "title": "环境挑战与绿色转型",
                    "section": "背景问题",
                    "goal": "阐述环境保护的重要性及当前面临的主要问题",
                    "bullets": ["城市发展", "公众健康", "资源安全"],
                },
                context="本地资料",
            ),
        )
    )

    body = response.model_dump()
    evidence = body["page_content"]["slides"][0]["evidencePack"][0]
    assert body["success"] is True
    assert evidence["sourceRefId"] == "src-001"
    assert evidence["claim"] == "垃圾分类、节能减排和绿色出行是推进低碳生活的重要措施。"
    assert evidence["sourceTitle"] == "本地资料：环境保护与低碳生活措施"
    assert evidence["sourceType"] == "local_document"
    assert evidence["publishDate"] == "2025-01-01"


def test_generator_content_normalizes_short_or_meta_display_bullets():
    malformed_content = json.loads(json.dumps(VALID_PAGE_CONTENT))
    malformed_content["slides"][0]["displayBullets"] = ["学术汇报", "课程讲师"]
    request = SimpleNamespace(
        app=SimpleNamespace(
            state=SimpleNamespace(llm_service=FakeLLM([json.dumps(malformed_content, ensure_ascii=False)]))
        )
    )

    response = asyncio.run(
        expand_content(
            request,
            ExpandContentRequest(
                outline_node={
                    "id": "slide-001",
                    "number": 1,
                    "title": "环境保护与绿色生活",
                    "section": "主题导入",
                    "goal": "阐述环境保护的重要性与当前面临的主要问题",
                    "bullets": ["城市发展", "公众健康", "资源安全"],
                },
                context="本地资料",
            ),
        )
    )

    body = response.model_dump()
    bullets = body["page_content"]["slides"][0]["displayBullets"]
    assert body["success"] is True
    assert len(bullets) >= 3
    assert "学术汇报" not in bullets
    assert "课程讲师" not in bullets
    assert body["page_content"]["slides"][0]["speakerNotes"]


def test_parse_page_content_normalizes_non_protocol_research_policy():
    malformed = json.loads(json.dumps(VALID_PAGE_CONTENT))
    malformed["researchPolicy"] = {
        "preferLocal": True,
        "allowedSources": ["test_text.pdf"],
    }
    expander = ContentExpander(llm_service=FakeLLM([]))
    parsed = expander._parse_page_content(json.dumps(malformed, ensure_ascii=False), {"id": "slide-001", "title": "Test"})
    policy = parsed.researchPolicy
    assert policy.triggerReason == "user_requested"
    assert policy.depthLevel == "standard"
    assert "local_document" in policy.sourcePriority


def test_parse_page_content_hoists_root_level_research_hints():
    malformed = json.loads(json.dumps(VALID_PAGE_CONTENT))
    malformed.pop("researchPolicy", None)
    malformed["preferLocal"] = True
    malformed["allowedSources"] = ["test_text.pdf"]
    expander = ContentExpander(llm_service=FakeLLM([]))
    parsed = expander._parse_page_content(
        json.dumps(malformed, ensure_ascii=False),
        {"id": "slide-001", "number": 1, "title": "Test", "bullets": ["a", "b", "c"]},
    )
    assert "local_document" in parsed.researchPolicy.sourcePriority


def test_parse_page_content_builds_slide_when_slides_missing():
    malformed = {
        "protocolVersion": "ppt-page-content.v1",
        "language": "zh-CN",
        "presentationTitle": "计算机原理学术汇报",
    }
    expander = ContentExpander(llm_service=FakeLLM([]))
    parsed = expander._parse_page_content(
        json.dumps(malformed, ensure_ascii=False),
        {
            "id": "slide-001",
            "number": 1,
            "title": "存储系统",
            "section": "第五章",
            "goal": "说明多级存储层次的基本概念",
            "bullets": ["Cache 原理", "映射方式", "替换算法"],
        },
        fallback_content="- Cache 采用组相联映射\n- 替换算法常用 LRU\n- 写策略分为写直达与写回",
    )
    assert len(parsed.slides) == 1
    assert len(parsed.slides[0].displayBullets) >= 3
    assert parsed.slides[0].speakerNotes


def test_generator_content_revise_api_returns_revised_page_content():
    revised_content = json.loads(json.dumps(VALID_PAGE_CONTENT))
    revised_content["slides"][0]["coreMessage"] = "修订后的核心信息：强调低碳生活与资源节约。"
    request = SimpleNamespace(
        app=SimpleNamespace(
            state=SimpleNamespace(llm_service=FakeLLM([json.dumps(revised_content, ensure_ascii=False)]))
        )
    )

    response = asyncio.run(
        revise_content(
            request,
            ReviseContentRequest(
                outline_node={
                    "id": "slide-001",
                    "number": 1,
                    "title": "环境保护与绿色生活",
                    "section": "主题导入",
                    "goal": "阐述环境保护的重要性与当前面临的主要问题",
                    "bullets": ["城市发展", "公众健康", "资源安全"],
                },
                context="本地资料",
                current_content="环境保护能够降低污染影响，并推动资源节约。",
                revision_suggestion="语气更正式，并突出低碳生活。",
            ),
        )
    )

    body = response.model_dump()
    assert body["success"] is True
    assert "修订后的核心信息" in body["page_content"]["slides"][0]["coreMessage"]


def test_generator_content_revise_text_api_returns_plain_body():
    revised = "- 修订后的要点一\n- 修订后的要点二\n- 修订后的要点三"
    request = SimpleNamespace(
        app=SimpleNamespace(
            state=SimpleNamespace(llm_service=FakeLLM([revised]))
        )
    )

    response = asyncio.run(
        revise_content_text(
            request,
            ReviseContentTextRequest(
                outline_node={
                    "title": "存储系统",
                    "bullets": ["Cache 原理", "映射方式", "替换算法"],
                },
                current_content="- 原正文要点一\n- 原正文要点二",
                revision_suggestion="压缩为 3 条，语气更口语化",
            ),
        )
    )

    body = response.model_dump()
    assert body["success"] is True
    assert "修订后的要点一" in body["content"]


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
