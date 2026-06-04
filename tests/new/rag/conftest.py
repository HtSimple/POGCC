from __future__ import annotations

import sys
from datetime import datetime
from pathlib import Path

import pytest

CURRENT = Path(__file__).resolve()
RAG_DIR = CURRENT.parent
FIXTURES_DIR = RAG_DIR / "fixtures"
TESTING_DIR = RAG_DIR.parent
OUTPUT_DIR = RAG_DIR / "outputs"

if str(TESTING_DIR) not in sys.path:
    sys.path.insert(0, str(TESTING_DIR))

from _test_utils import add_project_root_to_path, find_project_root, load_json, save_json  # noqa: E402
from rag_metrics import format_summary_lines, get_rag_quality_summary  # noqa: E402

PROJECT_ROOT = find_project_root(CURRENT)
add_project_root_to_path(CURRENT)

CORPUS_PATH = FIXTURES_DIR / "rag_corpus.txt"
QUERIES_PATH = FIXTURES_DIR / "rag_queries.json"


def embedding_model_path() -> str:
    from app.utils.config import config

    model = config.get("rag_embedding_model") or "app/rag/bge-small-en-v1.5"
    path = Path(model)
    root = find_project_root(CURRENT)
    return str(path if path.is_absolute() else (root / path).resolve())


@pytest.fixture(scope="module")
def sentence_transformers_available():
    pytest.importorskip("sentence_transformers")


@pytest.fixture
def rag_service(tmp_path: Path, sentence_transformers_available):
    from app.rag.service import RetrievalService

    try:
        service = RetrievalService(
            persist_dir=str(tmp_path / "index"),
            embedding_model=embedding_model_path(),
        )
    except Exception as exc:
        pytest.skip(f"RetrievalService cannot start: {exc}")
    return service


@pytest.fixture(scope="module")
def ingested_corpus_module(tmp_path_factory, sentence_transformers_available):
    from app.rag.service import RetrievalService

    base = tmp_path_factory.mktemp("rag_quality")
    try:
        service = RetrievalService(
            persist_dir=str(base / "index"),
            embedding_model=embedding_model_path(),
        )
    except Exception as exc:
        pytest.skip(f"RetrievalService cannot start: {exc}")

    assert CORPUS_PATH.is_file(), f"Missing fixture corpus: {CORPUS_PATH}"
    report = service.ingest(str(CORPUS_PATH.resolve()))
    assert report.status in {"success", "skipped"}
    assert report.num_chunks >= 1
    service._ingest_report = report  # noqa: SLF001 — test-only metadata
    return service


@pytest.fixture
def ingested_corpus(ingested_corpus_module):
    """Reuse module-level corpus index for content-quality tests."""
    return ingested_corpus_module


@pytest.fixture(scope="module")
def rag_query_cases():
    assert QUERIES_PATH.is_file(), f"Missing fixture queries: {QUERIES_PATH}"
    return load_json(QUERIES_PATH)


def pytest_terminal_summary(terminalreporter, exitstatus, config) -> None:
    summary = get_rag_quality_summary()
    if summary is None:
        return

    terminalreporter.write_sep("=", "RAG 检索质量报告")
    for line in format_summary_lines(summary):
        terminalreporter.write_line(line)

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    json_path = OUTPUT_DIR / f"rag_quality_metrics_{stamp}.json"
    save_json(json_path, summary.to_dict())
    terminalreporter.write_line("")
    terminalreporter.write_line(f"报告已保存: {json_path}")
