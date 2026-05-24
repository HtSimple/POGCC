from __future__ import annotations

import json
import os
import re
import socket
import sys
import time
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional
from urllib.parse import urlparse


def find_project_root(start_path: Optional[str | Path] = None) -> Path:
    """Find repository root by walking upward until app/ and main.py exist."""
    current = Path(start_path or __file__).resolve()
    if current.is_file():
        current = current.parent
    while True:
        if (current / "app").is_dir() and (current / "main.py").exists():
            return current
        if current.parent == current:
            return Path(start_path or ".").resolve()
        current = current.parent


def add_project_root_to_path(start_path: Optional[str | Path] = None) -> Path:
    root = find_project_root(start_path)
    root_str = str(root)
    if root_str not in sys.path:
        sys.path.insert(0, root_str)
    return root


def load_json(path: str | Path) -> Any:
    path = Path(path)
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def save_json(path: str | Path, data: Any) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def flatten_outline_slides(outline: Dict[str, Any]) -> List[Dict[str, Any]]:
    slides: List[Dict[str, Any]] = []
    for section in outline.get("sections", []) or []:
        for slide in section.get("slides", []) or []:
            item = dict(slide)
            item.setdefault("sectionId", section.get("sectionId"))
            item.setdefault("sectionTitle", section.get("sectionTitle"))
            slides.append(item)
    return slides


def normalize_text(text: Any) -> str:
    return re.sub(r"\s+", " ", str(text or "")).strip().lower()


def contains_any(text: str, words: Iterable[str]) -> bool:
    text_norm = normalize_text(text)
    return any(normalize_text(w) in text_norm for w in words if str(w).strip())


def rough_tokens(text: str) -> List[str]:
    """
    Lightweight tokenizer for Chinese/English without extra dependencies.
    Chinese chars are individual tokens; English words/numbers are grouped.
    """
    text = str(text or "")
    return re.findall(r"[\u4e00-\u9fff]|[a-zA-Z0-9]+(?:\.[a-zA-Z0-9]+)?", text.lower())


def jaccard_similarity(a: str, b: str) -> float:
    ta, tb = set(rough_tokens(a)), set(rough_tokens(b))
    if not ta or not tb:
        return 0.0
    return len(ta & tb) / max(1, len(ta | tb))


def split_claims(text: str) -> List[str]:
    """
    Extract rough verifiable claims from generated content.
    This is intentionally conservative: it favors sentences with numbers,
    years, named entities, causal/comparative wording, or clear conclusions.
    """
    if not text:
        return []
    pieces = re.split(r"[。！？!?；;\n]+", str(text))
    claims = []
    keywords = [
        "提升", "降低", "增长", "减少", "超过", "达到", "高于", "低于", "导致",
        "因为", "因此", "表明", "证明", "支持", "风险", "趋势", "核心", "主要",
        "increase", "decrease", "improve", "reduce", "because", "therefore",
        "shows", "indicates", "risk", "trend", "main", "key",
    ]
    for p in pieces:
        s = p.strip(" -•\t\r")
        if len(s) < 8:
            continue
        has_num = bool(re.search(r"\d+(\.\d+)?\s*(%|年|月|倍|万|亿|percent|million|billion)?", s))
        has_kw = any(k.lower() in s.lower() for k in keywords)
        # Keep some normal long sentences as potential claims too.
        if has_num or has_kw or len(s) >= 25:
            claims.append(s)
    # de-duplicate, keep order
    seen, unique = set(), []
    for c in claims:
        key = normalize_text(c)
        if key not in seen:
            seen.add(key)
            unique.append(c)
    return unique


def evidence_texts_from_record(record: Dict[str, Any]) -> List[str]:
    texts: List[str] = []
    for r in record.get("search_results", []) or []:
        texts.append(" ".join(str(r.get(k, "")) for k in ("title", "content", "snippet", "url")))
    for ev in record.get("evidence", []) or []:
        if isinstance(ev, dict):
            texts.append(" ".join(str(ev.get(k, "")) for k in ("claim", "sourceTitle", "quote", "content", "text", "url")))
        else:
            texts.append(str(ev))
    # page_content protocol
    for slide in (record.get("page_content", {}) or {}).get("slides", []) or []:
        for ev in slide.get("evidencePack", []) or []:
            texts.append(" ".join(str(ev.get(k, "")) for k in ("claim", "sourceTitle", "quote", "url")))
    return [t for t in texts if t.strip()]


def classify_claim_by_evidence(claim: str, evidence_texts: List[str], threshold: float = 0.18) -> Dict[str, Any]:
    """
    Simple non-LLM claim-evidence matcher.
    It is not a replacement for human/RAGAS judgment; it gives a repeatable
    automatic baseline for regression testing.
    """
    best_score = 0.0
    best_evidence = ""
    for ev in evidence_texts:
        score = jaccard_similarity(claim, ev)
        if score > best_score:
            best_score = score
            best_evidence = ev[:500]
    if not evidence_texts:
        status = "no_evidence"
    elif best_score >= threshold:
        status = "supported"
    elif best_score >= threshold * 0.55:
        status = "insufficient"
    else:
        status = "no_evidence"
    return {
        "claim": claim,
        "status": status,
        "similarity": round(best_score, 4),
        "matched_evidence": best_evidence,
    }


def domain_from_url(url: str) -> str:
    try:
        return urlparse(url or "").netloc.lower().replace("www.", "")
    except Exception:
        return ""


AUTHORITY_SUFFIXES = (".gov", ".edu", ".ac.", ".org")
AUTHORITY_KEYWORDS = (
    "who.int", "worldbank.org", "oecd.org", "un.org", "nature.com",
    "science.org", "springer", "ieee", "acm.org", "arxiv.org", "stats.gov",
    "gov.cn", "edu.cn", "europa.eu", "imf.org", "mckinsey.com", "gartner.com",
)


def authority_domain_score(domain: str) -> float:
    d = (domain or "").lower()
    if not d:
        return 0.0
    if d.endswith(AUTHORITY_SUFFIXES):
        return 1.0
    if any(k in d for k in AUTHORITY_KEYWORDS):
        return 1.0
    if any(k in d for k in ("news", "reuters", "bbc", "cnn", "bloomberg", "caixin", "people")):
        return 0.7
    return 0.35


def score_0_to_5(value_0_to_1: float) -> float:
    return round(max(0.0, min(1.0, value_0_to_1)) * 5.0, 2)


def count_information_units(text: str) -> int:
    """
    Estimate information density by counting bullets, numeric facts,
    evidence-like citations, and substantive sentences.
    """
    text = str(text or "")
    bullets = len(re.findall(r"(^|\n)\s*[-*•\d]+[.)、]?\s+", text))
    numeric_facts = len(re.findall(r"\d+(\.\d+)?\s*(%|年|月|倍|万|亿|million|billion|percent)?", text, flags=re.I))
    sentences = [s for s in re.split(r"[。！？!?;\n]+", text) if len(s.strip()) >= 12]
    evidence_markers = len(re.findall(r"(来源|参考|http|www\.|doi|报告|论文|白皮书|research|report|source)", text, flags=re.I))
    return max(len(sentences), 0) + bullets + numeric_facts + evidence_markers


def is_server_reachable(base_url: str, timeout: float = 1.5) -> bool:
    try:
        parsed = urlparse(base_url)
        host = parsed.hostname or "127.0.0.1"
        port = parsed.port or (443 if parsed.scheme == "https" else 80)
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except OSError:
        return False


def get_base_url() -> str:
    return os.environ.get("POGCC_BASE_URL", "http://127.0.0.1:8000").rstrip("/")


def get_health_url(base_url: Optional[str] = None) -> str:
    return f"{(base_url or get_base_url()).rstrip('/')}/health"


def wait_for_http_ready(
    base_url: Optional[str] = None,
    timeout_sec: float = 90.0,
    poll_interval: float = 0.8,
) -> bool:
    """Poll /health until the API responds with HTTP 200."""
    import requests

    deadline = time.time() + timeout_sec
    health_url = get_health_url(base_url)
    last_error = ""
    while time.time() < deadline:
        try:
            resp = requests.get(health_url, timeout=3)
            if resp.status_code == 200:
                return True
            last_error = f"HTTP {resp.status_code}"
        except requests.RequestException as exc:
            last_error = str(exc)
        time.sleep(poll_interval)
    print(f"[server] wait timeout ({timeout_sec}s): {health_url} last_error={last_error}")
    return False


class ManagedUvicornServer:
    """
    Start uvicorn as a child process when no server is listening.
    Only stops the process if this helper started it.
    """

    def __init__(
        self,
        base_url: Optional[str] = None,
        host: str = "127.0.0.1",
        port: Optional[int] = None,
        startup_timeout_sec: float = 90.0,
    ) -> None:
        parsed = urlparse(base_url or get_base_url())
        self.base_url = (base_url or get_base_url()).rstrip("/")
        self.host = parsed.hostname or host
        self.port = port or parsed.port or (443 if parsed.scheme == "https" else 80)
        self.startup_timeout_sec = startup_timeout_sec
        self.project_root = find_project_root()
        self._proc: Any = None
        self.started_by_us = False

    def ensure_running(self) -> None:
        if is_server_reachable(self.base_url):
            print(f"[server] reuse existing backend: {self.base_url}")
            return
        print(f"[server] starting uvicorn on {self.host}:{self.port} ...")
        import subprocess

        cmd = [
            sys.executable,
            "-m",
            "uvicorn",
            "main:app",
            "--host",
            self.host,
            "--port",
            str(self.port),
        ]
        self._proc = subprocess.Popen(
            cmd,
            cwd=str(self.project_root),
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
        self.started_by_us = True
        if not wait_for_http_ready(self.base_url, timeout_sec=self.startup_timeout_sec):
            self.stop()
            raise RuntimeError(
                f"Failed to start backend at {self.base_url} within {self.startup_timeout_sec}s"
            )
        print(f"[server] backend ready: {self.base_url}")

    def stop(self) -> None:
        if not self.started_by_us or self._proc is None:
            return
        print("[server] stopping managed uvicorn process ...")
        self._proc.terminate()
        try:
            self._proc.wait(timeout=15)
        except Exception:
            self._proc.kill()
        self._proc = None
        self.started_by_us = False
        print("[server] stopped")


def build_knowledge_query(
    topic: str,
    section_title: str,
    slide_title: str,
    bullets: Optional[List[str]] = None,
) -> str:
    """Same query shape as frontend App.vue fillKnowledge."""
    lines = [topic, section_title, slide_title, *(bullets or [])]
    return "\n".join(line for line in lines if str(line).strip())


def outline_node_from_slide(slide: Dict[str, Any]) -> Dict[str, Any]:
    """Map narrative outline slide to /api/generator/content outline_node."""
    bullets = slide.get("keyPoints") or slide.get("bullets") or []
    return {
        "id": slide.get("slideId") or slide.get("id"),
        "number": slide.get("slideNumber") or 1,
        "role": slide.get("slideRole") or "content",
        "title": slide.get("slideTitle") or slide.get("title") or "未命名页面",
        "section": slide.get("sectionTitle") or slide.get("section") or "",
        "goal": slide.get("pageGoal") or slide.get("goal") or slide.get("sectionObjective") or "",
        "bullets": bullets,
    }


def page_content_to_plain_text(page_content: Optional[Dict[str, Any]]) -> str:
    if not page_content:
        return ""
    slides = page_content.get("slides") or []
    if not slides:
        return ""
    slide = slides[0]
    lines = [str(slide.get("coreMessage") or "").strip()]
    for item in slide.get("displayBullets") or []:
        text = str(item).strip()
        if text:
            lines.append(f"- {text}")
    takeaway = str(slide.get("actionableTakeaway") or "").strip()
    if takeaway:
        lines.append(takeaway)
    return "\n".join(x for x in lines if x)


def now_ms() -> int:
    return int(time.time() * 1000)
