from __future__ import annotations

import json
from pathlib import Path
from typing import Iterable, List, Optional

import numpy as np

from .schemas import RetrievalResult, TextChunk

try:
    from sentence_transformers import SentenceTransformer
except Exception:  # pragma: no cover
    SentenceTransformer = None


class VectorIndex:
    """
    Lightweight local vector index.
    - Embeds chunks with sentence-transformers.
    - Persists chunk metadata and embeddings to disk.
    - Supports cosine-similarity retrieval.
    """

    def __init__(
        self,
        persist_dir: str,
        model_name: str = "app/rag/bge-small-en-v1.5",
        normalize_embeddings: bool = True,
    ) -> None:
        self.persist_dir = Path(persist_dir)
        self.persist_dir.mkdir(parents=True, exist_ok=True)
        self.model_name = model_name
        self.normalize_embeddings = normalize_embeddings
        self.meta_path = self.persist_dir / "chunks.jsonl"
        self.emb_path = self.persist_dir / "embeddings.npy"

        self._model: Optional[SentenceTransformer] = None
        self._chunks: List[TextChunk] = []
        self._embeddings: Optional[np.ndarray] = None
        self._load_if_exists()

    @property
    def model(self) -> SentenceTransformer:
        if self._model is None:
            if SentenceTransformer is None:
                raise ImportError(
                    "sentence-transformers is required. Please install: pip install sentence-transformers"
                )
            self._model = SentenceTransformer(self.model_name)
        return self._model

    @property
    def size(self) -> int:
        return len(self._chunks)

    def add_chunks(self, chunks: List[TextChunk]) -> int:
        if not chunks:
            return 0

        new_chunks = [c for c in chunks if c.chunk_id not in {x.chunk_id for x in self._chunks}]
        if not new_chunks:
            return 0

        texts = [self._prepare_text(c.text) for c in new_chunks]
        new_embs = self.model.encode(
            texts,
            convert_to_numpy=True,
            normalize_embeddings=self.normalize_embeddings,
            show_progress_bar=False,
        )
        new_embs = np.asarray(new_embs, dtype=np.float32)

        if self._embeddings is None:
            self._embeddings = new_embs
        else:
            self._embeddings = np.vstack([self._embeddings, new_embs]).astype(np.float32)

        self._chunks.extend(new_chunks)
        self._persist_all()
        return len(new_chunks)

    def search(self, query: str, top_k: int = 5, doc_id: Optional[str] = None) -> List[RetrievalResult]:
        if not query.strip():
            raise ValueError("Query must not be empty.")
        if self._embeddings is None or not self._chunks:
            return []

        indices = list(range(len(self._chunks)))
        if doc_id is not None:
            indices = [i for i, c in enumerate(self._chunks) if c.doc_id == doc_id]
            if not indices:
                return []

        query_vec = self.model.encode(
            [self._prepare_text(query)],
            convert_to_numpy=True,
            normalize_embeddings=self.normalize_embeddings,
            show_progress_bar=False,
        )[0]
        query_vec = np.asarray(query_vec, dtype=np.float32)

        mat = self._embeddings[indices]
        scores = mat @ query_vec
        order = np.argsort(-scores)[: max(1, top_k)]

        results: List[RetrievalResult] = []
        for idx in order:
            chunk = self._chunks[indices[idx]]
            score = float(scores[idx])
            results.append(
                RetrievalResult(
                    chunk_id=chunk.chunk_id,
                    doc_id=chunk.doc_id,
                    text=chunk.text,
                    score=score,
                    source_file=chunk.source_file,
                    chunk_index=chunk.chunk_index,
                    section_title=chunk.section_title,
                    start_page=chunk.start_page,
                    end_page=chunk.end_page,
                    pages=chunk.pages,
                    metadata=chunk.metadata,
                )
            )
        return results

    def delete_doc(self, doc_id: str) -> int:
        if not self._chunks:
            return 0
        keep_indices = [i for i, c in enumerate(self._chunks) if c.doc_id != doc_id]
        removed = len(self._chunks) - len(keep_indices)
        if removed == 0:
            return 0

        self._chunks = [self._chunks[i] for i in keep_indices]
        if self._embeddings is not None:
            self._embeddings = self._embeddings[keep_indices] if keep_indices else None
        self._persist_all()
        return removed

    def list_docs(self) -> List[dict]:
        docs = {}
        for c in self._chunks:
            docs.setdefault(
                c.doc_id,
                {
                    "doc_id": c.doc_id,
                    "source_file": c.source_file,
                    "num_chunks": 0,
                },
            )
            docs[c.doc_id]["num_chunks"] += 1
        return list(docs.values())

    def _prepare_text(self, text: str) -> str:
        return text.strip().replace("\n", " ")

    def _persist_all(self) -> None:
        with self.meta_path.open("w", encoding="utf-8") as f:
            for chunk in self._chunks:
                f.write(json.dumps(chunk.to_dict(), ensure_ascii=False) + "\n")

        if self._embeddings is None or len(self._chunks) == 0:
            if self.emb_path.exists():
                self.emb_path.unlink()
        else:
            np.save(self.emb_path, self._embeddings)

    def _load_if_exists(self) -> None:
        if self.meta_path.exists():
            with self.meta_path.open("r", encoding="utf-8") as f:
                self._chunks = [TextChunk.from_dict(json.loads(line)) for line in f if line.strip()]
        if self.emb_path.exists():
            self._embeddings = np.load(self.emb_path)
            if self._embeddings.ndim == 1:
                self._embeddings = self._embeddings.reshape(1, -1)
        if self._embeddings is not None and len(self._chunks) != len(self._embeddings):
            raise RuntimeError(
                "Vector index corrupted: number of chunks does not match number of embeddings."
            )
