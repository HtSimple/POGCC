"""
测量「生成大纲」一步耗时（真实调用 LLM）。

在项目根目录执行：
    python tests/test_outline_timing.py
    python tests/test_outline_timing.py "拿破仑" deepseek

换模型（三选一）：
  1. 改下面 DEFAULT_PROVIDER 为 "deepseek" 或 "qwen"
  2. 命令行第二个参数：python tests/test_outline_timing.py "主题" qwen
  3. 不改脚本，只改项目根 config.json 的 "llm_provider"

或：
    pytest tests/test_outline_timing.py -v -s
"""
from __future__ import annotations

import sys
import time
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from app.core.generator.outline_maker import OutlineMaker
from app.services.llm_service import LLMService

DEFAULT_TOPIC = "人工智能在教育中的应用"
# None = 使用 config.json 里的 llm_provider；也可写 "deepseek" / "qwen"
DEFAULT_PROVIDER: str | None = None


def run_outline_timing(
    topic: str = DEFAULT_TOPIC,
    requirements: str | None = None,
    provider: str | None = None,
) -> dict:
    llm = LLMService()
    use = provider if provider is not None else DEFAULT_PROVIDER
    if use is not None:
        llm.switch_provider(use)
    maker = OutlineMaker(llm_service=llm)
    provider_name = llm.provider_name

    t0 = time.perf_counter()
    outline = maker.generate_outline(topic, requirements=requirements)
    elapsed = time.perf_counter() - t0

    n_sections = len(outline.get("sections") or [])
    n_subs = sum(len(s.get("subsections") or []) for s in outline.get("sections") or [])

    return {
        "provider": provider_name,
        "topic": topic,
        "elapsed_sec": elapsed,
        "title": outline.get("title", ""),
        "n_sections": n_sections,
        "n_subsections": n_subs,
        "outline": outline,
    }


def print_timing_report(report: dict) -> None:
    print(f"\n{'=' * 56}")
    print("生成大纲耗时")
    print(f"{'=' * 56}")
    print(f"模型:     {report['provider']}")
    print(f"主题:     {report['topic']}")
    print(f"耗时:     {report['elapsed_sec']:.2f} 秒")
    print(f"章节数:   {report['n_sections']}")
    print(f"小节数:   {report['n_subsections']}")
    print(f"标题:     {str(report['title'])[:80]}")
    print(f"{'=' * 56}\n")


def test_generate_outline_timing():
    """集成测试：记录 generate_outline 墙钟时间并打印。"""
    report = run_outline_timing()
    print_timing_report(report)
    assert report["elapsed_sec"] > 0
    assert report["n_sections"] > 0


def main() -> None:
    topic = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_TOPIC
    cli_provider = sys.argv[2] if len(sys.argv) > 2 else None
    report = run_outline_timing(topic=topic, provider=cli_provider)
    print_timing_report(report)


if __name__ == "__main__":
    main()
