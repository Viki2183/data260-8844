from __future__ import annotations

import csv
import json
import time
from pathlib import Path
from statistics import mean

import numpy as np
import yaml
from llama_index.core import (
    Document,
    StorageContext,
    VectorStoreIndex,
)
from llama_index.core.schema import MetadataMode
from llama_index.core.node_parser import (
    SemanticSplitterNodeParser,
    SentenceWindowNodeParser,
    TokenTextSplitter,
)
from llama_index.embeddings.huggingface import HuggingFaceEmbedding

try:
    from llama_index.core.vector_stores import SimpleVectorStore
except ImportError:
    from llama_index.core.vector_stores.simple import SimpleVectorStore


REPOSITORY_ROOT = Path(__file__).resolve().parents[2]

CORPUS_DIR = (
    REPOSITORY_ROOT
    / "data"
    / "hw03_corpus"
    / "selected_pypi"
)

QUESTIONS_PATH = (
    REPOSITORY_ROOT
    / "reports"
    / "hw03"
    / "questions.yaml"
)

RAW_DIR = (
    REPOSITORY_ROOT
    / "reports"
    / "hw03"
    / "raw"
)

MODEL_NAME = "sentence-transformers/all-MiniLM-L6-v2"
TOP_K = 5

TECHNIQUES = (
    "Token",
    "Semantic",
    "Sentence-window",
)


def load_questions() -> list[dict]:
    """Load the fixed questions committed before retrieval."""
    with QUESTIONS_PATH.open("r", encoding="utf-8") as file:
        data = yaml.safe_load(file)

    questions = data.get("questions", [])

    if len(questions) < 5:
        raise ValueError(
            "questions.yaml must contain at least five questions."
        )

    return questions


def record_to_text(record: dict) -> str:
    """Convert one OSV record into searchable text."""
    return json.dumps(
        record,
        ensure_ascii=False,
        indent=2,
    )


def load_documents() -> list[Document]:
    """Load selected OSV JSON records as LlamaIndex documents."""
    documents = []

    for path in sorted(CORPUS_DIR.glob("*.json")):
        if path.name == "selection_summary.json":
            continue

        with path.open("r", encoding="utf-8") as file:
            record = json.load(file)

        text = record_to_text(record)

        documents.append(
            Document(
                text=text,
                metadata={
                    "source_file": path.name,
                    "advisory_id": record.get("id", path.stem),
                    "package_names": [
                        item.get("package", {}).get("name", "")
                        for item in record.get("affected", [])
                    ],
                },
            )
        )

    if not documents:
        raise RuntimeError(
            f"No JSON documents found in {CORPUS_DIR}"
        )

    return documents


def get_node_text(node) -> str:
    """Return node text without metadata."""
    return node.get_content(
        metadata_mode=MetadataMode.NONE
    ).strip()


def build_nodes(
    documents: list[Document],
    technique: str,
    embed_model: HuggingFaceEmbedding,
):
    """Build nodes using one of the three required chunkers."""
    if technique == "Token":
        splitter = TokenTextSplitter(
            chunk_size=256,
            chunk_overlap=40,
        )

    elif technique == "Semantic":
        splitter = SemanticSplitterNodeParser(
            buffer_size=1,
            breakpoint_percentile_threshold=95,
            embed_model=embed_model,
        )

    elif technique == "Sentence-window":
        splitter = SentenceWindowNodeParser.from_defaults(
            window_size=3,
            window_metadata_key="window",
            original_text_metadata_key="original_text",
        )

    else:
        raise ValueError(
            f"Unknown technique: {technique}"
        )

    nodes = splitter.get_nodes_from_documents(documents)

    if not nodes:
        raise RuntimeError(
            f"No nodes were produced for {technique}."
        )

    return nodes


def build_index(nodes, embed_model):
    """Build an in-memory SimpleVectorStore index."""
    storage_context = StorageContext.from_defaults(
        vector_store=SimpleVectorStore()
    )

    return VectorStoreIndex(
        nodes,
        storage_context=storage_context,
        embed_model=embed_model,
    )


def cosine_similarity(
    first_vector: list[float],
    second_vector: list[float],
) -> float:
    """Compute cosine similarity between two vectors."""
    first = np.asarray(first_vector, dtype=float)
    second = np.asarray(second_vector, dtype=float)

    denominator = (
        np.linalg.norm(first) * np.linalg.norm(second)
    )

    if denominator == 0:
        return 0.0

    return float(np.dot(first, second) / denominator)


def compact_preview(text: str, limit: int = 160) -> str:
    """Create a short one-line text preview."""
    cleaned = " ".join(text.split())
    return cleaned[:limit]


def write_jsonl(path: Path, rows: list[dict]) -> None:
    """Write records as newline-delimited JSON."""
    with path.open("w", encoding="utf-8") as file:
        for row in rows:
            file.write(
                json.dumps(
                    row,
                    ensure_ascii=False,
                )
                + "\n"
            )


def write_csv(path: Path, rows: list[dict]) -> None:
    """Write retrieval records as CSV."""
    if not rows:
        return

    fieldnames = list(rows[0].keys())

    with path.open(
        "w",
        encoding="utf-8",
        newline="",
    ) as file:
        writer = csv.DictWriter(
            file,
            fieldnames=fieldnames,
        )
        writer.writeheader()
        writer.writerows(rows)


def main() -> None:
    """Run all retrieval experiments."""
    RAW_DIR.mkdir(parents=True, exist_ok=True)

    print("Loading questions...")
    questions = load_questions()

    print("Loading selected corpus...")
    documents = load_documents()
    print(f"Loaded documents: {len(documents)}")

    print("Loading embedding model...")
    embed_model = HuggingFaceEmbedding(
        model_name=MODEL_NAME
    )

    retrieval_rows = []
    query_embedding_rows = []
    chunk_stats = []
    wrong_retrievals = []

    for technique in TECHNIQUES:
        print(f"\n=== Building {technique} pipeline ===")

        nodes = build_nodes(
            documents=documents,
            technique=technique,
            embed_model=embed_model,
        )

        node_lengths = [
            len(get_node_text(node))
            for node in nodes
        ]

        chunk_stats.append(
            {
                "technique": technique,
                "chunks": len(nodes),
                "avg_chunk_length": round(
                    mean(node_lengths),
                    2,
                ),
            }
        )

        print(
            f"{technique} chunks: {len(nodes)}"
        )

        index = build_index(
            nodes=nodes,
            embed_model=embed_model,
        )

        retriever = index.as_retriever(
            similarity_top_k=TOP_K
        )

        for question in questions:
            question_id = question["id"]
            query_text = question["question"]
            expected_source = question[
                "expected_source_file"
            ]

            print(
                f"Running {technique} / {question_id}"
            )

            query_vector = (
                embed_model.get_query_embedding(
                    query_text
                )
            )

            query_embedding_rows.append(
                {
                    "technique": technique,
                    "question_id": question_id,
                    "query": query_text,
                    "embedding_dimension": len(
                        query_vector
                    ),
                    "first_8_values": [
                        round(float(value), 8)
                        for value in query_vector[:8]
                    ],
                    "query_shape": [
                        len(query_vector)
                    ],
                }
            )

            started = time.perf_counter()
            results = retriever.retrieve(query_text)
            latency_ms = (
                time.perf_counter() - started
            ) * 1000

            for rank, result in enumerate(
                results,
                start=1,
            ):
                node = result.node
                node_text = get_node_text(node)

                document_vector = (
                    embed_model.get_text_embedding(
                        node_text
                    )
                )

                cosine_sim = cosine_similarity(
                    query_vector,
                    document_vector,
                )

                source_file = str(
                    node.metadata.get(
                        "source_file",
                        "",
                    )
                )

                context_text = str(
                    node.metadata.get(
                        "window",
                        node_text,
                    )
                )

                store_score = result.score

                if store_score is not None:
                    store_score = float(
                        store_score
                    )

                row = {
                    "technique": technique,
                    "question_id": question_id,
                    "query": query_text,
                    "rank": rank,
                    "expected_source_file": (
                        expected_source
                    ),
                    "source_file": source_file,
                    "source_match": (
                        source_file
                        == expected_source
                    ),
                    "store_score": store_score,
                    "cosine_sim": round(
                        cosine_sim,
                        8,
                    ),
                    "chunk_len": len(node_text),
                    "preview": compact_preview(
                        node_text
                    ),
                    "context_preview": compact_preview(
                        context_text
                    ),
                    "query_shape": str(
                        [len(query_vector)]
                    ),
                    "document_shape": str(
                        [len(document_vector)]
                    ),
                    "retrieval_latency_ms": round(
                        latency_ms,
                        3,
                    ),
                }

                retrieval_rows.append(row)

            top_result = [
                row
                for row in retrieval_rows
                if (
                    row["technique"] == technique
                    and row["question_id"]
                    == question_id
                )
            ]

            top_result.sort(
                key=lambda item: item["rank"]
            )

            if top_result:
                best = top_result[0]

                if not best["source_match"]:
                    wrong_retrievals.append(best)

    metrics = []

    for technique in TECHNIQUES:
        technique_rows = [
            row
            for row in retrieval_rows
            if row["technique"] == technique
        ]

        per_question = []

        for question in questions:
            rows = [
                row
                for row in technique_rows
                if row["question_id"]
                == question["id"]
            ]

            rows.sort(
                key=lambda item: item["rank"]
            )

            if not rows:
                continue

            cosine_values = [
                float(row["cosine_sim"])
                for row in rows
            ]

            retrieved_sources = {
                row["source_file"]
                for row in rows
            }

            expected_source = question[
                "expected_source_file"
            ]

            per_question.append(
                {
                    "top1_cosine": max(
                        cosine_values
                    ),
                    "mean_at_k": mean(
                        cosine_values
                    ),
                    "recall_at_k": int(
                        expected_source
                        in retrieved_sources
                    ),
                    "latency_ms": float(
                        rows[0][
                            "retrieval_latency_ms"
                        ]
                    ),
                }
            )

        stats = next(
            item
            for item in chunk_stats
            if item["technique"] == technique
        )

        metrics.append(
            {
                "technique": technique,
                "chunks": stats["chunks"],
                "avg_chunk_length": stats[
                    "avg_chunk_length"
                ],
                "top1_cosine": round(
                    mean(
                        item["top1_cosine"]
                        for item in per_question
                    ),
                    6,
                ),
                "mean_at_k_cosine": round(
                    mean(
                        item["mean_at_k"]
                        for item in per_question
                    ),
                    6,
                ),
                "recall_at_k_mean": round(
                    mean(
                        item["recall_at_k"]
                        for item in per_question
                    ),
                    6,
                ),
                "mean_retrieval_latency_ms": round(
                    mean(
                        item["latency_ms"]
                        for item in per_question
                    ),
                    3,
                ),
            }
        )

    wrong_retrievals.sort(
        key=lambda item: float(
            item["cosine_sim"]
        ),
        reverse=True,
    )

    write_jsonl(
        RAW_DIR / "retrieval_results.jsonl",
        retrieval_rows,
    )

    write_csv(
        RAW_DIR / "retrieval_results.csv",
        retrieval_rows,
    )

    write_jsonl(
        RAW_DIR / "query_embeddings.jsonl",
        query_embedding_rows,
    )

    with (
        RAW_DIR / "chunking_stats.json"
    ).open("w", encoding="utf-8") as file:
        json.dump(
            chunk_stats,
            file,
            indent=2,
        )

    with (
        RAW_DIR / "metrics.json"
    ).open("w", encoding="utf-8") as file:
        json.dump(
            metrics,
            file,
            indent=2,
        )

    with (
        RAW_DIR / "wrong_retrieval_candidates.json"
    ).open("w", encoding="utf-8") as file:
        json.dump(
            wrong_retrievals,
            file,
            indent=2,
        )

    print("\n=== Metrics ===")

    for metric in metrics:
        print(json.dumps(metric, indent=2))

    print(
        "\nIncorrect top-1 candidates: "
        f"{len(wrong_retrievals)}"
    )

    print(
        f"\nRaw outputs written to: {RAW_DIR}"
    )


if __name__ == "__main__":
    main()