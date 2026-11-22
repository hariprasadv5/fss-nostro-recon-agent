"""RAG knowledge layer over SOPs, policies, templates and past resolutions.

Backends:
  chroma - ChromaDB vector store with embeddings (pip install chromadb), persisted under outputs/chroma
  tfidf  - scikit-learn TF-IDF cosine similarity (offline fallback, no downloads)
Documents are split into chunks by markdown heading / bullet so each citation points to one SOP section.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path


@dataclass
class Chunk:
    chunk_id: str
    source: str
    section: str
    text: str


def chunk_markdown(path: Path) -> list[Chunk]:
    text = path.read_text(encoding="utf-8")
    doc_title = text.splitlines()[0].lstrip("# ").strip()
    chunks, section, buf = [], doc_title, []

    def flush():
        body = "\n".join(buf).strip()
        if body:
            chunks.append(Chunk(f"{path.stem}#{len(chunks)}", path.name, section, f"{section}\n{body}"))

    for line in text.splitlines()[1:]:
        if line.startswith("## "):
            flush(); buf = []; section = line[3:].strip()
        elif line.startswith("- CASE-"):          # one chunk per past case
            flush(); buf = [line]; section = line[2:15]
            flush(); buf = []; section = doc_title
        else:
            buf.append(line)
    flush()
    return chunks


class KnowledgeBase:
    def __init__(self, kb_dir: Path, backend: str = "auto", persist_dir: Path | None = None):
        self.chunks = [c for p in sorted(Path(kb_dir).glob("*.md")) for c in chunk_markdown(p)]
        self.backend = self._init_backend(backend, persist_dir)

    # ------------------------------------------------------------------
    def _init_backend(self, backend: str, persist_dir):
        if backend in ("auto", "chroma"):
            try:
                import chromadb  # noqa: F401
                client = chromadb.PersistentClient(path=str(persist_dir)) if persist_dir else chromadb.Client()
                self._col = client.get_or_create_collection("nostro_kb")
                if self._col.count() != len(self.chunks):
                    existing = self._col.get()["ids"]
                    if existing:
                        self._col.delete(ids=existing)
                    self._col.add(ids=[c.chunk_id for c in self.chunks], documents=[c.text for c in self.chunks],
                                  metadatas=[{"source": c.source, "section": c.section} for c in self.chunks])
                return "chroma"
            except Exception:
                if backend == "chroma":
                    raise
        from sklearn.feature_extraction.text import TfidfVectorizer
        self._vec = TfidfVectorizer(stop_words="english", ngram_range=(1, 2), sublinear_tf=True)
        self._mat = self._vec.fit_transform([c.text for c in self.chunks])
        return "tfidf"

    def search(self, query: str, k: int = 3) -> list[dict]:
        if self.backend == "chroma":
            r = self._col.query(query_texts=[query], n_results=k)
            by_id = {c.chunk_id: c for c in self.chunks}
            return [dict(source=by_id[i].source, section=by_id[i].section, text=by_id[i].text,
                         score=round(1 - d, 3)) for i, d in zip(r["ids"][0], r["distances"][0])]
        from sklearn.metrics.pairwise import cosine_similarity
        sims = cosine_similarity(self._vec.transform([query]), self._mat)[0]
        order = sims.argsort()[::-1][:k]
        return [dict(source=self.chunks[i].source, section=self.chunks[i].section,
                     text=self.chunks[i].text, score=round(float(sims[i]), 3)) for i in order]


def cite(hits: list[dict]) -> list[str]:
    return [f"{h['source']} > {h['section']}" for h in hits]


def clean_query(*parts: str) -> str:
    return re.sub(r"\s+", " ", " ".join(p for p in parts if p)).strip()
