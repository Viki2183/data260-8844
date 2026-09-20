import hashlib
import json
from datetime import date
from pathlib import Path


CORPUS_DIR = Path("data/hw03_corpus/selected_pypi")
OUTPUT_PATH = Path("reports/hw03/CORPUS_MANIFEST.json")


def sha256_file(path: Path) -> str:
    """Return the SHA-256 hash of a file."""
    digest = hashlib.sha256()

    with path.open("rb") as file:
        for block in iter(lambda: file.read(1024 * 1024), b""):
            digest.update(block)

    return digest.hexdigest()


def main() -> None:
    """Create a machine-readable corpus manifest."""
    if not CORPUS_DIR.exists():
        raise FileNotFoundError(
            f"Corpus directory not found: {CORPUS_DIR}"
        )

    documents = []

    for path in sorted(CORPUS_DIR.glob("*.json")):
        if path.name == "selection_summary.json":
            continue

        documents.append(
            {
                "filename": path.as_posix(),
                "bytes": path.stat().st_size,
                "sha256": sha256_file(path),
            }
        )

    manifest = {
        "domain_id": 4,
        "domain": "Open-source package vulnerabilities",
        "source_url": (
            "https://storage.googleapis.com/"
            "osv-vulnerabilities/PyPI/all.zip"
        ),
        "access_date": str(date.today()),
        "selected_document_count": len(documents),
        "selected_total_bytes": sum(
            item["bytes"] for item in documents
        ),
        "documents": documents,
    }

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)

    with OUTPUT_PATH.open("w", encoding="utf-8") as file:
        json.dump(manifest, file, indent=2)

    print(f"Documents: {len(documents)}")
    print(f"Total bytes: {manifest['selected_total_bytes']}")
    print(f"Manifest: {OUTPUT_PATH}")


if __name__ == "__main__":
    main()