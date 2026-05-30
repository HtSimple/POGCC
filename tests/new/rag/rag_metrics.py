from __future__ import annotations

import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional


@dataclass
class QueryCaseMetric:
    case_id: str
    query: str
    top_k: int
    hit: bool
    elapsed_ms: int
    result_count: int
    top_score: Optional[float]
    matched_keywords: List[str] = field(default_factory=list)
    source_files: List[str] = field(default_factory=list)
    top_preview: str = ""


@dataclass
class RagQualitySummary:
    corpus_file: str
    num_chunks: int
    ingest_status: str
    embedding_model: str
    case_count: int
    hit_count: int
    hit_rate: float
    avg_search_ms: float
    min_top_k_hit_rate: float
    cases: List[QueryCaseMetric] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        payload = asdict(self)
        payload["cases"] = [asdict(c) for c in self.cases]
        return payload


_SUMMARY: Optional[RagQualitySummary] = None


def set_rag_quality_summary(summary: RagQualitySummary) -> None:
    global _SUMMARY
    _SUMMARY = summary


def get_rag_quality_summary() -> Optional[RagQualitySummary]:
    return _SUMMARY


def case_hit(results, case: Dict[str, Any]) -> tuple[bool, List[str]]:
    if not results:
        return False, []

    joined = "\n".join(item.text or "" for item in results)
    any_words = case.get("must_contain_any") or []
    all_words = case.get("must_contain_all") or []
    expected_source = case.get("source_file")

    matched = [w for w in any_words if w in joined]
    matched += [w for w in all_words if w in joined]

    any_ok = not any_words or any(word in joined for word in any_words)
    all_ok = not all_words or all(word in joined for word in all_words)
    source_files = {item.source_file for item in results if item.source_file}
    source_ok = not expected_source or expected_source in source_files
    return any_ok and all_ok and source_ok, matched


def evaluate_query_case(service, case: Dict[str, Any]) -> QueryCaseMetric:
    top_k = int(case.get("top_k") or 3)
    started = time.perf_counter()
    resp = service.search(case["query"], top_k=top_k)
    elapsed_ms = int((time.perf_counter() - started) * 1000)

    hit, matched = case_hit(resp.results, case)
    top_score = resp.results[0].score if resp.results else None
    source_files = sorted({item.source_file for item in resp.results if item.source_file})
    preview = (resp.results[0].text[:120] + "...") if resp.results and len(resp.results[0].text) > 120 else (
        resp.results[0].text if resp.results else ""
    )

    return QueryCaseMetric(
        case_id=str(case.get("id") or case["query"]),
        query=case["query"],
        top_k=top_k,
        hit=hit,
        elapsed_ms=elapsed_ms,
        result_count=len(resp.results),
        top_score=top_score,
        matched_keywords=matched,
        source_files=source_files,
        top_preview=preview,
    )


def build_quality_summary(
    service,
    cases: List[Dict[str, Any]],
    corpus_path: Path,
    embedding_model: str,
    ingest_status: str,
    num_chunks: int,
    min_hit_rate: float,
) -> RagQualitySummary:
    case_metrics = [evaluate_query_case(service, case) for case in cases]
    hit_count = sum(1 for item in case_metrics if item.hit)
    case_count = len(case_metrics)
    avg_ms = sum(item.elapsed_ms for item in case_metrics) / max(1, case_count)

    return RagQualitySummary(
        corpus_file=corpus_path.name,
        num_chunks=num_chunks,
        ingest_status=ingest_status,
        embedding_model=embedding_model,
        case_count=case_count,
        hit_count=hit_count,
        hit_rate=hit_count / max(1, case_count),
        avg_search_ms=round(avg_ms, 1),
        min_top_k_hit_rate=min_hit_rate,
        cases=case_metrics,
    )


def format_summary_lines(summary: RagQualitySummary) -> List[str]:
    lines = [
        f"corpus_file     : {summary.corpus_file}",
        f"num_chunks      : {summary.num_chunks}",
        f"ingest_status   : {summary.ingest_status}",
        f"embedding_model : {summary.embedding_model}",
        f"hit_rate        : {summary.hit_count}/{summary.case_count} = {summary.hit_rate:.1%} (threshold >= {summary.min_top_k_hit_rate:.0%})",
        f"avg_search_ms   : {summary.avg_search_ms}",
        "",
        "Per-query results:",
    ]
    for item in summary.cases:
        flag = "HIT" if item.hit else "MISS"
        score = f"{item.top_score:.4f}" if item.top_score is not None else "n/a"
        lines.append(
            f"  [{flag}] {item.case_id:20s}  {item.elapsed_ms:4d}ms  top_score={score}  top_k={item.top_k}"
        )
        lines.append(f"         query: {item.query}")
        if item.matched_keywords:
            lines.append(f"         matched: {', '.join(item.matched_keywords)}")
        if item.source_files:
            lines.append(f"         sources: {', '.join(item.source_files)}")
        if item.top_preview:
            lines.append(f"         preview: {item.top_preview}")
    return lines
