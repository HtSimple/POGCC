from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path
from typing import Any, Dict, List

import requests

SCRIPT_PATH = Path(__file__).resolve()
PROJECT_ROOT = SCRIPT_PATH.parents[3]
TECH_REPORT_ROOT = PROJECT_ROOT / "testing" / "tech_validation_report"
SCENARIOS_PATH = TECH_REPORT_ROOT / "scenarios.json"
OUTPUT_ROOT = TECH_REPORT_ROOT / "outputs"

sys.path.insert(0, str(PROJECT_ROOT))

from tests.new._test_utils import (  # noqa: E402
    ManagedUvicornServer,
    build_knowledge_query,
    flatten_outline_slides,
    outline_node_from_slide,
    page_content_to_plain_text,
    save_json,
    get_base_url,
)


def now_ms() -> int:
    return int(time.time() * 1000)


def clip_text(text: str, limit: int = 5800) -> str:
    value = str(text or "").strip()
    if len(value) <= limit:
        return value
    return value[:limit].rstrip() + "..."


def request_json(method: str, base_url: str, path: str, payload: dict | None = None, timeout: int = 300) -> dict:
    url = f"{base_url.rstrip('/')}{path}"
    if method == "GET":
        resp = requests.get(url, timeout=timeout)
    else:
        resp = requests.post(url, json=payload or {}, timeout=timeout)
    if resp.status_code != 200:
        raise RuntimeError(f"{method} {path} -> HTTP {resp.status_code}: {resp.text[:800]}")
    return resp.json()


def load_scenarios() -> List[Dict[str, Any]]:
    with SCENARIOS_PATH.open("r", encoding="utf-8") as f:
        data = json.load(f)
    return data.get("scenarios", [])


def resolve_doc_path(doc_ref: str) -> Path:
    return (TECH_REPORT_ROOT / doc_ref).resolve()


def ensure_output_dir(scenario_id: str) -> Path:
    path = OUTPUT_ROOT / scenario_id / "deepseek" / "rag_search"
    path.mkdir(parents=True, exist_ok=True)
    return path


def switch_model(base_url: str, provider: str) -> dict:
    return request_json("POST", base_url, "/api/model/switch", {"provider": provider}, timeout=60)


def upload_documents(base_url: str, documents: List[str]) -> List[dict]:
    reports: List[dict] = []
    for doc in documents:
        doc_path = resolve_doc_path(doc)
        if not doc_path.exists():
            raise FileNotFoundError(f"Document not found: {doc_path}")
        payload = {"file_path": str(doc_path)}
        resp = request_json("POST", base_url, "/api/rag/upload", payload, timeout=180)
        reports.append({"file": str(doc_path), "response": resp})
        if not resp.get("success"):
            raise RuntimeError(f"RAG upload failed for {doc_path}: {resp.get('message')}")
    return reports


def build_markdown(outline: dict, content_results: List[dict]) -> str:
    slide_map: dict[str, dict] = {}
    for item in content_results:
        page_content = item.get("page_content") or {}
        slides = page_content.get("slides") or []
        if slides:
            slide_map[slides[0].get("slideId") or ""] = slides[0]

    lines: List[str] = []
    lines.append(f"# {outline.get('presentationTitle') or 'PPT'}")
    lines.append("")

    for section in outline.get("sections") or []:
        section_title = section.get("sectionTitle") or "未命名章节"
        lines.append(f"## {section_title}")
        lines.append("")
        for slide in section.get("slides") or []:
            slide_id = slide.get("slideId") or ""
            slide_title = slide.get("slideTitle") or "未命名页面"
            slide_number = slide.get("slideNumber") or "?"
            lines.append(f"### 第 {slide_number} 页 · {slide_title}")
            for kp in slide.get("keyPoints") or []:
                lines.append(f"- {kp}")
            page = slide_map.get(slide_id) or {}
            core = page.get("coreMessage")
            if core:
                lines.append("")
                lines.append("**正文**")
                lines.append(core)
            bullets = page.get("displayBullets") or []
            if bullets:
                for bp in bullets:
                    lines.append(f"- {bp}")
            notes = page.get("speakerNotes")
            if notes:
                lines.append("")
                lines.append("**演讲备注**")
                lines.append(notes)
            lines.append("")
    return "\n".join(lines).strip() + "\n"


def run_scenario(base_url: str, scenario: Dict[str, Any], refine_knowledge: bool, max_workers: int) -> dict:
    scenario_id = scenario.get("id") or "unknown"
    output_dir = ensure_output_dir(scenario_id)

    summary: Dict[str, Any] = {
        "scenario_id": scenario_id,
        "topic": scenario.get("topic"),
        "requirements": scenario.get("requirements"),
        "slides": scenario.get("slides"),
        "documents": scenario.get("documents", []),
        "model": "deepseek",
        "mode": "rag_search",
        "refine_knowledge": refine_knowledge,
        "success": False,
        "timing_ms": {},
        "errors": [],
    }

    start = now_ms()

    try:
        # Clear RAG index from previous scenario to avoid cross-contamination
        t0 = now_ms()
        request_json("POST", base_url, "/api/rag/clear", {}, timeout=60)
        summary["timing_ms"]["clear_rag"] = now_ms() - t0

        docs = scenario.get("documents") or []
        if docs:
            t0 = now_ms()
            upload_reports = upload_documents(base_url, docs)
            summary["timing_ms"]["upload_documents"] = now_ms() - t0
            save_json(output_dir / "upload_reports.json", upload_reports)

        t0 = now_ms()
        outline_resp = request_json(
            "POST",
            base_url,
            "/api/generator/outline",
            {"topic": scenario.get("topic", ""), "requirements": scenario.get("requirements", "")},
            timeout=360,
        )
        summary["timing_ms"]["outline"] = now_ms() - t0
        save_json(output_dir / "outline.json", outline_resp)

        outline = outline_resp.get("outline") or {}
        slides = flatten_outline_slides(outline)

        items = []
        for idx, slide in enumerate(slides):
            query = build_knowledge_query(
                scenario.get("topic", ""),
                slide.get("sectionTitle") or "",
                slide.get("slideTitle") or "",
                slide.get("keyPoints") or [],
            )
            items.append({"index": idx, "id": slide.get("slideId"), "query": query})

        t0 = now_ms()
        knowledge_resp = request_json(
            "POST",
            base_url,
            "/api/search/knowledge/batch",
            {"items": items, "refine_knowledge": refine_knowledge, "max_workers": max_workers},
            timeout=600,
        )
        summary["timing_ms"]["knowledge_batch"] = now_ms() - t0
        save_json(output_dir / "knowledge.json", knowledge_resp)

        knowledge_by_index = {r["index"]: r for r in knowledge_resp.get("results", [])}

        content_items = []
        for idx, slide in enumerate(slides):
            node = outline_node_from_slide(slide)
            knowledge = knowledge_by_index.get(idx, {}).get("knowledge", "")
            content_items.append({
                "index": idx,
                "id": slide.get("slideId"),
                "outline_node": node,
                "context": knowledge,
            })

        t0 = now_ms()
        content_resp = request_json(
            "POST",
            base_url,
            "/api/generator/content/batch",
            {"items": content_items, "max_workers": max_workers},
            timeout=600,
        )
        summary["timing_ms"]["content_batch"] = now_ms() - t0
        save_json(output_dir / "content.json", content_resp)

        notes_results = []
        for idx, slide in enumerate(slides):
            content_item = next((c for c in content_resp.get("results", []) if c.get("index") == idx), {})
            page_content = content_item.get("page_content")
            slide_text = content_item.get("content") or page_content_to_plain_text(page_content)
            slide_text = clip_text(slide_text, limit=2800)
            knowledge = knowledge_by_index.get(idx, {}).get("knowledge", "")
            payload = {
                "project_id": scenario_id,
                "slide_id": slide.get("slideId"),
                "slide_title": slide.get("slideTitle"),
                "slide_content": slide_text or "无正文",
                "knowledge_evidence": clip_text(knowledge, limit=3000),
                "style_requirement": "口语化、清晰、适合课堂或汇报场景",
            }
            t0 = now_ms()
            try:
                notes_resp = request_json(
                    "POST",
                    base_url,
                    "/api/generator/notes",
                    payload,
                    timeout=240,
                )
                notes_results.append({
                    "index": idx,
                    "slide_id": slide.get("slideId"),
                    "response": notes_resp,
                    "elapsed_ms": now_ms() - t0,
                })
            except Exception as exc:
                notes_results.append({
                    "index": idx,
                    "slide_id": slide.get("slideId"),
                    "error": str(exc),
                    "elapsed_ms": now_ms() - t0,
                })

        save_json(output_dir / "notes.json", notes_results)

        markdown = build_markdown(outline, content_resp.get("results", []))
        (output_dir / "markdown_preview.md").write_text(markdown, encoding="utf-8")

        summary["success"] = True
        summary["timing_ms"]["total"] = now_ms() - start
        save_json(output_dir / "summary.json", summary)
        return summary
    except Exception as exc:
        summary["errors"].append(str(exc))
        summary["timing_ms"]["total"] = now_ms() - start
        save_json(output_dir / "summary.json", summary)
        raise


def main() -> int:
    parser = argparse.ArgumentParser(description="Run DeepSeek with RAG and search for all scenarios")
    parser.add_argument("--base-url", default=get_base_url())
    parser.add_argument("--refine-knowledge", action="store_true", help="Enable deep knowledge refinement")
    parser.add_argument("--max-workers", type=int, default=3)
    args = parser.parse_args()

    server = ManagedUvicornServer(base_url=args.base_url)
    server.ensure_running()

    switch_model(args.base_url, "deepseek")

    scenarios = load_scenarios()
    if not scenarios:
        raise RuntimeError("No scenarios found")

    failures = 0
    for scenario in scenarios:
        scenario_id = scenario.get("id")
        print(f"\n=== Running {scenario_id} ===")
        try:
            run_scenario(args.base_url, scenario, args.refine_knowledge, args.max_workers)
        except Exception as exc:
            failures += 1
            print(f"[ERROR] {scenario_id}: {exc}")

    if failures:
        print(f"Completed with failures: {failures}/{len(scenarios)}")
        return 1

    print("All scenarios completed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
