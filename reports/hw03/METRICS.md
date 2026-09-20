# HW3 Retrieval Metrics

## Experiment configuration

- Domain: Open-source package vulnerabilities
- DOMAIN_ID: 4
- Corpus: 69 selected OSV PyPI vulnerability records
- Corpus size: 507,649 bytes
- Embedding model: sentence-transformers/all-MiniLM-L6-v2
- Embedding dimension: 384
- Retrieval type: Retrieval-only RAG
- Top-k value: 5
- Device: CPU
- Token chunk size: 256 tokens
- Token chunk overlap: 40 tokens
- Semantic buffer size: 1
- Semantic breakpoint percentile: 95
- Sentence-window size: 3 neighboring sentences

## Retrieval quality comparison

| Technique | Chunks | Average chunk length | Top-1 cosine | Mean@5 cosine | Recall@5 mean | Mean retrieval latency (ms) |
|---|---:|---:|---:|---:|---:|---:|
| Token | 2,260 | 362.36 | 0.655152 | 0.527624 | 1.000000 | 153.062 |
| Semantic | 142 | 4,856.94 | 0.629102 | 0.414521 | 1.000000 | 31.038 |
| Sentence-window | 727 | 947.94 | 0.651468 | 0.495669 | 1.000000 | 61.474 |

## Interpretation

All three techniques achieved a Recall@5 mean of 1.0 across the five questions. This means that the expected source document appeared somewhere in the five retrieved results for every question.

Token chunking produced the strongest overall similarity measurements. It had the highest average top-1 cosine score and the highest Mean@5 cosine score. Its smaller chunks allowed the embedding model to focus on specific facts such as affected versions, fixed versions, vulnerability mechanisms, and package names.

Sentence-window chunking performed almost as well as token chunking. Its sentence-level nodes preserved more local context through neighboring-sentence metadata. This helped maintain readable context while avoiding the very large chunks created by semantic splitting.

Semantic chunking was the fastest during retrieval and produced only 142 chunks. However, its average chunk was approximately 4,857 characters long. These large chunks combined several ideas into one embedding, which lowered the average similarity of the top five results. Its perfect Recall@5 shows that the relevant documents were still retrieved, but the similarity separation was weaker.

For this corpus, I judge Token chunking to be the best overall technique. It produced the highest top-1 and Mean@5 cosine scores while still achieving perfect Recall@5. Sentence-window chunking was a close second and may be preferable when preserving surrounding sentence context is more important than minimizing retrieval time.

## High-scoring incorrect retrieval

The experiment found two incorrect top-1 retrievals for question q4:

- Expected source: `GHSA-226f-f24g-524w.json`
- Incorrect source: `GHSA-24c9-2m8q-qhmh.json`
- Technique: Semantic
- Cosine similarity: 0.7008324
- Store score: 0.5570291

The incorrect source is a closely related Open WebUI SSRF advisory. It shares important terms and concepts with the expected source, including Open WebUI, OAuth, profile-picture processing, and SSRF. The embedding therefore considered it highly similar. However, the expected question focused on the specific redirect-bypass behavior in which the initial URL is validated but the redirect destination is not revalidated. The sibling advisory did not provide the exact answer required by the question.

A second incorrect top-1 retrieval occurred for the Token technique:

- Expected source: `GHSA-226f-f24g-524w.json`
- Incorrect source: `GHSA-24c9-2m8q-qhmh.json`
- Cosine similarity: 0.67904045
- Store score: 0.6390733

This demonstrates that high embedding similarity does not always mean that the retrieved chunk contains the exact answer. Similar vulnerability names and attack concepts can cause a semantically related but incorrect advisory to rank first.

## Generated raw outputs

The experiment generated:

- `raw/retrieval_results.jsonl`
- `raw/retrieval_results.csv`
- `raw/query_embeddings.jsonl`
- `raw/chunking_stats.json`
- `raw/metrics.json`
- `raw/wrong_retrieval_candidates.json`

The JSONL and CSV files contain the technique, question ID, rank, store score, cosine similarity, source filename, chunk length, preview, vector shapes, and retrieval latency.

## AI use disclosure

### 1. What I used an AI assistant for and what I did myself

I used an AI assistant to understand the homework requirements, plan the repository structure, explain authentication and retrieval concepts, draft starter code, and help interpret Python and LlamaIndex errors. I personally created the repository branch, downloaded the OSV corpus, ran the commands, inspected the records, tested the application, captured screenshots, executed the retrieval experiment, and reviewed the generated metrics.

### 2. One AI-produced output that was wrong or unsuitable

The initial retrieval script imported `MetadataMode` directly from `llama_index.core`, but that import was not available in my installed LlamaIndex version.

The first Hugging Face download attempt also used a cache location that produced an access-denied error on Windows.

### 3. How I detected the problem

I detected the import problem when the script stopped with an `ImportError`. I detected the cache problem when the embedding model download failed with an `OSError` stating that access was denied.

I verified the problems by running the smoke test and reading the complete terminal error messages instead of assuming that the packages were working.

### 4. What I changed and why it works now

I changed the import to load `MetadataMode` from `llama_index.core.schema`, which matches the installed LlamaIndex package structure. I also redirected the Hugging Face cache to a writable `.hf_cache` directory inside the repository and disabled the problematic Xet download path.

After those changes, the smoke test completed successfully with a 384-dimensional embedding, and the full retrieval experiment completed for all five questions and all three chunking techniques.