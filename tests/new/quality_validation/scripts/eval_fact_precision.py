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
    classify_claim_by_evidence,
    evidence_texts_from_record,
    load_json,
    save_json,
    split_claims,
)

ROOT = add_project_root_to_path(CURRENT)

from app.services.llm_service import LLMService  # noqa: E402
from app.utils.json_protocol import parse_json_object  # noqa: E402

VALID_STATUSES = {"supported", "insufficient", "contradicted", "no_evidence"}

FACT_CHECK_PROMPT = """你是严谨的事实核查员。请仅依据下方「证据材料」判断每条「待核查断言」是否成立。

判定标准：
- supported：证据能明确支持该断言（允许同义改写，不要求字面一致）
- insufficient：证据部分相关，但不足以完整支持，或只能弱支持
- contradicted：证据与该断言明显矛盾
- no_evidence：证据中找不到与该断言相关的信息

要求：
1. 必须逐条输出，claim 字段与输入断言原文完全一致
2. 不要引入证据材料之外的新事实
3. 只输出 JSON，不要 Markdown 代码块

输出格式：
{{
  "claims": [
    {{
      "claim": "断言原文",
      "status": "supported|insufficient|contradicted|no_evidence",
      "reason": "简要中文理由",
      "evidence_excerpt": "支撑判断的证据摘录，没有则空字符串"
    }}
  ]
}}

主题：{topic}

待核查断言（JSON 数组）：
{claims_json}

证据材料：
{evidence_block}
"""


def extract_generated_text(record: dict) -> str:
    answer = record.get("answer") or record.get("generated_text") or record.get("content") or ""
    page_content = record.get("page_content") or {}
    if isinstance(page_content, dict):
        for slide in page_content.get("slides", []) or []:
            answer += "\n" + str(slide.get("coreMessage", ""))
            answer += "\n" + "\n".join(slide.get("displayBullets", []) or [])
            answer += "\n" + str(slide.get("speakerNotes", ""))
    return answer.strip()


def build_evidence_block(evidence_texts: List[str], max_chars: int) -> str:
    if not evidence_texts:
        return "（无可用证据）"
    blocks: List[str] = []
    used = 0
    for idx, text in enumerate(evidence_texts, start=1):
        chunk = text.strip()
        if not chunk:
            continue
        remain = max_chars - used
        if remain <= 0:
            break
        if len(chunk) > remain:
            chunk = chunk[: max(0, remain - 20)] + "\n...(truncated)"
        blocks.append(f"[证据 {idx}]\n{chunk}")
        used += len(chunk)
    return "\n\n".join(blocks) if blocks else "（无可用证据）"


def is_llm_error_text(text: str) -> bool:
    text = (text or "").strip()
    return text.startswith("[") and "]" in text[:40]


def normalize_llm_claims(raw_claims: Any, input_claims: List[str]) -> List[Dict[str, Any]]:
    if not isinstance(raw_claims, list):
        raise ValueError("LLM response claims must be a list")

    by_text = {}
    for item in raw_claims:
        if not isinstance(item, dict):
            continue
        claim_text = str(item.get("claim") or "").strip()
        status = str(item.get("status") or "no_evidence").strip().lower()
        if status not in VALID_STATUSES:
            status = "no_evidence"
        normalized = {
            "claim": claim_text,
            "status": status,
            "reason": str(item.get("reason") or "").strip(),
            "evidence_excerpt": str(item.get("evidence_excerpt") or "").strip()[:500],
            "judge": "llm",
        }
        if claim_text:
            by_text[claim_text] = normalized

    checked: List[Dict[str, Any]] = []
    for claim in input_claims:
        if claim in by_text:
            checked.append(by_text[claim])
        else:
            # fuzzy fallback: first item whose claim is substring-related
            matched = None
            for item in by_text.values():
                c = item.get("claim") or ""
                if c == claim or c in claim or claim in c:
                    matched = dict(item)
                    matched["claim"] = claim
                    break
            if matched:
                checked.append(matched)
            else:
                checked.append(
                    {
                        "claim": claim,
                        "status": "no_evidence",
                        "reason": "LLM 未返回该断言的判定结果",
                        "evidence_excerpt": "",
                        "judge": "llm",
                    }
                )
    return checked


def llm_judge_claims(
    llm: LLMService,
    topic: str,
    claims: List[str],
    evidence_texts: List[str],
    max_evidence_chars: int,
    temperature: float,
    max_tokens: int,
) -> List[Dict[str, Any]]:
    if not claims:
        return []

    prompt = FACT_CHECK_PROMPT.format(
        topic=topic or "未指定主题",
        claims_json=json.dumps(claims, ensure_ascii=False, indent=2),
        evidence_block=build_evidence_block(evidence_texts, max_evidence_chars),
    )
    raw = llm.generate_json_object(prompt, temperature=temperature, max_tokens=max_tokens)
    if is_llm_error_text(raw):
        raise RuntimeError(raw)

    data = parse_json_object(raw)
    return normalize_llm_claims(data.get("claims"), claims)


def evaluate_record(
    record: dict,
    llm: Optional[LLMService],
    *,
    max_claims: int,
    max_evidence_chars: int,
    temperature: float,
    max_tokens: int,
    fallback_lexical: bool,
    lexical_threshold: float,
) -> dict:
    answer = extract_generated_text(record)
    claims = split_claims(answer)[: max(1, max_claims)]
    evidence_texts = evidence_texts_from_record(record)
    topic = str(record.get("topic") or "")

    checked: List[Dict[str, Any]] = []
    judge_error = ""

    if llm is not None and claims:
        try:
            checked = llm_judge_claims(
                llm,
                topic,
                claims,
                evidence_texts,
                max_evidence_chars=max_evidence_chars,
                temperature=temperature,
                max_tokens=max_tokens,
            )
        except Exception as exc:
            judge_error = str(exc)
            if not fallback_lexical:
                checked = [
                    {
                        "claim": c,
                        "status": "no_evidence",
                        "reason": f"LLM 判定失败: {judge_error}",
                        "evidence_excerpt": "",
                        "judge": "llm_error",
                    }
                    for c in claims
                ]
            else:
                checked = [
                    classify_claim_by_evidence(c, evidence_texts, threshold=lexical_threshold)
                    for c in claims
                ]
                for item in checked:
                    item["judge"] = "lexical_fallback"
                    item["reason"] = f"LLM 失败，回退词面匹配: {judge_error}"
    elif fallback_lexical and claims:
        checked = [
            classify_claim_by_evidence(c, evidence_texts, threshold=lexical_threshold)
            for c in claims
        ]
        for item in checked:
            item["judge"] = "lexical"
    else:
        checked = []

    counts = {"supported": 0, "insufficient": 0, "contradicted": 0, "no_evidence": 0}
    for item in checked:
        status = item.get("status") or "no_evidence"
        if status not in VALID_STATUSES:
            status = "no_evidence"
        counts[status] = counts.get(status, 0) + 1

    if checked:
        precision = round(counts["supported"] / len(checked), 4)
    else:
        precision = None

    out = dict(record)
    out["fact_check"] = {
        **(record.get("fact_check") or {}),
        **counts,
        "total_claims": len(checked),
        "precision": precision,
        "claims": checked,
        "judge_method": "llm" if llm is not None else "lexical",
        "judge_error": judge_error or None,
    }
    return out


def summarize(records: list[dict], baseline_precision: float | None = None) -> dict:
    precisions = [
        r.get("fact_check", {}).get("precision")
        for r in records
        if isinstance(r.get("fact_check", {}).get("precision"), (int, float))
    ]
    avg = round(sum(precisions) / len(precisions), 4) if precisions else 0.0
    summary = {
        "record_count": len(records),
        "avg_fact_precision": avg,
        "judge_method": records[0].get("fact_check", {}).get("judge_method") if records else "llm",
    }
    if baseline_precision is not None and baseline_precision > 0:
        summary["relative_improvement"] = round((avg - baseline_precision) / baseline_precision, 4)
        summary["meets_50_percent_improvement"] = summary["relative_improvement"] >= 0.5
    return summary


def run(
    input_path: str,
    output_path: str,
    *,
    provider: Optional[str],
    max_claims: int,
    max_evidence_chars: int,
    temperature: float,
    max_tokens: int,
    baseline_precision: float | None,
    fallback_lexical: bool,
    lexical_threshold: float,
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
        print(f"[fact_precision] LLM provider: {llm_provider}, records: {len(records)}")
    else:
        print("[fact_precision] dry-run mode: LLM will not be called")

    evaluated = []
    for idx, record in enumerate(records, start=1):
        topic = record.get("topic") or f"record-{idx}"
        print(f"[fact_precision] ({idx}/{len(records)}) judging: {topic}")
        started = time.perf_counter()
        evaluated.append(
            evaluate_record(
                record,
                llm,
                max_claims=max_claims,
                max_evidence_chars=max_evidence_chars,
                temperature=temperature,
                max_tokens=max_tokens,
                fallback_lexical=fallback_lexical,
                lexical_threshold=lexical_threshold,
            )
        )
        elapsed = time.perf_counter() - started
        precision = evaluated[-1].get("fact_check", {}).get("precision")
        print(f"  done in {elapsed:.1f}s, precision={precision}")

    out = dict(data) if isinstance(data, dict) else {}
    out["records"] = evaluated
    out["fact_precision_summary"] = summarize(evaluated, baseline_precision=baseline_precision)
    out["fact_precision_meta"] = {
        "judge_method": "llm" if not dry_run else "dry_run",
        "llm_provider": llm_provider,
        "max_claims": max_claims,
        "max_evidence_chars": max_evidence_chars,
        "temperature": temperature,
        "fallback_lexical": fallback_lexical,
    }
    out["fact_precision_note"] = (
        "Claims are judged by LLM against retrieved evidence (LLM-as-a-Judge). "
        "Combine with manual audit for final acceptance."
    )
    save_json(output_path, out)
    print(f"Saved fact precision report: {output_path}")


def main():
    parser = argparse.ArgumentParser(description="Evaluate factual precision using LLM-as-a-Judge.")
    parser.add_argument(
        "--input",
        default=str(OUTPUT_DIR / "quality_validation_results.json"),
        help="Input JSON with records.",
    )
    parser.add_argument(
        "--output",
        default=str(OUTPUT_DIR / "fact_precision_report.json"),
        help="Output report path.",
    )
    parser.add_argument("--provider", choices=["deepseek", "qwen"], default=None, help="LLM provider override.")
    parser.add_argument("--max-claims", type=int, default=12, help="Max claims per record sent to LLM.")
    parser.add_argument("--max-evidence-chars", type=int, default=12000, help="Max evidence chars per record.")
    parser.add_argument("--temperature", type=float, default=0.1, help="LLM temperature.")
    parser.add_argument("--max-tokens", type=int, default=4096, help="LLM max tokens.")
    parser.add_argument(
        "--baseline-precision",
        type=float,
        default=None,
        help="Baseline model precision for relative improvement calculation.",
    )
    parser.add_argument(
        "--fallback-lexical",
        action="store_true",
        help="If LLM fails, fall back to lexical Jaccard matching.",
    )
    parser.add_argument(
        "--lexical-threshold",
        type=float,
        default=0.18,
        help="Threshold for lexical fallback only.",
    )
    parser.add_argument("--dry-run", action="store_true", help="Parse input only, do not call LLM.")
    args = parser.parse_args()
    run(
        args.input,
        args.output,
        provider=args.provider,
        max_claims=args.max_claims,
        max_evidence_chars=args.max_evidence_chars,
        temperature=args.temperature,
        max_tokens=args.max_tokens,
        baseline_precision=args.baseline_precision,
        fallback_lexical=args.fallback_lexical,
        lexical_threshold=args.lexical_threshold,
        dry_run=args.dry_run,
    )


if __name__ == "__main__":
    main()
# python tests/new/quality_validation/scripts/eval_fact_precision.py --max-tokens 8192 --max-claims 6