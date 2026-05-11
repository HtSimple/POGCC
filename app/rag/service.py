from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Dict, List, Optional

from .document_processor import DocumentProcessor, ProcessorConfig
from .schemas import IngestReport, SearchResponse
from .vector_index import VectorIndex


class RetrievalService:
    """
    持续可用的本地知识库服务：
    - 支持分多次上传文件
    - 已入库文件不会重复入库
    - 同一路径文件内容变化时，自动替换旧版本
    - 查询时直接查历史知识库
    """

    def __init__(
        self,
        persist_dir: str,
        embedding_model: str = "app/rag/bge-small-en-v1.5",
        processor_config: Optional[ProcessorConfig] = None,
    ) -> None:
        self.persist_dir = Path(persist_dir)
        self.persist_dir.mkdir(parents=True, exist_ok=True)

        self.processor = DocumentProcessor(processor_config)
        self.index = VectorIndex(
            persist_dir=str(self.persist_dir),
            model_name=embedding_model,
        )

        self.manifest_path = self.persist_dir / "manifest.json"
        self._manifest: List[Dict] = self._load_manifest()

    # =========================
    # manifest
    # =========================
    def _load_manifest(self) -> List[Dict]:
        if self.manifest_path.exists():
            with self.manifest_path.open("r", encoding="utf-8") as f:
                data = json.load(f)
            if isinstance(data, list):
                return data
        return []

    def _save_manifest(self) -> None:
        with self.manifest_path.open("w", encoding="utf-8") as f:
            json.dump(self._manifest, f, ensure_ascii=False, indent=2)

    # =========================
    # utils
    # =========================
    def _normalize_path(self, file_path: str) -> str:
        return str(Path(file_path).resolve())

    def _calc_file_hash(self, file_path: str) -> str:
        h = hashlib.sha256()
        with open(file_path, "rb") as f:
            for chunk in iter(lambda: f.read(1024 * 1024), b""):
                h.update(chunk)
        return h.hexdigest()

    def _find_doc_by_hash(self, source_hash: str) -> Optional[Dict]:
        for item in self._manifest:
            if item.get("source_hash") == source_hash:
                return item
        return None

    def _find_doc_by_path(self, source_path: str) -> Optional[Dict]:
        for item in self._manifest:
            if item.get("source_path") == source_path:
                return item
        return None

    # =========================
    # ingest
    # =========================
    def ingest(self, file_path: str) -> IngestReport:
        path = Path(file_path)
        if not path.exists():
            raise FileNotFoundError(f"File not found: {file_path}")

        source_path = self._normalize_path(file_path)
        source_hash = self._calc_file_hash(source_path)

        # 1) 完全相同文件已经入库：直接跳过
        existed_same_hash = self._find_doc_by_hash(source_hash)
        if existed_same_hash is not None:
            return IngestReport(
                doc_id=existed_same_hash["doc_id"],
                file_name=Path(source_path).name,
                num_chunks=existed_same_hash.get("num_chunks", 0),
                status="skipped",
                message=f"File already ingested: {source_path}",
            )

        # 2) 同一路径但内容变了：先删旧版本，再入新版本
        existed_same_path = self._find_doc_by_path(source_path)
        if existed_same_path is not None:
            old_doc_id = existed_same_path["doc_id"]
            self.index.delete_doc(old_doc_id)
            self._manifest = [x for x in self._manifest if x["doc_id"] != old_doc_id]
            self._save_manifest()

        # 3) 正常入库
        document, chunks = self.processor.process_file(source_path)

        for chunk in chunks:
            chunk.metadata["source_path"] = source_path
            chunk.metadata["source_hash"] = source_hash

        added = self.index.add_chunks(chunks)

        record = {
            "doc_id": document.doc_id,
            "file_name": document.file_name,
            "source_path": source_path,
            "source_hash": source_hash,
            "file_type": document.file_type,
            "num_chunks": added,
        }
        self._manifest.append(record)
        self._save_manifest()

        return IngestReport(
            doc_id=document.doc_id,
            file_name=document.file_name,
            num_chunks=added,
            status="success",
            message=f"Ingested {added} chunks from {document.file_name}.",
        )

    def batch_ingest(self, file_paths: List[str]) -> List[IngestReport]:
        reports: List[IngestReport] = []
        for fp in file_paths:
            try:
                reports.append(self.ingest(fp))
            except Exception as exc:
                reports.append(
                    IngestReport(
                        doc_id="",
                        file_name=Path(fp).name,
                        num_chunks=0,
                        status="failed",
                        message=str(exc),
                    )
                )
        return reports

    # =========================
    # search
    # =========================
    def search(self, query: str, top_k: int = 5, doc_id: Optional[str] = None) -> SearchResponse:
        results = self.index.search(query=query, top_k=top_k, doc_id=doc_id)
        return SearchResponse(query=query, top_k=top_k, results=results)

    # =========================
    # manage docs
    # =========================
    def list_documents(self) -> List[Dict]:
        return list(self._manifest)

    def delete_document(self, doc_id: str) -> int:
        removed = self.index.delete_doc(doc_id)
        if removed > 0:
            self._manifest = [x for x in self._manifest if x["doc_id"] != doc_id]
            self._save_manifest()
        return removed

    def delete_by_path(self, file_path: str) -> int:
        source_path = self._normalize_path(file_path)
        item = self._find_doc_by_path(source_path)
        if item is None:
            return 0
        return self.delete_document(item["doc_id"])

    def update_file(self, file_path: str) -> IngestReport:
        """
        强制按当前文件内容更新：
        - 如果路径已存在旧版本，先删掉
        - 然后重新入库
        """
        source_path = self._normalize_path(file_path)
        old_item = self._find_doc_by_path(source_path)
        if old_item is not None:
            self.delete_document(old_item["doc_id"])
        return self.ingest(source_path)
