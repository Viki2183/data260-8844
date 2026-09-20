import json
import shutil
from pathlib import Path


SOURCE_DIR = Path("data/hw03_corpus/pypi_records")
OUTPUT_DIR = Path("data/hw03_corpus/selected_pypi")

TARGET_BYTES = 500_000
MAX_FILES = 100
MIN_DETAILS_CHARACTERS = 800


def load_record(path: Path) -> dict:
    """Load one OSV JSON record."""
    with path.open("r", encoding="utf-8") as file:
        return json.load(file)


def record_is_useful(record: dict) -> bool:
    """Keep records containing enough explanatory text."""
    details = str(record.get("details", "")).strip()
    summary = str(record.get("summary", "")).strip()

    return (
        len(details) >= MIN_DETAILS_CHARACTERS
        and bool(summary)
        and bool(record.get("affected"))
    )


def main() -> None:
    """Select a deterministic, sufficiently large corpus subset."""
    if not SOURCE_DIR.exists():
        raise FileNotFoundError(
            f"Source directory not found: {SOURCE_DIR}"
        )

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    # Remove an earlier selection so repeated runs are reproducible.
    for old_file in OUTPUT_DIR.glob("*.json"):
        old_file.unlink()

    candidates = sorted(SOURCE_DIR.rglob("*.json"))

    selected = []
    selected_bytes = 0

    for source_path in candidates:
        record = load_record(source_path)

        if not record_is_useful(record):
            continue

        output_name = f"{record['id']}.json"
        output_path = OUTPUT_DIR / output_name

        shutil.copy2(source_path, output_path)

        file_size = output_path.stat().st_size
        selected.append(
            {
                "id": record["id"],
                "filename": output_name,
                "bytes": file_size,
                "summary": record.get("summary", ""),
            }
        )
        selected_bytes += file_size

        if (
            selected_bytes >= TARGET_BYTES
            or len(selected) >= MAX_FILES
        ):
            break

    if selected_bytes < 200_000:
        raise RuntimeError(
            "Selected corpus is below the required 200 KB."
        )

    selection_summary = {
        "source_directory": str(SOURCE_DIR),
        "selected_record_count": len(selected),
        "selected_total_bytes": selected_bytes,
        "minimum_required_bytes": 200_000,
        "records": selected,
    }

    summary_path = OUTPUT_DIR / "selection_summary.json"

    with summary_path.open("w", encoding="utf-8") as file:
        json.dump(selection_summary, file, indent=2)

    print(
        f"Selected records: {len(selected)}"
    )
    print(
        f"Selected bytes: {selected_bytes}"
    )
    print(
        f"Selection summary: {summary_path}"
    )


if __name__ == "__main__":
    main()