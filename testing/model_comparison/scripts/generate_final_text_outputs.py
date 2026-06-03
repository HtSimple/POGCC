from __future__ import annotations

import argparse
import json
import sys
import time
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[3]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

DEFAULT_TOPICS_FILE = PROJECT_ROOT / "testing/model_comparison/model_comparison_topics.json"
DEFAULT_OUTPUT_DIR = PROJECT_ROOT / "testing/model_comparison/outputs"
VALID_PROVIDERS = ["deepseek", "qwen"]


@dataclass
class TopicCase:
    id: int
    topic: str
    capability: str


def resolve_path(value: str | Path) -> Path:
    path = Path(value)
    return path if path.is_absolute() else PROJECT_ROOT / path


def load_topics(path: Path) -> list[TopicCase]:
    with path.open("r", encoding="utf-8") as f:
        data = json.load(f)

    if not isinstance(data, list):
        raise ValueError("topics file must be a JSON array")

    topics: list[TopicCase] = []
    for index, item in enumerate(data, start=1):
        if not isinstance(item, dict):
            raise ValueError(f"topic entry #{index} must be an object")

        missing = [key for key in ("id", "topic", "capability") if key not in item]
        if missing:
            raise ValueError(f"topic entry #{index} missing fields: {', '.join(missing)}")

        topic_id = item["id"]
        if not isinstance(topic_id, int):
            raise ValueError(f"topic entry #{index} field 'id' must be an integer")

        topic = str(item["topic"]).strip()
        capability = str(item["capability"]).strip()
        if not topic:
            raise ValueError(f"topic entry #{index} field 'topic' must not be empty")
        if not capability:
            raise ValueError(f"topic entry #{index} field 'capability' must not be empty")

        topics.append(TopicCase(id=topic_id, topic=topic, capability=capability))

    return topics


def build_requirements(case: TopicCase, pages: int) -> str:
    return "\n".join(
        [
            "使用场景：课程/项目汇报",
            f"目标页数：{pages}",
            f"主要考察能力：{case.capability}",
            "输出语言：中文",
            "要求：围绕主题形成完整 PPT 叙事结构，包含背景、核心分析、关键方案或趋势、总结建议。",
            "要求：标题和要点要具体，避免空泛口号；不要根据受众推断汇报人身份。",
            "要求：最终文本应适合后续 GPT 评分和人工评分，尽量使用清晰、可核查的表述。",
        ]
    )


def flatten_outline_slides(outline: dict[str, Any]) -> list[dict[str, Any]]:
    slides: list[dict[str, Any]] = []
    for section in outline.get("sections") or []:
        section_title = str(section.get("sectionTitle") or "")
        section_objective = str(section.get("sectionObjective") or "")
        for slide in section.get("slides") or []:
            item = dict(slide)
            item["sectionTitle"] = section_title
            item["sectionObjective"] = section_objective
            slides.append(item)
    return slides


def outline_node_from_slide(slide: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": slide.get("slideId") or "slide-001",
        "number": slide.get("slideNumber") or 1,
        "role": slide.get("slideRole") or "content",
        "title": slide.get("slideTitle") or "未命名页面",
        "section": slide.get("sectionTitle") or "未命名章节",
        "goal": slide.get("sectionObjective") or f"围绕“{slide.get('slideTitle') or '本页'}”展开说明",
        "bullets": slide.get("keyPoints") or [],
    }


def build_knowledge_query(case: TopicCase, slide: dict[str, Any]) -> str:
    key_points = slide.get("keyPoints") or []
    key_point_text = "\n".join(f"- {point}" for point in key_points) if key_points else "- 无"
    return "\n".join(
        [
            f"测试主题：{case.topic}",
            f"主要考察能力：{case.capability}",
            f"章节：{slide.get('sectionTitle') or ''}",
            f"页面标题：{slide.get('slideTitle') or ''}",
            "页面关键点：",
            key_point_text,
            "请检索或整理能支撑本页最终 PPT 文本生成的事实、案例、数据、风险和方案信息，优先使用权威来源。",
        ]
    )


def safe_fence_text(text: str | None) -> str:
    value = str(text or "").strip()
    return value.replace("```", "'''") if value else "_empty_"


def limit_text(text: str | None, limit: int) -> str:
    value = str(text or "").strip()
    if limit <= 0 or len(value) <= limit:
        return value
    return value[:limit].rstrip() + "\n...（已截断，运行脚本时可调大 --knowledge-char-limit）"


def is_error_text(text: str | None) -> bool:
    value = str(text or "")
    return not value.strip() or (value.startswith("[") and "]" in value[:40])


def generate_for_provider(
    provider: str,
    topics: list[TopicCase],
    args: argparse.Namespace,
    llm_service: Any,
) -> dict[str, Any]:
    from app.core.generator.content_expander import ContentExpander
    from app.core.generator.outline_maker import OutlineMaker
    from app.core.knowledge_agent.search_agent import SearchAgent
    from app.services.web_search_service import WebSearchService

    llm_service.switch_provider(provider)
    outline_maker = OutlineMaker(llm_service=llm_service)
    search_agent = SearchAgent(
        llm_service=llm_service,
        web_search_service=WebSearchService(),
    )
    content_expander = ContentExpander(llm_service=llm_service)

    provider_report: dict[str, Any] = {
        "provider": provider,
        "started_at": datetime.now().isoformat(timespec="seconds"),
        "pages": args.pages,
        "refine_knowledge": args.refine_knowledge,
        "topics": [],
    }

    for case in topics:
        print(f"[{provider}] topic {case.id}: {case.topic}")
        requirements = build_requirements(case, args.pages)
        topic_started = time.perf_counter()
        topic_record: dict[str, Any] = {
            "id": case.id,
            "topic": case.topic,
            "capability": case.capability,
            "requirements": requirements,
            "outline": None,
            "outline_elapsed_sec": 0.0,
            "outline_used_fallback": False,
            "outline_validation_error": None,
            "slides": [],
            "error": None,
        }

        try:
            outline_started = time.perf_counter()
            outline = outline_maker.generate_outline(
                case.topic,
                requirements=requirements,
                max_tokens=args.outline_max_tokens,
            )
            topic_record["outline_elapsed_sec"] = round(time.perf_counter() - outline_started, 2)
            topic_record["outline_used_fallback"] = outline_maker.last_used_fallback
            topic_record["outline_validation_error"] = outline_maker.last_validation_error
            topic_record["outline"] = outline

            slides = flatten_outline_slides(outline)
            for slide in slides:
                slide_number = slide.get("slideNumber") or len(topic_record["slides"]) + 1
                print(f"  [{provider}] slide {slide_number}: {slide.get('slideTitle') or '未命名页面'}")

                knowledge = ""
                knowledge_error = None
                knowledge_started = time.perf_counter()
                try:
                    knowledge = search_agent.search(
                        build_knowledge_query(case, slide),
                        refine_knowledge=args.refine_knowledge,
                    )
                except Exception as exc:
                    knowledge_error = str(exc)
                knowledge_elapsed = round(time.perf_counter() - knowledge_started, 2)

                context_parts = [
                    f"测试主题：{case.topic}",
                    f"主要考察能力：{case.capability}",
                    f"生成要求：\n{requirements}",
                ]
                if knowledge.strip():
                    context_parts.append(f"知识补充：\n{knowledge}")
                context = "\n\n".join(context_parts)

                content_started = time.perf_counter()
                content_result = content_expander.expand_page_content(
                    outline_node_from_slide(slide),
                    context=context,
                    max_tokens=args.content_max_tokens,
                )
                content_elapsed = round(time.perf_counter() - content_started, 2)
                content = content_result.get("content") or ""
                page_content = content_result.get("page_content")
                content_message = content_result.get("message")
                content_success = page_content is not None and not is_error_text(content)

                topic_record["slides"].append(
                    {
                        "slide_id": slide.get("slideId"),
                        "slide_number": slide_number,
                        "slide_role": slide.get("slideRole"),
                        "section_title": slide.get("sectionTitle"),
                        "slide_title": slide.get("slideTitle"),
                        "key_points": slide.get("keyPoints") or [],
                        "knowledge": knowledge,
                        "knowledge_success": bool(knowledge.strip()) and knowledge_error is None,
                        "knowledge_error": knowledge_error,
                        "knowledge_elapsed_sec": knowledge_elapsed,
                        "content": content,
                        "content_success": content_success,
                        "content_message": content_message,
                        "content_elapsed_sec": content_elapsed,
                        "has_page_content": page_content is not None,
                    }
                )
        except Exception as exc:
            topic_record["error"] = str(exc)

        topic_record["total_elapsed_sec"] = round(time.perf_counter() - topic_started, 2)
        provider_report["topics"].append(topic_record)

    provider_report["finished_at"] = datetime.now().isoformat(timespec="seconds")
    return provider_report


def render_markdown(report: dict[str, Any], topics_file: Path) -> str:
    lines: list[str] = [
        f"# {report['provider']} 最终文本输出",
        "",
        "本文件用于 GPT 评分和人工评分。内容为模型按同一批测试主题生成的最终 PPT 页面文本，不包含评分结论。",
        "",
        "## 运行信息",
        "",
        f"- Provider：`{report['provider']}`",
        f"- 生成开始时间：{report.get('started_at', '')}",
        f"- 生成结束时间：{report.get('finished_at', '')}",
        f"- 主题文件：`{topics_file.relative_to(PROJECT_ROOT) if topics_file.is_relative_to(PROJECT_ROOT) else topics_file}`",
        f"- 默认目标页数：{report.get('pages')}",
        f"- 知识补充模式：{'完整整理 refine_knowledge=True' if report.get('refine_knowledge') else '快路径 refine_knowledge=False'}",
        "",
        "## 建议评分维度",
        "",
        "- 主题相关性",
        "- 大纲遵循度",
        "- 内容完整性",
        "- 结构清晰度",
        "- 知识补充利用程度",
        "- 事实一致性风险",
        "- PPT 展示可用性",
        "",
    ]

    for topic_record in report["topics"]:
        outline = topic_record.get("outline") or {}
        slides = topic_record.get("slides") or []
        lines.extend(
            [
                f"## 主题 {topic_record['id']}：{topic_record['topic']}",
                "",
                f"- 主要考察能力：{topic_record['capability']}",
                f"- 大纲生成耗时：{topic_record.get('outline_elapsed_sec', 0)} 秒",
                f"- 主题总耗时：{topic_record.get('total_elapsed_sec', 0)} 秒",
                f"- 是否触发 fallback：{topic_record.get('outline_used_fallback')}",
                f"- 大纲校验错误：{topic_record.get('outline_validation_error') or '无'}",
                f"- 主题级错误：{topic_record.get('error') or '无'}",
                "",
                "### 大纲摘要",
                "",
                f"- 演示标题：{outline.get('presentationTitle') or '未生成'}",
                f"- 目标页数：{outline.get('targetSlideCount') or '未知'}",
                f"- 实际页数：{len(slides)}",
                "",
            ]
        )

        for section in outline.get("sections") or []:
            lines.append(f"- {section.get('sectionTitle') or '未命名章节'}")
            for slide in section.get("slides") or []:
                points = "；".join(str(p) for p in (slide.get("keyPoints") or []))
                lines.append(
                    f"  - 第 {slide.get('slideNumber', '?')} 页：{slide.get('slideTitle') or '未命名页面'}"
                    + (f"（{points}）" if points else "")
                )
        lines.append("")
        lines.append("### 最终文本与证据")
        lines.append("")

        for slide_record in slides:
            lines.extend(
                [
                    f"#### 第 {slide_record.get('slide_number', '?')} 页：{slide_record.get('slide_title') or '未命名页面'}",
                    "",
                    f"- Slide ID：`{slide_record.get('slide_id') or ''}`",
                    f"- Slide Role：`{slide_record.get('slide_role') or ''}`",
                    f"- 所属章节：{slide_record.get('section_title') or ''}",
                    f"- 知识补充成功：{slide_record.get('knowledge_success')}",
                    f"- 最终文本成功：{slide_record.get('content_success')}",
                    f"- 知识补充耗时：{slide_record.get('knowledge_elapsed_sec')} 秒",
                    f"- 最终文本耗时：{slide_record.get('content_elapsed_sec')} 秒",
                    f"- 知识补充错误：{slide_record.get('knowledge_error') or '无'}",
                    f"- 最终文本消息：{slide_record.get('content_message') or '无'}",
                    "",
                    "**大纲 keyPoints**",
                    "",
                ]
            )
            for point in slide_record.get("key_points") or []:
                lines.append(f"- {point}")

            knowledge = limit_text(slide_record.get("knowledge"), report.get("knowledge_char_limit", 1800))
            lines.extend(
                [
                    "",
                    "**知识补充摘要**",
                    "",
                    "```text",
                    safe_fence_text(knowledge),
                    "```",
                    "",
                    "**最终文本**",
                    "",
                    "```text",
                    safe_fence_text(slide_record.get("content")),
                    "```",
                    "",
                ]
            )

    return "\n".join(lines).rstrip() + "\n"


def write_markdown(report: dict[str, Any], output_dir: Path, topics_file: Path, knowledge_char_limit: int) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)
    report["knowledge_char_limit"] = knowledge_char_limit
    output_path = output_dir / f"{report['provider']}_final_texts.md"
    output_path.write_text(render_markdown(report, topics_file), encoding="utf-8")
    return output_path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Generate final text outputs for DeepSeek/Qwen model comparison."
    )
    parser.add_argument(
        "--topics-file",
        default=str(DEFAULT_TOPICS_FILE.relative_to(PROJECT_ROOT)),
        help="JSON file containing model comparison topics.",
    )
    parser.add_argument(
        "--providers",
        nargs="+",
        default=["deepseek", "qwen"],
        choices=VALID_PROVIDERS,
        help="Providers to run.",
    )
    parser.add_argument("--pages", type=int, default=3, help="Target slide count per topic.")
    parser.add_argument(
        "--output-dir",
        default=str(DEFAULT_OUTPUT_DIR.relative_to(PROJECT_ROOT)),
        help="Directory for Markdown outputs.",
    )
    parser.add_argument("--max-topics", type=int, help="Limit topic count for trial runs.")
    parser.add_argument(
        "--refine-knowledge",
        action="store_true",
        help="Use full SearchAgent knowledge evaluation/summarization flow.",
    )
    parser.add_argument("--outline-max-tokens", type=int, default=8192)
    parser.add_argument("--content-max-tokens", type=int, default=4096)
    parser.add_argument(
        "--knowledge-char-limit",
        type=int,
        default=1800,
        help="Max knowledge characters shown per slide in Markdown. Use 0 for no truncation.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Validate topics and print planned outputs without calling model/search APIs.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    topics_file = resolve_path(args.topics_file)
    output_dir = resolve_path(args.output_dir)

    topics = load_topics(topics_file)
    if args.max_topics is not None:
        topics = topics[: max(0, args.max_topics)]
    if not topics:
        raise ValueError("no topics to run")

    if args.dry_run:
        print("Dry run only. No model/search API calls will be made.")
        print(f"Topics file: {topics_file}")
        print(f"Output dir:  {output_dir}")
        print(f"Providers:   {', '.join(args.providers)}")
        print(f"Topic count: {len(topics)}")
        for provider in args.providers:
            print(f"Will write:  {output_dir / f'{provider}_final_texts.md'}")
        return 0

    from app.services.llm_service import LLMService

    llm_service = LLMService()
    original_provider = llm_service.provider_name
    written: list[Path] = []

    try:
        for provider in args.providers:
            report = generate_for_provider(provider, topics, args, llm_service)
            path = write_markdown(report, output_dir, topics_file, args.knowledge_char_limit)
            written.append(path)
            print(f"[saved] {path}")
    finally:
        if llm_service.provider_name != original_provider:
            llm_service.switch_provider(original_provider)

    print("\nGenerated output files:")
    for path in written:
        print(f"- {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
