from llama_index.core import Document
from llama_index.core.node_parser import (
    SemanticSplitterNodeParser,
    SentenceWindowNodeParser,
    TokenTextSplitter,
)
from llama_index.embeddings.huggingface import HuggingFaceEmbedding


def main() -> None:
    """Verify the required LlamaIndex components."""
    print("Loading embedding model...")

    embed_model = HuggingFaceEmbedding(
        model_name="sentence-transformers/all-MiniLM-L6-v2"
    )

    sample_text = (
        "Open-source packages may contain security vulnerabilities. "
        "Advisories describe affected versions and remediation guidance. "
        "Users should upgrade to a fixed release."
    )

    document = Document(text=sample_text)

    token_splitter = TokenTextSplitter(
        chunk_size=64,
        chunk_overlap=10,
    )

    semantic_splitter = SemanticSplitterNodeParser(
        buffer_size=1,
        breakpoint_percentile_threshold=95,
        embed_model=embed_model,
    )

    sentence_window_splitter = (
        SentenceWindowNodeParser.from_defaults(
            window_size=2,
        )
    )

    token_nodes = token_splitter.get_nodes_from_documents(
        [document]
    )

    semantic_nodes = (
        semantic_splitter.get_nodes_from_documents(
            [document]
        )
    )

    sentence_window_nodes = (
        sentence_window_splitter.get_nodes_from_documents(
            [document]
        )
    )

    query_vector = embed_model.get_query_embedding(
        "What are affected package versions?"
    )

    print(f"Embedding dimension: {len(query_vector)}")
    print(f"Token nodes: {len(token_nodes)}")
    print(f"Semantic nodes: {len(semantic_nodes)}")
    print(
        "Sentence-window nodes: "
        f"{len(sentence_window_nodes)}"
    )
    print("LlamaIndex API smoke test passed.")


if __name__ == "__main__":
    main()