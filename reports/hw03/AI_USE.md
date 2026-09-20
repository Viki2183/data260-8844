# AI Use Disclosure

I used an AI assistant to help understand the HW3 requirements, plan the repository structure, explain authentication and retrieval concepts, draft starter code, and troubleshoot errors.

I personally created the Git branch, downloaded the OSV corpus, selected the local records, created the questions, ran the FastAPI application, tested login and session expiration, captured screenshots, executed the retrieval experiments, and reviewed the metrics.

One unsuitable suggestion was the initial import of `MetadataMode` directly from `llama_index.core`. My installed LlamaIndex version required the import from `llama_index.core.schema`.

I detected the problem when the retrieval script stopped with an ImportError. I also independently verified the Hugging Face cache error when the model download failed with an access-denied message.

I fixed the import path and redirected the Hugging Face cache to a writable `.hf_cache` directory inside the repository. The smoke test then passed, and the complete retrieval experiment successfully generated results for all five questions and all three chunking techniques.