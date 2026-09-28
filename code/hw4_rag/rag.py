from __future__ import annotations

import json
import sys
import time
from pathlib import Path

import numpy as np
import yaml
from llama_index.core import Document, StorageContext, VectorStoreIndex
from llama_index.core.node_parser import TokenTextSplitter
from llama_index.core.schema import MetadataMode

try:
    from llama_index.core.vector_stores import SimpleVectorStore
except ImportError:
    from llama_index.core.vector_stores.simple import SimpleVectorStore

ROOT = Path(__file__).resolve().parents[2]
CORPUS_DIR = ROOT / "data" / "hw03_corpus" / "selected_pypi"
QUESTIONS_FILE = ROOT / "reports" / "hw04" / "questions.yaml"
RAW_DIR = ROOT / "reports" / "hw04" / "raw"
MODEL_NAME = "sentence-transformers/all-MiniLM-L6-v2"
REFUSAL = "I cannot answer this question from the provided documents"

sys.path.insert(0, str(ROOT))
from src.model_client import ModelClient


def cosine_similarity(first, second):
    first = np.asarray(first, dtype=float)
    second = np.asarray(second, dtype=float)
    denominator = np.linalg.norm(first) * np.linalg.norm(second)

    if denominator == 0:
        return 0.0

    return float(np.dot(first, second) / denominator)


def load_questions():
    with QUESTIONS_FILE.open("r", encoding="utf-8") as file:
        return yaml.safe_load(file)["questions"]


def load_documents():
    documents = []

    for path in sorted(CORPUS_DIR.glob("*.json")):
        if path.name == "selection_summary.json":
            continue

        record = json.loads(path.read_text(encoding="utf-8"))

        documents.append(
            Document(
                text=json.dumps(record, ensure_ascii=False, indent=2),
                metadata={"source_file": path.name},
            )
        )

    return documents


def build_index(documents, embed_model):
    splitter = TokenTextSplitter(
        chunk_size=500,
        chunk_overlap=50,
    )

    nodes = splitter.get_nodes_from_documents(documents)

    for chunk_id, node in enumerate(nodes):
        node.metadata["chunk_id"] = chunk_id
        node.metadata["source_file"] = node.metadata.get(
            "source_file",
            "unknown",
        )

    storage_context = StorageContext.from_defaults(
        vector_store=SimpleVectorStore()
    )

    index = VectorStoreIndex(
        nodes,
        storage_context=storage_context,
        embed_model=embed_model,
    )

    return index, nodes

def retrieve(index, question, embed_model, top_k):
    query_vector = embed_model.get_query_embedding(question)
    retriever = index.as_retriever(similarity_top_k=top_k)
    results = retriever.retrieve(question)

    retrieved = []

    for rank, result in enumerate(results, start=1):
        node = result.node
        text = node.get_content(
            metadata_mode=MetadataMode.NONE
        ).strip()

        retrieved.append(
            {
                "rank": rank,
                "source_file": str(
                    node.metadata.get("source_file", "unknown")
                ),
                "chunk_id": int(
                    node.metadata.get("chunk_id", -1)
                ),
                "score": round(float(result.score or 0.0), 6),
                "text": text,
                "cosine_similarity": round(
                    cosine_similarity(
                        query_vector,
                        embed_model.get_text_embedding(text),
                    ),
                    6,
                ),
            }
        )

    return retrieved


def print_retrieved(question_id, top_k, chunks):
    print(f"\n--- Retrieved chunks: {question_id}, k={top_k} ---")

    for chunk in chunks:
        print(
            f"[rank={chunk['rank']}] "
            f"source={chunk['source_file']} "
            f"chunk_id={chunk['chunk_id']} "
            f"score={chunk['score']}"
        )
        print(chunk["text"])
        print("---")


def remove_duplicates_and_irrelevant(chunks):
    if not chunks:
        return []

    survivors = []
    seen_text = set()
    best_score = chunks[0]["score"]

    for chunk in chunks:
        text_key = " ".join(chunk["text"].split())

        if text_key in seen_text:
            continue

        seen_text.add(text_key)

        if chunk["score"] >= max(best_score - 0.15, 0.0):
            survivors.append(chunk)

    return survivors


def make_context(chunks):
    sections = []

    for number, chunk in enumerate(chunks, start=1):
        sections.append(
            f"[Source {number}: {chunk['source_file']}, "
            f"chunk {chunk['chunk_id']}]\n"
            f"{chunk['text']}"
        )

    return "\n\n".join(sections)


def ask_model(client, question, configuration, chunks):
    if configuration == "No-RAG":
        prompt = f"""
Answer the following question.

Question:
{question}

Give a concise answer.
"""
    elif configuration == "Basic-RAG":
        context = "\n\n".join(chunk["text"] for chunk in chunks)

        prompt = f"""
Answer the question using the context below.

Context:
{context}

Question:
{question}

Give a concise answer.
"""
    else:
        context = make_context(chunks)

        prompt = f"""
You are a grounded question-answering system.

Answer only from the provided context.
Use the source number when making a factual claim.
Do not use outside knowledge.
If the evidence is insufficient, respond exactly:
I cannot answer this question from the provided documents

Context:
{context}

Question:
{question}

Answer:
"""

    response = client.complete(
        [{"role": "user", "content": prompt}]
    )

    return response["content"]


def keyword_overlap(answer, expected_answer):
    stop_words = {
        "the", "a", "an", "and", "or", "to", "of", "in",
        "is", "are", "that", "this", "for", "with", "on",
        "by", "it", "as", "from", "can", "be", "which",
    }

    expected_words = {
        word.strip(".,;:()").lower()
        for word in expected_answer.split()
        if word.strip(".,;:()").lower() not in stop_words
    }

    answer_words = {
        word.strip(".,;:()").lower()
        for word in answer.split()
    }

    if not expected_words:
        return 0.0

    return len(expected_words & answer_words) / len(expected_words)


def evaluate(question, answer, chunks, configuration):
    expected_sources = set(
        question.get("expected_source_files", [])
    )
    retrieved_sources = {
        chunk["source_file"]
        for chunk in chunks
    }

    must_refuse = question.get("must_refuse", False)
    refused = REFUSAL.lower() in answer.lower()

    correct_retrieval = (
        expected_sources.issubset(retrieved_sources)
        if expected_sources
        else None
    )

    if must_refuse:
        correct_answer = refused
        refused_when_needed = refused
    else:
        correct_answer = (
            keyword_overlap(
                answer,
                question["expected_answer"],
            )
            >= 0.25
        )
        refused_when_needed = None

    grounded = (
        refused
        if must_refuse
        else configuration == "Context-RAG"
    )

    return {
        "correct_retrieval": correct_retrieval,
        "correct_answer_heuristic": correct_answer,
        "grounded": grounded,
        "refused_when_needed": refused_when_needed,
        "retrieved_sources": sorted(retrieved_sources),
        "answer": answer,
    }

def main():
    RAW_DIR.mkdir(parents=True, exist_ok=True)

    print("Loading questions...")
    questions = load_questions()

    print("Loading embedding model...")
    from llama_index.embeddings.huggingface import (
        HuggingFaceEmbedding,
    )

    embed_model = HuggingFaceEmbedding(
        model_name=MODEL_NAME
    )

    print("Loading corpus...")
    documents = load_documents()
    print(f"Documents loaded: {len(documents)}")

    print("Building 500-token / 50-overlap index...")
    index, nodes = build_index(
        documents,
        embed_model,
    )
    print(f"Chunks created: {len(nodes)}")

    print("Loading local Ollama model...")
    client = ModelClient(
        temperature=0.0,
        json_mode=False,
    )

    comparison_rows = []
    retrieval_rows = []

    for question in questions:
        question_id = question["id"]
        question_text = question["question"]

        chunks = retrieve(
            index,
            question_text,
            embed_model,
            top_k=3,
        )

        print_retrieved(
            question_id,
            3,
            chunks,
        )

        retrieval_rows.append(
            {
                "question_id": question_id,
                "top_k": 3,
                "chunks": chunks,
            }
        )

        for configuration in [
            "No-RAG",
            "Basic-RAG",
            "Context-RAG",
        ]:
            selected_chunks = chunks

            if configuration == "Context-RAG":
                selected_chunks = (
                    remove_duplicates_and_irrelevant(
                        chunks
                    )
                )

            started = time.perf_counter()

            try:
                answer = ask_model(
                    client,
                    question_text,
                    configuration,
                    selected_chunks,
                )
                error = None
            except Exception as exc:
                answer = ""
                error = repr(exc)

            latency_ms = (
                time.perf_counter() - started
            ) * 1000

            evaluation = evaluate(
                question,
                answer,
                selected_chunks,
                configuration,
            )

            comparison_rows.append(
                {
                    "question_id": question_id,
                    "question_type": question["type"],
                    "configuration": configuration,
                    "top_k": 3,
                    "latency_ms": round(
                        latency_ms,
                        3,
                    ),
                    "error": error,
                    **evaluation,
                }
            )

            print(
                f"{question_id} / {configuration}: "
                f"{answer}"
            )

    sweep_rows = []
    sweep_question = questions[0]

    for top_k in [1, 3, 5]:
        chunks = retrieve(
            index,
            sweep_question["question"],
            embed_model,
            top_k,
        )

        print_retrieved(
            sweep_question["id"],
            top_k,
            chunks,
        )

        sweep_rows.append(
            {
                "question_id": sweep_question["id"],
                "top_k": top_k,
                "sources": [
                    chunk["source_file"]
                    for chunk in chunks
                ],
                "chunk_ids": [
                    chunk["chunk_id"]
                    for chunk in chunks
                ],
                "scores": [
                    chunk["score"]
                    for chunk in chunks
                ],
            }
        )

    (RAW_DIR / "retrieved_chunks.json").write_text(
        json.dumps(
            retrieval_rows,
            indent=2,
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    (RAW_DIR / "rag_comparison.json").write_text(
        json.dumps(
            comparison_rows,
            indent=2,
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    (RAW_DIR / "k_sweep.json").write_text(
        json.dumps(
            sweep_rows,
            indent=2,
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    print("\nRAG outputs written to:", RAW_DIR)
    print("Comparison rows:", len(comparison_rows))
    print("Sweep rows:", len(sweep_rows))


if __name__ == "__main__":
    main()
