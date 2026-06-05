from __future__ import annotations

from unittest.mock import MagicMock, patch

from app.core.generator.batch_content import expand_content_batch


def _valid_expanded():
    return {
        "content": "页面正文",
        "page_content": {
            "protocolVersion": "ppt-page-content.v1",
            "language": "zh-CN",
            "presentationTitle": "Demo",
            "researchPolicy": {
                "triggerReason": "user_requested",
                "depthLevel": "standard",
                "sourcePriority": ["local_document"],
                "maxSourcesPerSlide": 3,
            },
            "slides": [],
        },
        "message": None,
    }


def test_expand_content_batch_retries_failed_item_until_success():
    llm = MagicMock()
    items = [
        {
            "index": 0,
            "id": "slide-a",
            "outline_node": {"title": "A", "bullets": ["a"]},
        }
    ]

    with patch("app.core.generator.batch_content.ContentExpander") as expander_cls:
        expander = expander_cls.return_value
        expander.expand_page_content.side_effect = [
            {"content": "", "page_content": None, "message": "structured content validation failed"},
            _valid_expanded(),
        ]

        with patch("app.core.generator.batch_content.time.sleep"):
            report = expand_content_batch(items, context="ctx", max_workers=1, llm_service=llm)

    assert report["success"] is True
    assert report["results"][0]["success"] is True
    assert expander.expand_page_content.call_count == 2


def test_expand_content_batch_retries_failed_parallel_items_sequentially():
    llm = MagicMock()
    items = [
        {"index": 0, "id": "slide-a", "outline_node": {"title": "A", "bullets": ["a"]}},
        {"index": 1, "id": "slide-b", "outline_node": {"title": "B", "bullets": ["b"]}},
    ]
    call_count = {"n": 0}

    def fake_expand(outline_node, context=None, max_tokens=4096):
        call_count["n"] += 1
        title = outline_node.get("title")
        if title == "A" and call_count["n"] == 1:
            return {"content": "", "page_content": None, "message": "temporary failure"}
        return _valid_expanded()

    with patch("app.core.generator.batch_content.ContentExpander") as expander_cls:
        expander = expander_cls.return_value
        expander.expand_page_content.side_effect = fake_expand

        with patch("app.core.generator.batch_content.time.sleep"):
            report = expand_content_batch(items, context="ctx", max_workers=2, llm_service=llm)

    assert all(row["success"] for row in report["results"])
    assert expander.expand_page_content.call_count >= 3
