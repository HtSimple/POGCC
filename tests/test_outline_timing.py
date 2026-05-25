"""
测量「生成大纲」一步耗时（真实调用 LLM，ppt-narrative-outline.v1 JSON 协议）。

在项目根目录执行：
    python tests/test_outline_timing.py
    python tests/test_outline_timing.py "喜洋洋和小灰灰" qwen
    python tests/test_outline_timing.py "拿破仑" deepseek --pages 10

换模型（三选一）：
  1. 改下面 DEFAULT_PROVIDER 为 "deepseek" 或 "qwen"
  2. 命令行第二个参数：python tests/test_outline_timing.py "主题" qwen
  3. 不改脚本，只改项目根 config.json 的 "llm_provider"

或：
    pytest tests/test_outline_timing.py -v -s
"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path
from typing import Any

_ROOT = Path(__file__).resolve().parents[1]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from app.core.generator.outline_maker import OutlineMaker
from app.services.llm_service import LLMService

DEFAULT_TOPIC = "人工智能在教育中的应用"
DEFAULT_PAGE_COUNT = 6
# None = 使用 config.json 里的 llm_provider；也可写 "deepseek" / "qwen"
DEFAULT_PROVIDER: str | None = None


def build_requirements(
    page_count: int = DEFAULT_PAGE_COUNT,
    scene: str = "学术汇报",
    audience: str = "",
    extra: str = "",
) -> str:
    """与前端 App.vue requirementsText 拼接方式一致。"""
    lines = [
        f"使用场景：{scene}",
        f"目标页数：{page_count}",
        (
            f"目标受众：{audience}（这是听众/观看者，不是汇报人身份）"
            if audience
            else ""
        ),
        "不要根据目标受众推断汇报人身份；除非用户明确提供汇报人，否则不要生成「汇报人」「我是...」等身份表述。",
        f"额外要求：{extra}" if extra else "",
    ]
    return "\n".join(line for line in lines if line)


def count_outline_slides(outline: dict[str, Any]) -> int:
    return sum(len(section.get("slides") or []) for section in outline.get("sections") or [])


def run_outline_timing(
    topic: str = DEFAULT_TOPIC,
    requirements: str | None = None,
    provider: str | None = None,
    reference_context: str | None = None,
) -> dict[str, Any]:
    llm = LLMService()
    use = provider if provider is not None else DEFAULT_PROVIDER
    if use is not None:
        llm.switch_provider(use)
    maker = OutlineMaker(llm_service=llm)
    provider_name = llm.provider_name

    req = requirements if requirements is not None else build_requirements()

    t0 = time.perf_counter()
    outline = maker.generate_outline(
        topic,
        requirements=req,
        reference_context=reference_context,
    )
    elapsed = time.perf_counter() - t0

    n_sections = len(outline.get("sections") or [])
    n_slides = count_outline_slides(outline)

    return {
        "provider": provider_name,
        "topic": topic,
        "requirements": req,
        "elapsed_sec": elapsed,
        "protocol_version": outline.get("protocolVersion", ""),
        "presentation_title": outline.get("presentationTitle", ""),
        "target_slide_count": outline.get("targetSlideCount"),
        "n_sections": n_sections,
        "n_slides": n_slides,
        "used_fallback": maker.last_used_fallback,
        "validation_error": maker.last_validation_error,
        "raw_output": maker.last_raw_output,
        "outline": outline,
    }


def print_timing_report(report: dict[str, Any]) -> None:
    print(f"\n{'=' * 56}")
    print("生成大纲耗时（JSON 协议）")
    print(f"{'=' * 56}")
    print(f"模型:           {report['provider']}")
    print(f"主题:           {report['topic']}")
    print(f"耗时:           {report['elapsed_sec']:.2f} 秒")
    print(f"协议:           {report['protocol_version']}")
    print(f"演示标题:       {str(report['presentation_title'])[:80]}")
    print(f"目标页数:       {report['target_slide_count']}")
    print(f"章节数:         {report['n_sections']}")
    print(f"实际 slide 数:  {report['n_slides']}")
    print(f"是否 fallback:  {report['used_fallback']}")
    if report["used_fallback"] and report.get("validation_error"):
        print(f"校验/回退原因:   {str(report['validation_error'])[:200]}")
    print(f"{'=' * 56}\n")


def print_outline_body(report: dict[str, Any]) -> None:
    outline = report.get("outline") or {}
    print("生成的大纲（可读摘要）")
    print("-" * 56)
    print(f"标题: {outline.get('presentationTitle', '')}")
    print(f"语言: {outline.get('language', '')}")
    for section in outline.get("sections") or []:
        slide_range = section.get("slideRange") or {}
        print(
            f"\n[{section.get('sectionId', '')}] {section.get('sectionTitle', '')} "
            f"(slide {slide_range.get('start', '?')}-{slide_range.get('end', '?')})"
        )
        print(f"  章节目标: {section.get('sectionObjective', '')}")
        for slide in section.get("slides") or []:
            print(
                f"  - {slide.get('slideId', '')} #{slide.get('slideNumber', '?')} "
                f"[{slide.get('slideRole', '')}] {slide.get('slideTitle', '')}"
            )
            for point in slide.get("keyPoints") or []:
                print(f"      · {point}")
            if slide.get("notes"):
                print(f"      备注: {slide['notes']}")
    print("-" * 56)
    print("完整 JSON:")
    print(json.dumps(outline, ensure_ascii=False, indent=2))
    print("-" * 56)
    if report.get("used_fallback") and report.get("raw_output"):
        print("模型原始输出（fallback 时可供排查）:")
        print(report["raw_output"][:3000])
        if len(report["raw_output"]) > 3000:
            print("...（已截断）")
        print("-" * 56)
    print()


def test_generate_outline_timing():
    """集成测试：记录 generate_outline 墙钟时间并打印。"""
    report = run_outline_timing()
    print_timing_report(report)
    print_outline_body(report)
    assert report["elapsed_sec"] > 0
    assert report["protocol_version"] == "ppt-narrative-outline.v1"
    assert report["n_sections"] > 0
    assert report["n_slides"] > 0
    assert report["presentation_title"]


def main() -> None:
    topic = DEFAULT_TOPIC
    provider: str | None = None
    page_count = DEFAULT_PAGE_COUNT

    args = sys.argv[1:]
    i = 0
    while i < len(args):
        arg = args[i]
        if arg == "--pages":
            page_count = int(args[i + 1])
            i += 2
            continue
        if arg in LLMService.VALID_PROVIDERS:
            provider = arg
        elif topic == DEFAULT_TOPIC:
            topic = arg
        i += 1

    requirements = build_requirements(page_count=page_count)
    report = run_outline_timing(
        topic=topic,
        requirements=requirements,
        provider=provider,
    )
    print_timing_report(report)
    print_outline_body(report)


if __name__ == "__main__":
    main()
