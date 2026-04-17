import json
import logging
import tempfile
from dataclasses import asdict, dataclass
from pathlib import Path

import fitz

RAW_DIR = Path("data/raw")
PROCESSED_DIR = Path("data/processed")
KEYWORDS = ("konkurssi", "yrityssaneeraus", "alkaminen", "lakkaaminen")

logger = logging.getLogger(__name__)


@dataclass
class HotPage:
    """Represents one relevant page extracted from a source PDF."""

    source_file: str
    page_number: int
    matched_keywords: list[str]
    text: str


def configure_logging() -> None:
    """Configure parser logging settings."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    )


def find_matched_keywords(text: str, keywords: tuple[str, ...]) -> list[str]:
    """Return keywords that appear in given text (case-insensitive)."""
    normalized_text = text.casefold()
    matched_keywords: list[str] = []
    for keyword in keywords:
        if keyword in normalized_text:
            matched_keywords.append(keyword)
            continue
        if keyword.endswith("minen"):
            inflection_stem = keyword[:-3]
            if inflection_stem in normalized_text:
                matched_keywords.append(keyword)
    return matched_keywords


def extract_hot_pages_from_pdf(pdf_path: Path, keywords: tuple[str, ...]) -> list[HotPage]:
    """Extract pages containing one or more relevant keywords."""
    matched_pages: list[HotPage] = []

    try:
        with fitz.open(pdf_path) as document:
            for page_number, page in enumerate(document, start=1):
                page_text = page.get_text().strip()
                if not page_text:
                    continue

                matched_keywords = find_matched_keywords(page_text, keywords)
                if not matched_keywords:
                    continue

                matched_pages.append(
                    HotPage(
                        source_file=pdf_path.name,
                        page_number=page_number,
                        matched_keywords=matched_keywords,
                        text=page_text,
                    )
                )
    except Exception as exc:  # pragma: no cover - external PDF parsing failure
        logger.error("Failed while parsing PDF %s: %s", pdf_path, exc)

    return matched_pages


def save_hot_pages_json(pdf_path: Path, hot_pages: list[HotPage], output_dir: Path) -> Path:
    """Save extracted pages to JSON with atomic file replacement."""
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / f"{pdf_path.stem}_hot_pages.json"
    payload = {
        "source_file": pdf_path.name,
        "hot_page_count": len(hot_pages),
        "pages": [asdict(item) for item in hot_pages],
    }
    with tempfile.NamedTemporaryFile(
        mode="w",
        dir=output_dir,
        prefix=f".{pdf_path.stem}_",
        suffix=".tmp",
        encoding="utf-8",
        delete=False,
    ) as temp_file:
        temp_path = Path(temp_file.name)
        json.dump(payload, temp_file, ensure_ascii=False, indent=2)
    temp_path.replace(output_path)

    return output_path


def parse_all_pdfs(raw_dir: Path = RAW_DIR, output_dir: Path = PROCESSED_DIR) -> None:
    """Process all PDFs in raw_dir and write page-level JSON outputs."""
    pdf_files = sorted(raw_dir.glob("*.pdf"))
    if not pdf_files:
        logger.warning("No PDF files found in %s", raw_dir)
        return

    logger.info("Found %d PDF file(s) in %s", len(pdf_files), raw_dir)
    for pdf_path in pdf_files:
        logger.info("Scanning %s", pdf_path.name)
        hot_pages = extract_hot_pages_from_pdf(pdf_path, KEYWORDS)
        output_path = save_hot_pages_json(pdf_path, hot_pages, output_dir)
        logger.info(
            "Saved %d hot page(s) from %s to %s",
            len(hot_pages),
            pdf_path.name,
            output_path,
        )


def main() -> int:
    """Entrypoint for parser command-line execution."""
    configure_logging()
    parse_all_pdfs()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
