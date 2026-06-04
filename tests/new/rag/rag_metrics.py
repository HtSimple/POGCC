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

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class RagQualitySummary:
    corpus_file: str
    num_chunks: int
    ingest_status: str
    embedding_model: str
    case_count: int
    hit_count: int
    miss_count: int
    hit_rate: float
    avg_search_ms: float
    min_top_k_hit_rate: float
    cases: List[QueryCaseMetric] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "corpus_file": self.corpus_file,
            "num_chunks": self.num_chunks,
            "ingest_status": self.ingest_status,
            "embedding_model": self.embedding_model,
            "case_count": self.case_count,
            "hit_count": self.hit_count,
            "miss_count": self.miss_count,
            "hit_rate": round(self.hit_rate, 4),
            "avg_search_ms": self.avg_search_ms,
            "min_top_k_hit_rate": self.min_top_k_hit_rate,
            "cases": [c.to_dict() for c in self.cases],
        }


_SUMMARY: Optional[RagQualitySummary] = None


def set_rag_quality_summary(summary: RagQualitySummary) -> None:
    global _SUMMARY
    _SUMMARY = summary


def get_rag_quality_summary() -> Optional[RagQualitySummary]:
    return _SUMMARY


def _evaluation_text_and_sources(results, case: Dict[str, Any]) -> tuple[str, set[str]]:
    """Default: only Top-1 counts (stricter than merging all Top-K)."""
    if not results:
        return "", set()

    scope = str(case.get("hit_scope") or "topk").lower()
    if scope == "topk":
        text = "\n".join(item.text or "" for item in results)
        sources = {item.source_file for item in results if item.source_file}
        return text, sources

    top = results[0]
    text = top.text or ""
    sources = {top.source_file} if top.source_file else set()
    return text, sources


def case_hit(results, case: Dict[str, Any]) -> tuple[bool, List[str]]:
    if not results:
        return False, []

    text, source_files = _evaluation_text_and_sources(results, case)
    any_words = case.get("must_contain_any") or []
    all_words = case.get("must_contain_all") or []
    expected_source = case.get("source_file")

    matched = [w for w in any_words if w in text]
    matched += [w for w in all_words if w in text]

    any_ok = not any_words or any(word in text for word in any_words)
    all_ok = not all_words or all(word in text for word in all_words)
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
        miss_count=case_count - hit_count,
        hit_rate=hit_count / max(1, case_count),
        avg_search_ms=round(avg_ms, 1),
        min_top_k_hit_rate=min_hit_rate,
        cases=case_metrics,
    )


def _short_path(path: str, max_len: int = 56) -> str:
    if len(path) <= max_len:
        return path
    return "..." + path[-(max_len - 3) :]


def format_summary_lines(summary: RagQualitySummary) -> List[str]:
    lines = [
        "",
        "【概览】",
        f"  语料文件      {summary.corpus_file}",
        f"  Chunk 数量    {summary.num_chunks}",
        f"  入库状态      {summary.ingest_status}",
        f"  Embedding     {_short_path(summary.embedding_model)}",
        f"  用例总数      {summary.case_count}",
        f"  命中 / 未命中 {summary.hit_count} / {summary.miss_count}",
        f"  命中率        {summary.hit_rate:.1%}  (阈值 >= {summary.min_top_k_hit_rate:.0%})",
        f"  平均检索耗时  {summary.avg_search_ms} ms",
        f"  判定规则      Top-K 合并文本 + must_contain_all + 来源文件",
        "",
        "【逐条结果】",
        f"  {'ID':<22} {'结果':<5} {'耗时':>6}  {'Top-1':>7}  {'K':>3}  {'命中词'}",
        f"  {'-' * 22} {'-' * 5} {'-' * 6}  {'-' * 7}  {'-' * 3}  {'-' * 20}",
    ]
    for item in summary.cases:
        flag = "PASS" if item.hit else "FAIL"
        score = f"{item.top_score:.4f}" if item.top_score is not None else "  n/a"
        keywords = ", ".join(item.matched_keywords) if item.matched_keywords else "-"
        if len(keywords) > 36:
            keywords = keywords[:33] + "..."
        lines.append(
            f"  {item.case_id:<22} {flag:<5} {item.elapsed_ms:>5}ms  {score:>7}  {item.top_k:>3}  {keywords}"
        )

    misses = [c for c in summary.cases if not c.hit]
    if misses:
        lines.extend(["", "【未命中 query】"])
        for item in misses:
            lines.append(f"  - {item.case_id}: {item.query}")
    return lines
