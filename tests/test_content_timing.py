"""
对比「逐页串行」与「ThreadPoolExecutor + 每线程独立 LLMService」生成正文的耗时。

使用固定示例大纲（不调用大纲 LLM），仅测内容补全。

在项目根目录执行：
    python tests/test_content_timing.py
    python tests/test_content_timing.py deepseek
    python tests/test_content_timing.py qwen 3

或：
    pytest tests/test_content_timing.py -v -s
"""
from __future__ import annotations

import re
import sys
import time
from pathlib import Path
from typing import Any

_ROOT = Path(__file__).resolve().parents[1]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from app.core.generator.batch_content import expand_content_batch
from app.core.generator.content_expander import ContentExpander
from app.services.llm_service import LLMService

# 固定示例大纲（与 outline_maker 默认结构一致，共 6 页）
SAMPLE_OUTLINE: dict[str, Any] = {
    "title": "人工智能在教育中的应用",
    "sections": [
        {
            "title": "1. 概述",
            "subsections": [
                {
                    "title": "背景介绍",
                    "goal": "介绍教育领域应用 AI 的背景与动因",
                    "bullets": ["教育数字化", "学习者需求变化", "技术成熟度"],
                },
                {
                    "title": "研究意义",
                    "goal": "说明本主题的研究与实践价值",
                    "bullets": ["理论意义", "实践价值", "政策关联"],
                },
            ],
        },
        {
            "title": "2. 主要内容",
            "subsections": [
                {
                    "title": "核心概念",
                    "goal": "界定关键概念与基本框架",
                    "bullets": ["智能教学", "自适应学习", "教育数据"],
                },
                {
                    "title": "应用案例",
                    "goal": "展示典型应用场景与成效",
                    "bullets": ["K12 场景", "高等教育", "职业培训"],
                },
            ],
        },
        {
            "title": "3. 总结展望",
            "subsections": [
                {
                    "title": "总结",
                    "goal": "归纳全文核心结论",
                    "bullets": ["主要发现", "关键启示", "行动建议"],
                },
                {
                    "title": "未来发展",
                    "goal": "展望未来趋势与研究方向",
                    "bullets": ["技术趋势", "政策环境", "研究空白"],
                },
            ],
        },
    ],
}

SAMPLE_CONTEXT = (
    "场景：课程汇报；受众：本科生；"
    "风格：条理清晰、每页 3～5 个要点；避免空泛口号。"
)

DEFAULT_PROVIDER: str | None = None
DEFAULT_MAX_WORKERS = 3


def _clean_title(text: str) -> str:
    return re.sub(r"^(\d+|[a-zA-Z])[.)]\s*", "", (text or "").strip()).strip()


def outline_to_nodes(outline: dict[str, Any]) -> list[dict[str, Any]]:
    """将大纲转为与前端 expandContent 一致的 outline_node 列表。"""
    nodes: list[dict[str, Any]] = []
    for section in outline.get("sections") or []:
        section_title = _clean_title(str(section.get("title") or ""))
        subs = section.get("subsections") or []
        if not subs:
            subs = [section_title]
        for sub in subs:
            if isinstance(sub, dict):
                title = _clean_title(str(sub.get("title") or ""))
                goal = str(sub.get("goal") or "").strip() or f"围绕「{title}」说明核心信息"
                bullets_raw = sub.get("bullets") or []
                bullets = [str(b).strip() for b in bullets_raw if str(b).strip()]
            else:
                title = _clean_title(str(sub))
                goal = f"围绕「{title}」说明核心信息"
                bullets = [title] if title else []
            nodes.append(
                {
                    "title": title,
                    "section": section_title,
                    "goal": goal,
                    "bullets": bullets or ([title] if title else []),
                }
            )
    if not nodes:
        topic = str(outline.get("title") or "未命名主题")
        nodes.append({"title": topic, "section": topic, "goal": "", "bullets": [topic]})
    return nodes


def _resolve_provider(provider: str | None) -> str | None:
    return provider if provider is not None else DEFAULT_PROVIDER


def _make_expander(provider: str | None = None) -> tuple[ContentExpander, str]:
    llm = LLMService()
    use = _resolve_provider(provider)
    if use is not None:
        llm.switch_provider(use)
    return ContentExpander(llm_service=llm), llm.provider_name


def run_serial(
    nodes: list[dict[str, Any]],
    context: str = SAMPLE_CONTEXT,
    provider: str | None = None,
) -> dict[str, Any]:
    expander, provider_name = _make_expander(provider)
    results: list[dict[str, Any]] = []

    t0 = time.perf_counter()
    for i, node in enumerate(nodes):
        label = node.get("title") or f"page-{i}"
        print(f"  [串行] 开始 #{i + 1}: {label}")
        page_t0 = time.perf_counter()
        content = expander.expand_content(node, context=context)
        page_elapsed = time.perf_counter() - page_t0
        ok = bool(content and not (content.startswith("[") and "]" in content[:40]))
        print(f"  [串行] 结束 #{i + 1}: {page_elapsed:.1f}s, ok={ok}")
        results.append(
            {
                "index": i,
                "title": label,
                "elapsed_sec": page_elapsed,
                "ok": ok,
                "content_len": len(content or ""),
            }
        )
    total = time.perf_counter() - t0

    return {
        "mode": "serial",
        "provider": provider_name,
        "n_pages": len(nodes),
        "elapsed_sec": total,
        "sum_page_sec": sum(r["elapsed_sec"] for r in results),
        "ok_count": sum(1 for r in results if r["ok"]),
        "pages": results,
    }


def run_parallel(
    nodes: list[dict[str, Any]],
    context: str = SAMPLE_CONTEXT,
    provider: str | None = None,
    max_workers: int = DEFAULT_MAX_WORKERS,
) -> dict[str, Any]:
    if provider is not None:
        llm = LLMService()
        llm.switch_provider(provider)

    items = [
        {"index": i, "outline_node": node, "context": context}
        for i, node in enumerate(nodes)
    ]
    report = expand_content_batch(items, context=context, max_workers=max_workers)
    llm = LLMService()
    pages = [
        {
            "index": r["index"],
            "title": nodes[r["index"]].get("title") or f"page-{r['index']}",
            "elapsed_sec": 0.0,
            "ok": r["success"],
            "content_len": len(r.get("content") or ""),
        }
        for r in report["results"]
    ]

    return {
        "mode": "parallel",
        "provider": llm.provider_name,
        "max_workers": max_workers,
        "n_pages": len(nodes),
        "elapsed_sec": report["elapsed_sec"],
        "sum_page_sec": 0.0,
        "ok_count": sum(1 for r in pages if r["ok"]),
        "pages": pages,
    }


def run_comparison(
    provider: str | None = None,
    max_workers: int = DEFAULT_MAX_WORKERS,
    outline: dict[str, Any] | None = None,
) -> dict[str, Any]:
    nodes = outline_to_nodes(outline or SAMPLE_OUTLINE)
    print(f"\n示例大纲: {outline or SAMPLE_OUTLINE}")
    print(f"共 {len(nodes)} 页待生成正文\n")

    print("=" * 56)
    print("【1/2】串行（单 LLMService，逐页调用）")
    print("=" * 56)
    serial = run_serial(nodes, provider=provider)

    print("\n" + "=" * 56)
    print(f"【2/2】并行（expand_content_batch, max_workers={max_workers}）")
    print("=" * 56)
    parallel = run_parallel(nodes, provider=provider, max_workers=max_workers)

    saved = serial["elapsed_sec"] - parallel["elapsed_sec"]
    speedup = serial["elapsed_sec"] / parallel["elapsed_sec"] if parallel["elapsed_sec"] > 0 else 0.0

    return {
        "n_pages": len(nodes),
        "serial": serial,
        "parallel": parallel,
        "saved_sec": saved,
        "speedup": speedup,
    }


def print_comparison_report(report: dict[str, Any]) -> None:
    serial = report["serial"]
    parallel = report["parallel"]

    print(f"\n{'=' * 56}")
    print("正文生成耗时对比（固定示例大纲）")
    print(f"{'=' * 56}")
    print(f"页数:           {report['n_pages']}")
    print(f"模型 provider:  {serial['provider']}")
    print(f"串行总耗时:     {serial['elapsed_sec']:.2f} 秒  (成功 {serial['ok_count']}/{serial['n_pages']})")
    print(f"并行总耗时:     {parallel['elapsed_sec']:.2f} 秒  (成功 {parallel['ok_count']}/{parallel['n_pages']}, workers={parallel['max_workers']})")
    print(f"节省:           {report['saved_sec']:.2f} 秒")
    print(f"加速比:         {report['speedup']:.2f}x")
    print(f"（各页耗时之和: 串行 {serial['sum_page_sec']:.1f}s / 并行 {parallel['sum_page_sec']:.1f}s）")
    print(f"{'=' * 56}\n")

    print("各页耗时（秒）:")
    print(f"{'#':<4} {'标题':<20} {'串行':>8} {'并行':>8}")
    for s, p in zip(serial["pages"], parallel["pages"]):
        print(f"{s['index'] + 1:<4} {str(s['title'])[:18]:<20} {s['elapsed_sec']:>8.1f} {p['elapsed_sec']:>8.1f}")
    print()


def test_content_serial_vs_parallel():
    """集成测试：对比串行与并行，并打印报告。"""
    report = run_comparison(max_workers=DEFAULT_MAX_WORKERS)
    print_comparison_report(report)
    assert report["serial"]["elapsed_sec"] > 0
    assert report["parallel"]["elapsed_sec"] > 0
    assert report["serial"]["ok_count"] > 0
    assert report["parallel"]["ok_count"] > 0


def main() -> None:
    provider = sys.argv[1] if len(sys.argv) > 1 else None
    max_workers = int(sys.argv[2]) if len(sys.argv) > 2 else DEFAULT_MAX_WORKERS
    report = run_comparison(provider=provider, max_workers=max_workers)
    print_comparison_report(report)


if __name__ == "__main__":
    main()
