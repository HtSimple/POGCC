"""
POGCC 全流程 E2E 测试（一键运行）。

在项目根目录执行：
    python tests/new/e2e/test_full_generation.py
    python tests/new/e2e/test_full_generation.py --topic "拿破仑" --with-batch
    python tests/new/e2e/test_full_generation.py --keep-server

pytest 模式（需后端已启动或同样会自动拉起）：
    pytest tests/new/e2e/test_full_generation.py -v -s

链路覆盖：
    GET  /health
    GET  /api/model/info
    POST /api/generator/outline
    POST /api/search/knowledge
    POST /api/search/knowledge/batch   (可选)
    POST /api/generator/content
    POST /api/generator/content/batch  (可选)
    POST /api/generator/notes
"""
from __future__ import annotations

import argparse
import atexit
import json
import os
import sys
import textwrap
import traceback
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import requests

try:
    import pytest
except ImportError:  # pragma: no cover - allow `python test_full_generation.py` without pytest
    pytest = None  # type: ignore

CURRENT = Path(__file__).resolve()
TESTING_DIR = CURRENT.parents[1]
E2E_OUTPUT_DIR = TESTING_DIR / "outputs" / "e2e"
if str(TESTING_DIR) not in sys.path:
    sys.path.insert(0, str(TESTING_DIR))

from _test_utils import (  # noqa: E402
    ManagedUvicornServer,
    build_knowledge_query,
    flatten_outline_slides,
    get_base_url,
    is_server_reachable,
    now_ms,
    outline_node_from_slide,
    page_content_to_plain_text,
    save_json,
)

pytestmark = pytest.mark.e2e if pytest else None

DEFAULT_TOPIC = "AI PPT大纲智能生成与内容补全系统"
DEFAULT_REQUIREMENTS = (
    "生成5页课程汇报PPT，包含背景、技术路线、RAG、测试和总结。"
    "语言使用中文，结构清晰，适合软件工程课程答辩。"
)
DEFAULT_CONTEXT = (
    "项目目标：解决 AI PPT 生成中的逻辑断层和事实幻觉问题，"
    "采用 RAG 与结构化 JSON Schema 协议。"
)


@dataclass
class StepResult:
    name: str
    ok: bool
    elapsed_ms: int
    endpoint: str
    message: str = ""
    detail: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class SlideSnapshot:
    slide_id: str
    slide_number: int
    slide_role: str
    section_title: str
    slide_title: str
    page_goal: str
    key_points: List[str]
    knowledge_preview: str = ""
    content_preview: str = ""
    notes_preview: str = ""


@dataclass
class FullGenerationReport:
    started_at: str
    base_url: str
    topic: str
    requirements: str
    success: bool
    total_elapsed_ms: int
    steps: List[StepResult] = field(default_factory=list)
    outline_summary: Dict[str, Any] = field(default_factory=dict)
    slides: List[SlideSnapshot] = field(default_factory=list)
    markdown_preview: str = ""
    errors: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        payload = asdict(self)
        payload["steps"] = [s if isinstance(s, dict) else s.to_dict() for s in self.steps]
        payload["slides"] = [s if isinstance(s, dict) else asdict(s) for s in self.slides]
        return payload


class E2EHttpClient:
    """Thin HTTP wrapper with timing and consistent error messages."""

    def __init__(self, base_url: str, default_timeout: int = 300) -> None:
        self.base_url = base_url.rstrip("/")
        self.default_timeout = default_timeout

    def get_json(self, path: str, timeout: Optional[int] = None) -> Tuple[dict, int]:
        started = now_ms()
        resp = requests.get(
            f"{self.base_url}{path}",
            timeout=timeout or self.default_timeout,
        )
        elapsed = now_ms() - started
        if resp.status_code != 200:
            raise RuntimeError(f"GET {path} -> HTTP {resp.status_code}: {resp.text[:800]}")
        return resp.json(), elapsed

    def post_json(self, path: str, payload: dict, timeout: Optional[int] = None) -> Tuple[dict, int]:
        started = now_ms()
        resp = requests.post(
            f"{self.base_url}{path}",
            json=payload,
            timeout=timeout or self.default_timeout,
        )
        elapsed = now_ms() - started
        if resp.status_code != 200:
            raise RuntimeError(f"POST {path} -> HTTP {resp.status_code}: {resp.text[:800]}")
        return resp.json(), elapsed


def truncate(text: str, limit: int = 240) -> str:
    text = str(text or "").strip()
    if len(text) <= limit:
        return text
    return text[: limit - 3] + "..."


def pick_content_slides(slides: List[Dict[str, Any]], limit: int = 3) -> List[Dict[str, Any]]:
    """Prefer non-cover slides; fall back to any slide if needed."""
    non_cover = [s for s in slides if (s.get("slideRole") or "").lower() != "cover"]
    pool = non_cover or slides
    return pool[: max(1, limit)]


def validate_outline_shape(outline: Dict[str, Any]) -> Tuple[bool, str]:
    if not outline:
        return False, "outline is empty"
    sections = outline.get("sections") or []
    if not sections:
        return False, "outline.sections is empty"
    flat = flatten_outline_slides(outline)
    if not flat:
        return False, "no slides under sections"
    target = outline.get("targetSlideCount")
    if isinstance(target, int) and target > 0 and len(flat) != target:
        return False, f"slide count {len(flat)} != targetSlideCount {target}"
    return True, "ok"


def build_markdown_preview(
    topic: str,
    outline: Dict[str, Any],
    slide_snapshots: List[SlideSnapshot],
) -> str:
    """Mirror frontend Step 5 markdown assembly (simplified)."""
    lines = [
        f"# {outline.get('presentationTitle') or topic}",
        "",
        f"> 受众：{outline.get('audienceProfile') or '未指定'}",
        f"> 页数：{outline.get('targetSlideCount') or len(slide_snapshots)}",
        "",
    ]
    snapshot_by_id = {s.slide_id: s for s in slide_snapshots}
    for section in outline.get("sections") or []:
        section_title = section.get("sectionTitle") or "未命名章节"
        lines.append(f"## {section_title}")
        lines.append("")
        for slide in section.get("slides") or []:
            slide_id = slide.get("slideId") or slide.get("id") or ""
            snap = snapshot_by_id.get(slide_id)
            title = slide.get("slideTitle") or slide.get("title") or "未命名页面"
            lines.append(f"### 第 {slide.get('slideNumber', '?')} 页 · {title}")
            goal = slide.get("pageGoal") or slide.get("goal") or ""
            if goal:
                lines.append(f"**目标**：{goal}")
            bullets = slide.get("keyPoints") or slide.get("bullets") or []
            for bp in bullets:
                lines.append(f"- {bp}")
            if snap and snap.content_preview:
                lines.append("")
                lines.append("**正文**")
                lines.append(snap.content_preview)
            if snap and snap.notes_preview:
                lines.append("")
                lines.append("**演讲备注**")
                lines.append(snap.notes_preview)
            lines.append("")
    return "\n".join(lines).strip() + "\n"


class FullGenerationRunner:
    def __init__(
        self,
        base_url: str,
        topic: str = DEFAULT_TOPIC,
        requirements: str = DEFAULT_REQUIREMENTS,
        shared_context: str = DEFAULT_CONTEXT,
        outline_timeout: int = 360,
        content_timeout: int = 360,
        notes_timeout: int = 180,
        knowledge_timeout: int = 300,
        batch_timeout: int = 600,
        knowledge_batch_size: int = 3,
        content_batch_size: int = 2,
        with_knowledge: bool = True,
        with_batch: bool = False,
        refine_knowledge: bool = False,
        max_workers: int = 2,
        verbose: bool = True,
    ) -> None:
        self.client = E2EHttpClient(base_url)
        self.topic = topic
        self.requirements = requirements
        self.shared_context = shared_context
        self.outline_timeout = outline_timeout
        self.content_timeout = content_timeout
        self.notes_timeout = notes_timeout
        self.knowledge_timeout = knowledge_timeout
        self.batch_timeout = batch_timeout
        self.knowledge_batch_size = knowledge_batch_size
        self.content_batch_size = content_batch_size
        self.with_knowledge = with_knowledge
        self.with_batch = with_batch
        self.refine_knowledge = refine_knowledge
        self.max_workers = max_workers
        self.verbose = verbose

        self.report = FullGenerationReport(
            started_at=datetime.now().isoformat(timespec="seconds"),
            base_url=base_url,
            topic=topic,
            requirements=requirements,
            success=False,
            total_elapsed_ms=0,
        )

    def log(self, msg: str) -> None:
        if self.verbose:
            print(msg)

    def record_step(
        self,
        name: str,
        ok: bool,
        elapsed_ms: int,
        endpoint: str,
        message: str = "",
        detail: Optional[Dict[str, Any]] = None,
    ) -> StepResult:
        step = StepResult(
            name=name,
            ok=ok,
            elapsed_ms=elapsed_ms,
            endpoint=endpoint,
            message=message,
            detail=detail or {},
        )
        self.report.steps.append(step)
        status = "OK" if ok else "FAIL"
        self.log(f"  [{status}] {name} ({elapsed_ms} ms) {message}")
        if not ok:
            self.report.errors.append(f"{name}: {message}")
        return step

    def step_health(self) -> None:
        self.log("\n[1/8] Health check")
        try:
            data, elapsed = self.client.get_json("/health", timeout=10)
            ok = data.get("status") == "healthy"
            self.record_step(
                "health",
                ok,
                elapsed,
                "GET /health",
                message=data.get("status", ""),
                detail=data,
            )
            if not ok:
                raise RuntimeError("health status is not healthy")
        except Exception as exc:
            self.record_step("health", False, 0, "GET /health", message=str(exc))
            raise

    def step_model_info(self) -> None:
        self.log("\n[2/8] Model info")
        try:
            data, elapsed = self.client.get_json("/api/model/info", timeout=15)
            provider = data.get("current_provider") or "unknown"
            available = data.get("available_providers") or []
            self.record_step(
                "model_info",
                True,
                elapsed,
                "GET /api/model/info",
                message=f"provider={provider}",
                detail={"current_provider": provider, "available_providers": available},
            )
        except Exception as exc:
            self.record_step("model_info", False, 0, "GET /api/model/info", message=str(exc))
            raise

    def step_outline(self) -> Dict[str, Any]:
        self.log("\n[3/8] Outline generation")
        try:
            data, elapsed = self.client.post_json(
                "/api/generator/outline",
                {"topic": self.topic, "requirements": self.requirements},
                timeout=self.outline_timeout,
            )
            outline = data.get("outline") or {}
            ok_shape, shape_msg = validate_outline_shape(outline)
            ok = bool(data.get("success")) and ok_shape
            slides = flatten_outline_slides(outline)
            self.report.outline_summary = {
                "presentationTitle": outline.get("presentationTitle"),
                "targetSlideCount": outline.get("targetSlideCount"),
                "sectionCount": len(outline.get("sections") or []),
                "slideCount": len(slides),
                "fallback_hint": "fallback" in str(data.get("message") or "").lower(),
                "message": data.get("message"),
            }
            self.record_step(
                "outline",
                ok,
                elapsed,
                "POST /api/generator/outline",
                message=shape_msg if ok else f"{data.get('message')} | {shape_msg}",
                detail={
                    "slide_count": len(slides),
                    "presentation_title": outline.get("presentationTitle"),
                },
            )
            if not ok:
                raise RuntimeError(f"outline failed: {shape_msg}")
            self.log(
                f"    title={truncate(outline.get('presentationTitle', ''), 60)} "
                f"slides={len(slides)} elapsed={elapsed}ms"
            )
            return outline
        except Exception as exc:
            if not any(s.name == "outline" for s in self.report.steps):
                self.record_step("outline", False, 0, "POST /api/generator/outline", message=str(exc))
            raise

    def step_knowledge_single(self, slide: Dict[str, Any]) -> str:
        self.log("\n[4/8] Single-page knowledge retrieval")
        query = build_knowledge_query(
            self.topic,
            slide.get("sectionTitle") or "",
            slide.get("slideTitle") or "",
            slide.get("keyPoints") or [],
        )
        try:
            data, elapsed = self.client.post_json(
                "/api/search/knowledge",
                {"topic": query, "refine_knowledge": self.refine_knowledge},
                timeout=self.knowledge_timeout,
            )
            knowledge = data.get("knowledge") or ""
            ok = bool(data.get("success")) and len(knowledge.strip()) >= 20
            self.record_step(
                "knowledge_single",
                ok,
                elapsed,
                "POST /api/search/knowledge",
                message=truncate(data.get("message") or knowledge, 120),
                detail={"query_lines": query.count("\n") + 1, "knowledge_len": len(knowledge)},
            )
            return knowledge
        except Exception as exc:
            self.record_step(
                "knowledge_single",
                False,
                0,
                "POST /api/search/knowledge",
                message=str(exc),
            )
            return ""

    def step_knowledge_batch(self, slides: List[Dict[str, Any]]) -> Dict[str, str]:
        self.log("\n[5/8] Batch knowledge retrieval")
        items = []
        for idx, slide in enumerate(slides[: self.knowledge_batch_size]):
            query = build_knowledge_query(
                self.topic,
                slide.get("sectionTitle") or "",
                slide.get("slideTitle") or "",
                slide.get("keyPoints") or [],
            )
            items.append(
                {
                    "index": idx,
                    "id": slide.get("slideId") or f"slide-{idx}",
                    "query": query,
                }
            )
        knowledge_map: Dict[str, str] = {}
        try:
            data, elapsed = self.client.post_json(
                "/api/search/knowledge/batch",
                {
                    "items": items,
                    "refine_knowledge": self.refine_knowledge,
                    "max_workers": self.max_workers,
                },
                timeout=self.batch_timeout,
            )
            results = data.get("results") or []
            success_count = sum(1 for r in results if r.get("success"))
            for item, result in zip(items, results):
                sid = item.get("id") or ""
                if sid and result.get("knowledge"):
                    knowledge_map[sid] = result["knowledge"]
            ok = bool(data.get("success")) and success_count > 0
            self.record_step(
                "knowledge_batch",
                ok,
                elapsed,
                "POST /api/search/knowledge/batch",
                message=f"{success_count}/{len(items)} succeeded, elapsed_sec={data.get('elapsed_sec')}",
                detail={"items": len(items), "success_count": success_count},
            )
        except Exception as exc:
            self.record_step(
                "knowledge_batch",
                False,
                0,
                "POST /api/search/knowledge/batch",
                message=str(exc),
            )
        return knowledge_map

    def step_content_single(
        self,
        slide: Dict[str, Any],
        knowledge: str,
    ) -> Tuple[str, Optional[Dict[str, Any]]]:
        self.log("\n[6/8] Single-page content expansion")
        node = outline_node_from_slide(slide)
        context_parts = [self.shared_context]
        if knowledge.strip():
            context_parts.append(f"检索资料：\n{knowledge}")
        context = "\n\n".join(p for p in context_parts if p.strip())
        try:
            data, elapsed = self.client.post_json(
                "/api/generator/content",
                {"outline_node": node, "context": context},
                timeout=self.content_timeout,
            )
            content = data.get("content") or ""
            page_content = data.get("page_content")
            if not content.strip() and page_content:
                content = page_content_to_plain_text(page_content)
            ok = bool(data.get("success")) and len(content.strip()) >= 10
            self.record_step(
                "content_single",
                ok,
                elapsed,
                "POST /api/generator/content",
                message=truncate(data.get("message") or content, 120),
                detail={
                    "slide_id": node.get("id"),
                    "content_len": len(content),
                    "has_page_content": page_content is not None,
                },
            )
            return content, page_content
        except Exception as exc:
            self.record_step(
                "content_single",
                False,
                0,
                "POST /api/generator/content",
                message=str(exc),
            )
            return "", None

    def step_content_batch(
        self,
        slides: List[Dict[str, Any]],
        knowledge_map: Dict[str, str],
    ) -> Dict[str, str]:
        self.log("\n[7/8] Batch content expansion")
        items = []
        for idx, slide in enumerate(slides[: self.content_batch_size]):
            node = outline_node_from_slide(slide)
            sid = slide.get("slideId") or f"slide-{idx}"
            ctx = self.shared_context
            if knowledge_map.get(sid):
                ctx = f"{ctx}\n\n检索资料：\n{knowledge_map[sid]}"
            items.append(
                {
                    "index": idx,
                    "id": sid,
                    "outline_node": node,
                    "context": ctx,
                }
            )
        content_map: Dict[str, str] = {}
        try:
            data, elapsed = self.client.post_json(
                "/api/generator/content/batch",
                {
                    "items": items,
                    "context": self.shared_context,
                    "max_workers": self.max_workers,
                },
                timeout=self.batch_timeout,
            )
            results = data.get("results") or []
            success_count = sum(1 for r in results if r.get("success"))
            for result in results:
                sid = result.get("id") or ""
                text = result.get("content") or ""
                if not text.strip() and result.get("page_content"):
                    text = page_content_to_plain_text(result.get("page_content"))
                if sid and text:
                    content_map[sid] = text
            ok = bool(data.get("success")) and success_count > 0
            self.record_step(
                "content_batch",
                ok,
                elapsed,
                "POST /api/generator/content/batch",
                message=f"{success_count}/{len(items)} succeeded, elapsed_sec={data.get('elapsed_sec')}",
                detail={"items": len(items), "success_count": success_count},
            )
        except Exception as exc:
            self.record_step(
                "content_batch",
                False,
                0,
                "POST /api/generator/content/batch",
                message=str(exc),
            )
        return content_map

    def step_notes_single(
        self,
        slide: Dict[str, Any],
        content: str,
        knowledge: str,
    ) -> str:
        self.log("\n[8/8] Speaker notes generation")
        slide_id = slide.get("slideId") or "slide-001"
        slide_title = slide.get("slideTitle") or "测试页"
        body = content.strip() or "页面内容生成失败时的测试占位文本。"
        try:
            data, elapsed = self.client.post_json(
                "/api/generator/notes",
                {
                    "slide_id": slide_id,
                    "slide_title": slide_title,
                    "slide_content": body[:3000],
                    "knowledge_evidence": (knowledge or "")[:6000],
                    "style_requirement": "正式、适合课程汇报，口语化但专业。",
                },
                timeout=self.notes_timeout,
            )
            notes = data.get("notes") or ""
            ok = bool(data.get("success")) and len(notes.strip()) >= 10
            self.record_step(
                "notes_single",
                ok,
                elapsed,
                "POST /api/generator/notes",
                message=truncate(data.get("message") or notes, 120),
                detail={"slide_id": slide_id, "notes_len": len(notes)},
            )
            return notes
        except Exception as exc:
            self.record_step(
                "notes_single",
                False,
                0,
                "POST /api/generator/notes",
                message=str(exc),
            )
            return ""

    def run(self) -> FullGenerationReport:
        started = now_ms()
        self.log("=" * 72)
        self.log("POGCC Full Generation E2E")
        self.log(f"base_url={self.client.base_url}")
        self.log(f"topic={self.topic}")
        self.log("=" * 72)

        outline: Dict[str, Any] = {}
        try:
            self.step_health()
            self.step_model_info()
            outline = self.step_outline()
            slides = flatten_outline_slides(outline)
            targets = pick_content_slides(slides, limit=max(self.knowledge_batch_size, self.content_batch_size, 1))
            primary = targets[0]

            knowledge_primary = ""
            knowledge_map: Dict[str, str] = {}
            if self.with_knowledge:
                knowledge_primary = self.step_knowledge_single(primary)
                if self.with_batch:
                    knowledge_map = self.step_knowledge_batch(targets)
            else:
                self.log("\n[4/8] Single-page knowledge retrieval — skipped (--no-knowledge)")

            content_primary, _ = self.step_content_single(primary, knowledge_primary)
            content_map: Dict[str, str] = {}
            if self.with_batch:
                content_map = self.step_content_batch(targets, knowledge_map)
            else:
                self.log("\n[7/8] Batch content expansion — skipped (use --with-batch)")

            notes_primary = self.step_notes_single(primary, content_primary, knowledge_primary)

            for slide in slides:
                sid = slide.get("slideId") or ""
                snap = SlideSnapshot(
                    slide_id=sid,
                    slide_number=int(slide.get("slideNumber") or 0),
                    slide_role=str(slide.get("slideRole") or ""),
                    section_title=str(slide.get("sectionTitle") or ""),
                    slide_title=str(slide.get("slideTitle") or ""),
                    page_goal=str(slide.get("pageGoal") or ""),
                    key_points=list(slide.get("keyPoints") or []),
                    knowledge_preview=truncate(
                        knowledge_map.get(sid) or (knowledge_primary if sid == primary.get("slideId") else ""),
                        300,
                    ),
                    content_preview=truncate(
                        content_map.get(sid) or (content_primary if sid == primary.get("slideId") else ""),
                        400,
                    ),
                    notes_preview=truncate(notes_primary if sid == primary.get("slideId") else "", 300),
                )
                self.report.slides.append(snap)

            self.report.markdown_preview = build_markdown_preview(
                self.topic,
                outline,
                self.report.slides,
            )

            failed = [s for s in self.report.steps if not s.ok]
            self.report.success = not failed
        except Exception as exc:
            self.report.errors.append(str(exc))
            self.report.success = False
            self.log(f"\n[E2E aborted] {exc}")
            if self.verbose:
                traceback.print_exc()

        self.report.total_elapsed_ms = now_ms() - started
        return self.report


def print_report(report: FullGenerationReport) -> None:
    print("\n" + "=" * 72)
    print("E2E REPORT")
    print("=" * 72)
    print(f"started_at      : {report.started_at}")
    print(f"base_url        : {report.base_url}")
    print(f"topic           : {report.topic}")
    print(f"total_elapsed   : {report.total_elapsed_ms} ms ({report.total_elapsed_ms / 1000:.1f}s)")
    print(f"overall_success : {report.success}")
    if report.outline_summary:
        print(f"outline_title   : {report.outline_summary.get('presentationTitle')}")
        print(f"outline_slides  : {report.outline_summary.get('slideCount')}")
    print("\nSteps:")
    for step in report.steps:
        flag = "OK" if step.ok else "FAIL"
        print(f"  - [{flag}] {step.name:18s} {step.elapsed_ms:6d} ms  {step.endpoint}")
        if step.message:
            print(f"           {truncate(step.message, 100)}")
    if report.errors:
        print("\nErrors:")
        for err in report.errors:
            print(f"  - {err}")
    if report.slides:
        print("\nSlide snapshots (first 3):")
        for snap in report.slides[:3]:
            print(
                f"  - #{snap.slide_number} [{snap.slide_role}] {snap.slide_title} "
                f"| content={len(snap.content_preview)} chars"
            )
    if report.markdown_preview:
        preview = report.markdown_preview[:1200]
        print("\nMarkdown preview (truncated):")
        print("-" * 72)
        print(preview)
        if len(report.markdown_preview) > len(preview):
            print("... (truncated)")
        print("-" * 72)
    print("=" * 72)


def save_report_artifacts(report: FullGenerationReport) -> Tuple[Path, Path]:
    E2E_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    json_path = E2E_OUTPUT_DIR / f"e2e_report_{stamp}.json"
    md_path = E2E_OUTPUT_DIR / f"e2e_report_{stamp}.md"
    save_json(json_path, report.to_dict())
    md_body = textwrap.dedent(
        f"""\
        # POGCC E2E Report

        - started_at: {report.started_at}
        - base_url: {report.base_url}
        - topic: {report.topic}
        - success: {report.success}
        - total_elapsed_ms: {report.total_elapsed_ms}

        ## Steps

        """
    )
    for step in report.steps:
        md_body += f"- [{'x' if step.ok else ' '}] **{step.name}** ({step.elapsed_ms} ms) — {step.message}\n"
    md_body += "\n## Markdown Preview\n\n"
    md_body += report.markdown_preview or "_empty_"
    md_path.write_text(md_body, encoding="utf-8")
    return json_path, md_path


def parse_args(argv: Optional[List[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="POGCC 全流程 E2E（自动拉起/关闭后端）")
    parser.add_argument("--base-url", default=get_base_url(), help="API base URL")
    parser.add_argument("--topic", default=DEFAULT_TOPIC, help="PPT 主题")
    parser.add_argument("--requirements", default=DEFAULT_REQUIREMENTS, help="大纲附加要求")
    parser.add_argument("--context", default=DEFAULT_CONTEXT, help="正文共享上下文")
    parser.add_argument("--outline-timeout", type=int, default=int(os.environ.get("POGCC_E2E_OUTLINE_TIMEOUT", "360")))
    parser.add_argument("--content-timeout", type=int, default=int(os.environ.get("POGCC_E2E_CONTENT_TIMEOUT", "360")))
    parser.add_argument("--notes-timeout", type=int, default=int(os.environ.get("POGCC_E2E_NOTES_TIMEOUT", "180")))
    parser.add_argument("--knowledge-timeout", type=int, default=int(os.environ.get("POGCC_E2E_KNOWLEDGE_TIMEOUT", "300")))
    parser.add_argument("--batch-timeout", type=int, default=int(os.environ.get("POGCC_E2E_BATCH_TIMEOUT", "600")))
    parser.add_argument("--knowledge-batch-size", type=int, default=3)
    parser.add_argument("--content-batch-size", type=int, default=2)
    parser.add_argument("--max-workers", type=int, default=2, help="批量接口并行 worker 数")
    parser.add_argument("--with-batch", action="store_true", help="额外跑 knowledge/content 批量接口")
    parser.add_argument("--no-knowledge", action="store_true", help="跳过检索步骤")
    parser.add_argument("--refine-knowledge", action="store_true", help="检索后走 LLM 整理（更慢）")
    parser.add_argument(
        "--keep-server",
        action="store_true",
        help="若由脚本启动 uvicorn，结束后不关闭（默认会自动关闭）",
    )
    parser.add_argument(
        "--no-auto-server",
        action="store_true",
        help="不自动启动后端；未检测到服务则直接失败",
    )
    parser.add_argument("--quiet", action="store_true", help="减少控制台输出")
    parser.add_argument("--save-report", action="store_true", default=True, help="保存 JSON/Markdown 报告")
    return parser.parse_args(argv)


def run_cli(argv: Optional[List[str]] = None) -> int:
    args = parse_args(argv)
    base_url = args.base_url.rstrip("/")
    managed: Optional[ManagedUvicornServer] = None

    if not is_server_reachable(base_url):
        if args.no_auto_server:
            print(f"[error] server not reachable at {base_url} (--no-auto-server)")
            return 2
        managed = ManagedUvicornServer(base_url=base_url)
        managed.ensure_running()
        if not args.keep_server:
            atexit.register(managed.stop)
    else:
        print(f"[server] using existing backend at {base_url}")

    runner = FullGenerationRunner(
        base_url=base_url,
        topic=args.topic,
        requirements=args.requirements,
        shared_context=args.context,
        outline_timeout=args.outline_timeout,
        content_timeout=args.content_timeout,
        notes_timeout=args.notes_timeout,
        knowledge_timeout=args.knowledge_timeout,
        batch_timeout=args.batch_timeout,
        knowledge_batch_size=args.knowledge_batch_size,
        content_batch_size=args.content_batch_size,
        with_knowledge=not args.no_knowledge,
        with_batch=args.with_batch,
        refine_knowledge=args.refine_knowledge,
        max_workers=args.max_workers,
        verbose=not args.quiet,
    )
    report = runner.run()
    print_report(report)

    if args.save_report:
        json_path, md_path = save_report_artifacts(report)
        print(f"\nReport saved:\n  - {json_path}\n  - {md_path}")

    if managed and not args.keep_server:
        managed.stop()

    return 0 if report.success else 1


# ---------------------------------------------------------------------------
# pytest entry points
# ---------------------------------------------------------------------------

def require_server_or_skip(base_url: Optional[str] = None) -> str:
    url = (base_url or get_base_url()).rstrip("/")
    if not is_server_reachable(url):
        msg = (
            f"POGCC server is not reachable at {url}. "
            "Run `python tests/new/e2e/test_full_generation.py` to auto-start, "
            "or start uvicorn manually."
        )
        if pytest:
            pytest.skip(msg)
        raise RuntimeError(msg)
    return url


def test_outline_content_notes_endpoint_chain():
    """Minimal pytest chain: outline -> content -> notes (reuse existing server)."""
    base_url = require_server_or_skip()
    runner = FullGenerationRunner(
        base_url=base_url,
        with_knowledge=False,
        with_batch=False,
        verbose=False,
    )
    report = runner.run()
    assert report.success, report.errors or "E2E chain failed"
    assert report.outline_summary.get("slideCount", 0) >= 1
    notes_step = next((s for s in report.steps if s.name == "notes_single"), None)
    assert notes_step and notes_step.ok


def test_full_chain_with_knowledge_when_server_available():
    """Extended pytest chain including single-page knowledge retrieval."""
    base_url = require_server_or_skip()
    runner = FullGenerationRunner(
        base_url=base_url,
        with_knowledge=True,
        with_batch=False,
        verbose=False,
        outline_timeout=360,
        knowledge_timeout=300,
    )
    report = runner.run()
    assert any(s.name == "knowledge_single" for s in report.steps)
    if report.errors and "knowledge_single" in " ".join(report.errors):
        if pytest:
            pytest.skip(f"knowledge retrieval unavailable or failed: {report.errors}")
        return
    assert report.success, report.errors


def test_future_full_generation_endpoint_if_available():
    """Optional test for POST /api/project/generate (skip if 404)."""
    base_url = require_server_or_skip()
    resp = requests.post(
        f"{base_url}/api/project/generate",
        json={
            "topic": DEFAULT_TOPIC,
            "scenario": "课程项目汇报",
            "audience": "老师和同学",
            "page_count": 8,
            "duration": "5-10分钟",
            "style": "学术正式",
            "depth": "standard",
            "source_mode": "input_only",
            "output_format": "json",
            "constraints": "需要包含证据和演讲备注",
        },
        timeout=240,
    )
    if resp.status_code == 404:
        if pytest:
            pytest.skip("/api/project/generate has not been implemented yet.")
        return
    assert resp.status_code == 200, resp.text[:1000]
    data = resp.json()
    assert data.get("success") is True
    payload = data.get("draft") or data.get("result") or data
    assert payload
    assert "slides" in str(payload) or "outline" in str(payload)


if __name__ == "__main__":
    raise SystemExit(run_cli())
