from __future__ import annotations

from dataclasses import dataclass, field, asdict
from typing import Any, Dict, List, Optional


@dataclass
class RawDocument:
    """A fully parsed source document."""

    doc_id: str
    file_name: str
    file_type: str
    text: str
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class TextChunk:
    chunk_id: str
    doc_id: str
    text: str
    chunk_index: int
    source_file: str
    section_title: Optional[str] = None
    start_page: Optional[int] = None
    end_page: Optional[int] = None
    pages: List[int] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "TextChunk":
        return cls(**data)


@dataclass
class RetrievalResult:
    chunk_id: str
    doc_id: str
    text: str
    score: float
    source_file: str
    chunk_index: int
    section_title: Optional[str] = None
    start_page: Optional[int] = None
    end_page: Optional[int] = None
    pages: List[int] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class IngestReport:
    """Outcome summary for a single ingestion job."""

    doc_id: str
    file_name: str
    num_chunks: int
    status: str
    message: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class SearchResponse:
    """Top-k retrieval results for a query."""

    query: str
    top_k: int
    results: List[RetrievalResult] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "query": self.query,
            "top_k": self.top_k,
            "results": [r.to_dict() for r in self.results],
        }
