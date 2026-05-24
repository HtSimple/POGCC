from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

CURRENT = Path(__file__).resolve()
TESTING_DIR = CURRENT.parents[2]
QV_ROOT = CURRENT.parents[1]
OUTPUT_DIR = QV_ROOT / "outputs"
if str(TESTING_DIR) not in sys.path:
    sys.path.insert(0, str(TESTING_DIR))

from _test_utils import (  # noqa: E402
    add_project_root_to_path,
    authority_domain_score,
    contains_any,
    domain_from_url,
    load_json,
    normalize_text,
    save_json,
    score_0_to_5,
)

ROOT = add_project_root_to_path(CURRENT)

from app.services.llm_service import LLMService  # noqa: E402
from app.utils.json_protocol import parse_json_object  # noqa: E402

SCORE_KEYS = ("relevance", "authority", "coverage", "diversity", "redundancy")

SEARCH_QUALITY_PROMPT = """你是检索质量评估专家。请根据「主题」「要点」和「检索结果列表」，评估这批网络检索结果的质量。

评分维度（每项 0~5 分，可为小数，5 最好）：
- relevance：结果与主题/要点的相关程度
- authority：来源是否权威可信（政府、高校、国际组织、权威媒体等高于营销博客）
- coverage：要点列表被检索结果覆盖的比例与深度
- diversity：来源域名/视角是否多样，避免单一站点刷屏
- redundancy：去重质量（5=几乎无重复，0=大量重复或同质内容）

要求：
1. 只依据提供的检索结果判断，不要引入外部知识
2. coverage_checklist 必须覆盖输入中的每个 key_point
3. 只输出 JSON，不要 Markdown 代码块

输出格式：
{{
  "scores": {{
    "relevance": 0,
    "authority": 0,
    "coverage": 0,
    "diversity": 0,
    "redundancy": 0
  }},
  "overall_comment": "50字以内中文总评",
  "coverage_checklist": [
    {{
      "point": "要点原文",
      "covered": true,
      "evidence": "支持该要点的结果标题或摘录，未覆盖则空字符串"
    }}
  ],
  "result_reviews": [
    {{
      "index": 1,
      "relevant": true,
      "reason": "30字以内中文理由"
    }}
  ]
}}

主题：{topic}

要点（JSON 数组）：
{key_points_json}

检索结果：
{results_block}
"""


def is_llm_error_text(text: str) -> bool:
    text = (text or "").strip()
    return text.startswith("[") and "]" in text[:40]


def clamp_score(value: Any) -> float:
    try:
        num = float(value)
    except (TypeError, ValueError):
        return 0.0
    return round(max(0.0, min(5.0, num)), 2)


def build_results_block(results: List[dict], max_result_chars: int) -> str:
    if not results:
        return "（无检索结果）"
    blocks: List[str] = []
    for idx, item in enumerate(results, start=1):
        title = str(item.get("title") or "").strip()
        url = str(item.get("url") or "").strip()
        content = str(item.get("content") or item.get("snippet") or "").strip()
        if len(content) > max_result_chars:
            content = content[: max(0, max_result_chars - 20)] + "\n...(truncated)"
        blocks.append(
            f"[结果 {idx}]\n标题: {title}\nURL: {url}\n正文:\n{content or '（无正文）'}"
        )
    return "\n\n".join(blocks)


def normalize_scores(raw: Any) -> Dict[str, float]:
    src = raw if isinstance(raw, dict) else {}
    return {key: clamp_score(src.get(key)) for key in SCORE_KEYS}


def normalize_coverage_checklist(raw: Any, key_points: List[str]) -> List[Dict[str, Any]]:
    items = raw if isinstance(raw, list) else []
    by_point: Dict[str, Dict[str, Any]] = {}
    for item in items:
        if not isinstance(item, dict):
            continue
        point = str(item.get("point") or "").strip()
        if not point:
            continue
        by_point[point] = {
            "point": point,
            "covered": bool(item.get("covered")),
            "evidence": str(item.get("evidence") or "").strip()[:500],
        }

    checklist: List[Dict[str, Any]] = []
    for point in key_points:
        if point in by_point:
            checklist.append(by_point[point])
        else:
            checklist.append({"point": point, "covered": False, "evidence": ""})
    return checklist


def normalize_result_reviews(raw: Any, result_count: int) -> List[Dict[str, Any]]:
    items = raw if isinstance(raw, list) else []
    reviews: List[Dict[str, Any]] = []
    for item in items:
        if not isinstance(item, dict):
            continue
        try:
            index = int(item.get("index"))
        except (TypeError, ValueError):
            continue
        reviews.append(
            {
                "index": index,
                "relevant": bool(item.get("relevant")),
                "reason": str(item.get("reason") or "").strip()[:200],
            }
        )
    if not reviews and result_count > 0:
        reviews = [
            {"index": i, "relevant": None, "reason": "LLM 未返回逐条评审"}
            for i in range(1, result_count + 1)
        ]
    return reviews


def llm_judge_search_quality(
    llm: LLMService,
    topic: str,
    key_points: List[str],
    results: List[dict],
    *,
    max_result_chars: int,
    temperature: float,
    max_tokens: int,
    retries: int,
) -> Dict[str, Any]:
    prompt = SEARCH_QUALITY_PROMPT.format(
        topic=topic or "未指定主题",
        key_points_json=json.dumps(key_points, ensure_ascii=False, indent=2),
        results_block=build_results_block(results, max_result_chars),
    )

    last_error = ""
    for attempt in range(1, retries + 1):
        try:
            raw = llm.generate_json_object(prompt, temperature=temperature, max_tokens=max_tokens)
            if is_llm_error_text(raw):
                raise RuntimeError(raw)
            data = parse_json_object(raw)
            return {
                "scores": normalize_scores(data.get("scores")),
                "overall_comment": str(data.get("overall_comment") or "").strip()[:300],
                "coverage_checklist": normalize_coverage_checklist(
                    data.get("coverage_checklist"), key_points
                ),
                "result_reviews": normalize_result_reviews(
                    data.get("result_reviews"), len(results)
                ),
                "judge": "llm",
                "judge_error": None,
            }
        except Exception as exc:
            last_error = str(exc)
            if attempt < retries:
                time.sleep(1.5 * attempt)
    raise RuntimeError(last_error or "LLM search quality evaluation failed")


def score_record_lexical(record: dict) -> dict:
    """Legacy rule-based scorer used only for fallback."""
    topic = record.get("topic", "")
    key_points = record.get("key_points", []) or []
    results = record.get("search_results", []) or []

    if not results:
        scores = {key: 0.0 for key in SCORE_KEYS}
        return {
            **record,
            "scores": {**record.get("scores", {}), **scores},
            "coverage_checklist": [
                {"point": p, "covered": False, "evidence": ""} for p in key_points
            ],
            "search_quality_judge": "lexical",
        }

    joined_results = []
    domains = []
    titles = []
    relevant_count = 0
    authority_sum = 0.0

    for r in results:
        text = " ".join(str(r.get(k, "")) for k in ("title", "content", "snippet", "url"))
        joined_results.append(text)
        titles.append(normalize_text(r.get("title", "")))
        domain = domain_from_url(r.get("url", ""))
        domains.append(domain)
        authority_sum += authority_domain_score(domain)
        if contains_any(text, [topic]) or contains_any(text, key_points):
            relevant_count += 1

    all_text = "\n".join(joined_results)
    covered_points = [p for p in key_points if contains_any(all_text, [p])]
    unique_domains = set(d for d in domains if d)
    duplicate_titles = len([t for t in titles if t]) - len(set(t for t in titles if t))

    scores = {
        "relevance": score_0_to_5(relevant_count / max(1, len(results))),
        "authority": score_0_to_5(authority_sum / max(1, len(results))),
        "coverage": score_0_to_5(len(covered_points) / max(1, len(key_points))),
        "diversity": score_0_to_5(len(unique_domains) / max(1, len(results))),
        "redundancy": score_0_to_5(1.0 - max(0, duplicate_titles) / max(1, len(results))),
    }

    out = dict(record)
    out["scores"] = {**record.get("scores", {}), **scores}
    out["coverage_checklist"] = [
        {"point": p, "covered": p in covered_points, "evidence": ""} for p in key_points
    ]
    out["search_quality_judge"] = "lexical"
    out["search_quality_comment"] = "rule-based fallback"
    return out


def score_record(
    record: dict,
    llm: Optional[LLMService],
    *,
    max_result_chars: int,
    temperature: float,
    max_tokens: int,
    retries: int,
    fallback_lexical: bool,
) -> dict:
    topic = str(record.get("topic") or "")
    key_points = list(record.get("key_points") or [])
    results = list(record.get("search_results") or [])

    out = dict(record)
    if not results:
        out["scores"] = {**record.get("scores", {}), **{key: 0.0 for key in SCORE_KEYS}}
        out["coverage_checklist"] = [
            {"point": p, "covered": False, "evidence": ""} for p in key_points
        ]
        out["search_quality_judge"] = "empty"
        out["search_quality_comment"] = "无检索结果"
        return out

    if llm is None:
        return score_record_lexical(record)

    try:
        judged = llm_judge_search_quality(
            llm,
            topic,
            key_points,
            results,
            max_result_chars=max_result_chars,
            temperature=temperature,
            max_tokens=max_tokens,
            retries=retries,
        )
        out["scores"] = {**record.get("scores", {}), **judged["scores"]}
        out["coverage_checklist"] = judged["coverage_checklist"]
        out["result_reviews"] = judged["result_reviews"]
        out["search_quality_judge"] = judged["judge"]
        out["search_quality_comment"] = judged["overall_comment"]
        out["search_quality_error"] = None
        return out
    except Exception as exc:
        if fallback_lexical:
            fallback = score_record_lexical(record)
            fallback["search_quality_error"] = str(exc)
            fallback["search_quality_comment"] = f"LLM 失败，已回退规则评分: {exc}"
            return fallback
        out["scores"] = {**record.get("scores", {}), **{key: 0.0 for key in SCORE_KEYS}}
        out["coverage_checklist"] = [
            {"point": p, "covered": False, "evidence": ""} for p in key_points
        ]
        out["search_quality_judge"] = "llm_error"
        out["search_quality_error"] = str(exc)
        out["search_quality_comment"] = f"LLM 判定失败: {exc}"
        return out


def summarize(records: list[dict]) -> dict:
    summary: Dict[str, Any] = {}
    for name in SCORE_KEYS:
        vals = [
            (r.get("scores", {}) or {}).get(name)
            for r in records
            if isinstance((r.get("scores", {}) or {}).get(name), (int, float))
        ]
        summary[name + "_avg"] = round(sum(vals) / len(vals), 3) if vals else None
    return summary


def run(
    input_path: str,
    output_path: str,
    *,
    provider: Optional[str],
    max_result_chars: int,
    temperature: float,
    max_tokens: int,
    retries: int,
    fallback_lexical: bool,
    dry_run: bool,
) -> None:
    data = load_json(input_path)
    records = data.get("records", data if isinstance(data, list) else [])

    llm: Optional[LLMService] = None
    llm_provider = None
    if not dry_run:
        llm = LLMService()
        if provider:
            llm.switch_provider(provider)
        llm_provider = llm.provider_name
        print(f"[search_quality] LLM provider: {llm_provider}, records: {len(records)}")
    else:
        print("[search_quality] dry-run mode: using lexical fallback only")

    scored = []
    for idx, record in enumerate(records, start=1):
        topic = record.get("topic") or f"record-{idx}"
        print(f"[search_quality] ({idx}/{len(records)}) judging: {topic}")
        started = time.perf_counter()
        scored.append(
            score_record(
                record,
                None if dry_run else llm,
                max_result_chars=max_result_chars,
                temperature=temperature,
                max_tokens=max_tokens,
                retries=retries,
                fallback_lexical=fallback_lexical or dry_run,
            )
        )
        elapsed = time.perf_counter() - started
        scores = scored[-1].get("scores") or {}
        print(
            f"  done in {elapsed:.1f}s, "
            f"relevance={scores.get('relevance')} coverage={scores.get('coverage')} "
            f"judge={scored[-1].get('search_quality_judge')}"
        )

    out = dict(data) if isinstance(data, dict) else {}
    out["records"] = scored
    out["search_quality_summary"] = summarize(scored)
    out["search_quality_meta"] = {
        "judge_method": "llm" if not dry_run else "dry_run",
        "llm_provider": llm_provider,
        "max_result_chars": max_result_chars,
        "temperature": temperature,
        "retries": retries,
        "fallback_lexical": fallback_lexical,
    }
    out["search_quality_note"] = (
        "Search quality is judged by LLM-as-a-Judge over retrieved web results. "
        "Combine with manual audit for final acceptance."
    )
    save_json(output_path, out)
    print(f"Saved search quality report: {output_path}")


def main():
    parser = argparse.ArgumentParser(description="Evaluate search quality using LLM-as-a-Judge.")
    parser.add_argument(
        "--input",
        default=str(OUTPUT_DIR / "quality_validation_results.json"),
        help="Input JSON under tests/new/quality_validation/outputs/",
    )
    parser.add_argument(
        "--output",
        default=str(OUTPUT_DIR / "search_quality_report.json"),
        help="Output report path",
    )
    parser.add_argument("--provider", choices=["deepseek", "qwen"], default=None)
    parser.add_argument("--max-result-chars", type=int, default=1800, help="Max chars per search result.")
    parser.add_argument("--temperature", type=float, default=0.1)
    parser.add_argument("--max-tokens", type=int, default=4096)
    parser.add_argument("--retries", type=int, default=2, help="JSON/LLM failure retries per record.")
    parser.add_argument(
        "--fallback-lexical",
        action="store_true",
        help="Fall back to rule-based scoring if LLM fails.",
    )
    parser.add_argument("--dry-run", action="store_true", help="Skip LLM and use lexical fallback.")
    args = parser.parse_args()
    run(
        args.input,
        args.output,
        provider=args.provider,
        max_result_chars=args.max_result_chars,
        temperature=args.temperature,
        max_tokens=args.max_tokens,
        retries=args.retries,
        fallback_lexical=args.fallback_lexical,
        dry_run=args.dry_run,
    )


if __name__ == "__main__":
    main()

'''
python tests/new/quality_validation/scripts/eval_search_quality.py --max-tokens 8192 --retries 2
'''