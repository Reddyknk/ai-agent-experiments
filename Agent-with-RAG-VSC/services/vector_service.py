from __future__ import annotations

import hashlib
import re
from pathlib import Path
from typing import Any

import chromadb
import requests

from config import DATABASE_DIR, PROJECT_ROOT, SKILLS_DIR


class VectorService:
    def __init__(self):
        self.db_dir = str(DATABASE_DIR)
        self.client = chromadb.PersistentClient(path=self.db_dir)
        self.skill_collection = self.client.get_or_create_collection("skills")
        self.doc_collection = self.client.get_or_create_collection("documents")

    def ensure_initialized(self) -> None:
        DATABASE_DIR.mkdir(parents=True, exist_ok=True)
        self.skill_collection = self.client.get_or_create_collection("skills")
        self.doc_collection = self.client.get_or_create_collection("documents")

    def ensure_skill_index(self) -> None:
        self.ensure_initialized()
        if self.skill_collection.count() == 0:
            self._load_skills_from_directory()

    def _load_skills_from_directory(self) -> None:
        if not SKILLS_DIR.exists():
            return
        for skill_dir in sorted(SKILLS_DIR.iterdir()):
            if not skill_dir.is_dir():
                continue
            skill_file = skill_dir / "SKILL.md"
            if not skill_file.exists():
                continue
            content = skill_file.read_text(encoding="utf-8")
            if not self._skill_exists(skill_dir.name):
                self.skill_collection.add(
                    ids=[skill_dir.name],
                    documents=[content],
                    metadatas=[{"name": skill_dir.name, "path": str(skill_file), "content": content}],
                )

    def _skill_exists(self, name: str) -> bool:
        try:
            results = self.skill_collection.get(where={"name": name})
            return bool(results.get("ids"))
        except Exception:
            return False

    def query_skills(self, query: str, threshold: float = 0.2, limit: int = 3) -> list[dict[str, Any]]:
        self.ensure_skill_index()
        if not query:
            return []
        results = self.skill_collection.query(query_texts=[query], n_results=limit)
        items: list[dict[str, Any]] = []
        for idx, doc in enumerate(results.get("documents", [[]])[0]):
            metadata = results.get("metadatas", [[{}]])[0][idx]
            distance = results.get("distances", [[1.0]])[0][idx]
            score = round(1 / (1 + distance), 6)
            if score >= threshold:
                items.append({
                    "name": metadata.get("name", "skill"),
                    "content": doc,
                    "score": score,
                    "distance": distance,
                })
        return items

    def query_documents(self, query: str, threshold: float = 0.3, limit: int = 5) -> list[dict[str, Any]]:
        self.ensure_initialized()
        if not query or self.doc_collection.count() == 0:
            return []
        results = self.doc_collection.query(query_texts=[query], n_results=min(limit, self.doc_collection.count()))
        items: list[dict[str, Any]] = []
        candidates: list[dict[str, Any]] = []
        documents = results.get("documents", [[]])[0]
        metadatas = results.get("metadatas", [[{}]])[0]
        distances = results.get("distances", [[1.0]])[0]
        for index, document in enumerate(documents):
            distance = distances[index]
            metadata = metadatas[index] or {}
            source = metadata.get("source", "unknown")
            candidate = {
                "id": results.get("ids", [[]])[0][index],
                "title": metadata.get("title") or Path(source).name or source,
                "source": source,
                "content": document,
                "score": distance,
            }
            candidates.append(candidate)
            if distance <= threshold:
                items.append(candidate)
        if not items:
            query_terms = {term for term in re.findall(r"[a-zA-Z]+", query.lower()) if len(term) > 3}
            items = [
                candidate for candidate in candidates
                if query_terms.intersection(set(re.findall(r"[a-zA-Z]+", f"{candidate['title']} {candidate['source']} {candidate['content']}".lower())))
            ][:limit]
        return items

    def populate_from_source(self, source: str, chunk_size: int = 1200, overlap: int = 150) -> dict[str, Any]:
        self.ensure_initialized()
        chunk_size = max(100, int(chunk_size))
        overlap = max(0, min(int(overlap), chunk_size - 1))
        sources: list[tuple[str, str, str]] = []
        path = PROJECT_ROOT / source if not source.startswith("http") else None
        if path and path.exists():
            files = list(path.rglob("*.txt")) + list(path.rglob("*.md")) + list(path.rglob("*.csv"))
            sources = [(str(file), file.name, file.read_text(encoding="utf-8", errors="ignore")) for file in files]
        elif source.startswith(("http://", "https://")):
            response = requests.get(source, timeout=20)
            response.raise_for_status()
            title = source.rstrip("/").rsplit("/", 1)[-1] or source
            sources = [(source, title, response.text)]

        existing_ids = set(self.doc_collection.get(include=[]).get("ids", []))
        ingested: list[dict[str, Any]] = []
        total_chunks = 0
        for source_name, title, text in sources:
            if not text.strip():
                continue
            chunks = self._chunk_text(text, chunk_size, overlap)
            document_chunks = 0
            for index, chunk in enumerate(chunks):
                chunk_id = hashlib.sha256(f"{source_name}:{index}:{chunk}".encode()).hexdigest()
                if chunk_id in existing_ids:
                    continue
                self.doc_collection.add(
                    ids=[chunk_id],
                    documents=[chunk],
                    metadatas=[{"source": source_name, "type": "doc", "title": title, "chars": len(text), "chunk_index": index, "chunk_count": len(chunks)}],
                )
                existing_ids.add(chunk_id)
                document_chunks += 1
            if document_chunks:
                ingested.append({"id": hashlib.md5(source_name.encode()).hexdigest(), "title": title, "chars": len(text), "chunks": document_chunks})
                total_chunks += document_chunks
        return {"documents": len(ingested), "chunks": total_chunks, "source": source, "items": ingested}

    def _chunk_text(self, text: str, chunk_size: int, overlap: int) -> list[str]:
        chunks: list[str] = []
        step = chunk_size - overlap
        for start in range(0, len(text), step):
            chunk = text[start:start + chunk_size].strip()
            if chunk:
                chunks.append(chunk)
            if start + chunk_size >= len(text):
                break
        return chunks

    def get_stats(self) -> dict[str, Any]:
        try:
            documents = self.doc_collection.count()
            skill_count = self.skill_collection.count()
            total_chars = 0
            docs = self.list_documents()
            for row in docs:
                total_chars += row.get("chars", 0)
            size_mb = round((total_chars / 1024 / 1024), 2)
            chunks = sum(row.get("chunks", 0) for row in docs)
            return {"documents": len(docs), "chunks": skill_count + chunks, "size_mb": size_mb}
        except Exception:
            return {"documents": 0, "chunks": 0, "size_mb": 0}

    def list_skill_records(self) -> list[dict[str, Any]]:
        self.ensure_skill_index()
        try:
            result = self.skill_collection.get(include=["metadatas", "documents"])
            records = []
            for idx, doc_id in enumerate(result.get("ids", [])):
                metadata = result.get("metadatas", [{}])[idx]
                records.append({"id": doc_id, "name": metadata.get("name", doc_id), "content": result.get("documents", [""])[idx][:200]})
            return records
        except Exception:
            return []

    def list_documents(self) -> list[dict[str, Any]]:
        try:
            result = self.doc_collection.get(include=["metadatas", "documents"])
            grouped: dict[tuple[str, str], dict[str, Any]] = {}
            for index, doc_id in enumerate(result.get("ids", [])):
                metadata = result.get("metadatas", [{}])[index]
                source = metadata.get("source", "unknown")
                title = metadata.get("title") or Path(source).name or source
                key = (source, title)
                if key not in grouped:
                    stored_text = result.get("documents", [""])[index] or ""
                    grouped[key] = {"id": doc_id, "title": title, "source": source, "chars": metadata.get("chars", len(stored_text)), "chunks": 0}
                grouped[key]["chunks"] += 1
            return list(grouped.values())
        except Exception:
            return []

    def reset_all(self) -> None:
        try:
            self.client.delete_collection("skills")
        except Exception:
            pass
        try:
            self.client.delete_collection("documents")
        except Exception:
            pass
        self.skill_collection = self.client.get_or_create_collection("skills")
        self.doc_collection = self.client.get_or_create_collection("documents")

    def delete_document(self, doc_id: str) -> None:
        try:
            self.doc_collection.delete(ids=[doc_id])
        except Exception:
            pass
