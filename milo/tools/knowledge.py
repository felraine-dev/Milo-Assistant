"""Second Brain: Local RAG document ingestion and semantic search."""

from __future__ import annotations

import hashlib
import os
import chromadb
from google import genai
from pypdf import PdfReader

from milo.safety import RISK_HIGH, tool, confirm

_DB_PATH = ".milo_brain"
_COLLECTION_NAME = "milo_second_brain"
_EMBED_MODEL = "gemini-embedding-001"


def _get_collection():
    client = chromadb.PersistentClient(path=_DB_PATH)
    return client.get_or_create_collection(name=_COLLECTION_NAME)


def _embed_texts(texts: list[str]) -> list[list[float]]:
    client = genai.Client()
    embeddings = []
    for text in texts:
        response = client.models.embed_content(
            model=_EMBED_MODEL,
            contents=text,
        )
        embeddings.append(response.embeddings[0].values)
    return embeddings


def _chunk_text(text: str, chunk_size: int = 800, overlap: int = 150) -> list[str]:
    """Split text into overlapping chunks to preserve context across boundaries."""
    chunks = []
    start = 0
    text_len = len(text)
    while start < text_len:
        end = min(start + chunk_size, text_len)
        chunk = text[start:end].strip()
        if chunk:
            chunks.append(chunk)
        if end == text_len:
            break
        start += chunk_size - overlap
    return chunks


def _extract_text(file_path: str) -> str:
    ext = os.path.splitext(file_path)[1].lower()
    if ext == ".pdf":
        reader = PdfReader(file_path)
        return "\n".join(page.extract_text() or "" for page in reader.pages)
    with open(file_path, "r", encoding="utf-8", errors="replace") as f:
        return f.read()


@tool(risk=RISK_HIGH)
def ingest_documents(target_path: str) -> str:
    """Read, chunk, and index local Markdown, text, or Python files into Milo's Second Brain.

    Args:
        target_path: Path to a specific file or directory of notes/documents to index.
    """
    target_path = os.path.abspath(target_path)

    if not os.path.exists(target_path):
        return f"Path not found: {target_path}"

    action_desc = f"Ingest and index documents from path: {target_path}"
    if not confirm(action_desc):
        return f"Cancelled: User aborted document ingestion for {target_path}."

    supported_exts = {".md", ".txt", ".pdf", ".py", ".js", ".json"}
    files_to_process: list[str] = []

    if os.path.isfile(target_path):
        files_to_process.append(target_path)
    else:
        for root, _, files in os.walk(target_path):
            for file in files:
                if os.path.splitext(file)[1].lower() in supported_exts:
                    files_to_process.append(os.path.join(root, file))

    if not files_to_process:
        return f"No supported files ({', '.join(supported_exts)}) found in {target_path}."

    collection = _get_collection()
    total_chunks = 0
    indexed_files = 0

    for file_path in files_to_process:
        try:
            raw_text = _extract_text(file_path)
            chunks = _chunk_text(raw_text)
            if not chunks:
                continue

            embeddings = _embed_texts(chunks)
            abs_path = os.path.abspath(file_path)
            ids = [
                hashlib.sha256(f"{abs_path}:{i}".encode()).hexdigest()[:16]
                for i in range(len(chunks))
            ]
            metadatas = [{"source": abs_path, "chunk": i} for i in range(len(chunks))]

            collection.upsert(
                ids=ids,
                documents=chunks,
                embeddings=embeddings,
                metadatas=metadatas,
            )
            total_chunks += len(chunks)
            indexed_files += 1
        except Exception as exc:
            return f"Failed indexing file {file_path}: {exc}"

    return f"Indexed {total_chunks} semantic chunks across {indexed_files} file(s) into Second Brain."


@tool()
def query_knowledge_base(query: str, top_k: int = 4) -> str:
    """Semantically search Milo's Second Brain for notes, code, or documentation matching a concept.

    Args:
        query: The natural language question or concept to search for.
        top_k: Number of most relevant text chunks to retrieve. Defaults to 4.
    """
    collection = _get_collection()
    if collection.count() == 0:
        return "Second Brain is currently empty. Use ingest_documents first to index some files."

    try:
        query_embedding = _embed_texts([query])[0]
        results = collection.query(
            query_embeddings=[query_embedding],
            n_results=min(top_k, collection.count()),
        )
    except Exception as exc:
        return f"Knowledge retrieval error: {exc}"

    documents = results.get("documents", [[]])[0]
    metadatas = results.get("metadatas", [[]])[0]

    if not documents:
        return f"No relevant context found for: '{query}'"

    formatted = []
    for doc, meta in zip(documents, metadatas):
        source = os.path.basename(meta.get("source", "unknown"))
        formatted.append(f"\n{doc}")

    return "\n\n---\n\n".join(formatted)


@tool()
def list_knowledge_sources() -> str:
    """List all unique files currently indexed inside Milo's Second Brain."""
    collection = _get_collection()
    count = collection.count()
    if count == 0:
        return "Second Brain is empty (0 chunks indexed)."

    data = collection.get(include=["metadatas"])
    sources = sorted({
        meta["source"] for meta in data.get("metadatas", []) if meta and "source" in meta
    })
    source_list = "\n".join(f"- {src}" for src in sources)
    return f"Total indexed chunks: {count}\nIndexed sources:\n{source_list}"