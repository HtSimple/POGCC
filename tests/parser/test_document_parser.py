from __future__ import annotations

import sys
from pathlib import Path

import pytest

CURRENT = Path(__file__).resolve()
TESTING_DIR = CURRENT.parents[1]
if str(TESTING_DIR) not in sys.path:
    sys.path.insert(0, str(TESTING_DIR))

from _test_utils import add_project_root_to_path

ROOT = add_project_root_to_path(CURRENT)


@pytest.fixture()
def tmp_txt_file(tmp_path: Path) -> Path:
    p = tmp_path / "sample.txt"
    p.write_text(
        "PPT大纲智能生成与内容补全系统\n"
        "本系统通过结构化Schema、RAG检索和演讲备注生成提升PPT内容质量。\n",
        encoding="utf-8",
    )
    return p


def test_rag_document_processor_txt(tmp_txt_file: Path):
    from app.rag.document_processor import DocumentProcessor

    processor = DocumentProcessor()
    document, chunks = processor.process_file(str(tmp_txt_file))
    assert document.file_name == "sample.txt"
    assert chunks
    assert any("RAG" in chunk.text or "检索" in chunk.text for chunk in chunks)


def test_rag_document_processor_rejects_missing_file(tmp_path: Path):
    from app.rag.document_processor import DocumentProcessor

    processor = DocumentProcessor()
    with pytest.raises(Exception):
        processor.process_file(str(tmp_path / "missing.txt"))


def test_legacy_document_parser_if_available(tmp_txt_file: Path):
    """
    The repository has a legacy app/core/document_parser.py in some versions.
    This test keeps compatibility, but does not require that module.
    """
    try:
        from app.core.document_parser import DocumentParser
    except Exception:
        pytest.skip("legacy DocumentParser is not available")

    parser = DocumentParser()
    text = parser.parse(str(tmp_txt_file))
    assert "PPT" in text
