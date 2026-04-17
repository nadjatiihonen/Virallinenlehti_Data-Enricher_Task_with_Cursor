import json
import logging
import os
import tempfile
import unicodedata
from datetime import date
from enum import StrEnum
from pathlib import Path
from typing import Any

import instructor
from dotenv import load_dotenv
from openai import OpenAI
from pydantic import BaseModel, Field, ValidationError

PROCESSED_DIR = Path("data/processed")
FINAL_DIR = Path("data/final")
OUTPUT_JSON_PATH = FINAL_DIR / "yritystapahtumat.json"
MODEL_NAME = "gpt-4o-mini"
OPENAI_TIMEOUT_SECONDS = 60

logger = logging.getLogger(__name__)


class TapahtumaTyyppi(StrEnum):
    """Supported business event categories."""

    KONKURSSIN_ALKAMINEN = "konkurssin_alkaminen"
    KONKURSSIVALVONTA = "konkurssivalvonta"
    KONKURSSIN_PAATTYMINEN = "konkurssin_paattyminen"
    YRITYSSANEERAUKSEN_ALKAMINEN = "yrityssaneerauksen_alkaminen"
    YRITYSSANEERAUKSEN_LAKKAAMINEN = "yrityssaneerauksen_lakkaaminen"


class YritysTapahtuma(BaseModel):
    """Validated event payload generated from source page text."""

    tapahtuma_tyyppi: TapahtumaTyyppi
    y_tunnus: str = Field(
        pattern=r"^\d{7}-\d$",
        description="Suomalainen Y-tunnus muodossa 1234567-8.",
    )
    yrityksen_nimi: str = Field(min_length=1)
    tapahtuman_pvm: date
    lahdetiedosto: str = Field(min_length=1)
    sivunumero: int = Field(ge=1)


class YritysTapahtumaLista(BaseModel):
    """Container model for structured Instructor responses."""

    tapahtumat: list[YritysTapahtuma]


def configure_logging() -> None:
    """Configure module-wide logging format and level."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    )


def normalize_text_for_llm(text: str) -> str:
    """Normalize text to avoid encoding edge-cases in API requests."""
    normalized_text = unicodedata.normalize("NFKC", text)
    return normalized_text.replace("\x00", "")


def create_instructor_client() -> instructor.Instructor:
    """Create an Instructor-wrapped OpenAI client from environment settings."""
    load_dotenv()
    api_key = os.getenv("OPENAI_API_KEY", "").strip()
    if not api_key:
        raise RuntimeError("OPENAI_API_KEY is missing. Add it to your .env file.")
    openai_client = OpenAI(api_key=api_key, timeout=OPENAI_TIMEOUT_SECONDS)
    return instructor.from_openai(openai_client)


def is_dry_run_enabled() -> bool:
    """Return True when extraction should skip external LLM calls."""
    load_dotenv()
    value = os.getenv("EXTRACTOR_DRY_RUN", "").strip().lower()
    return value in {"1", "true", "yes", "on"}


def extract_events_from_text(
    client: instructor.Instructor,
    text: str,
    source_file: str,
    page_number: int,
) -> list[YritysTapahtuma]:
    """Call LLM for one page and return validated event objects."""
    page_text = normalize_text_for_llm(text)
    if not page_text.strip():
        return []

    system_prompt = (
        "Extract company events from legal notices. "
        "Return only facts explicitly present in the text. "
        "If a required field is missing or uncertain, omit that event."
    )
    user_prompt = (
        f"Source file: {source_file}\n"
        f"Page number: {page_number}\n\n"
        "Extract 0..N company events and return structured output. "
        "Fields: tapahtuma_tyyppi, y_tunnus, yrityksen_nimi, tapahtuman_pvm, "
        "lahdetiedosto, sivunumero.\n"
        "Use ISO date format YYYY-MM-DD for tapahtuman_pvm.\n\n"
        f"Text:\n{page_text}"
    )

    try:
        response = client.chat.completions.create(
            model=MODEL_NAME,
            response_model=YritysTapahtumaLista,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
        )
        return response.tapahtumat
    except ValidationError as exc:
        logger.warning("Validation error for %s page %s: %s", source_file, page_number, exc)
    except Exception as exc:  # pragma: no cover - external API failures
        logger.error("LLM extraction failed for %s page %s: %s", source_file, page_number, exc)
    return []


def read_processed_pages(file_path: Path) -> list[dict[str, Any]]:
    """Read parsed hot pages from a processed JSON payload."""
    with file_path.open("r", encoding="utf-8") as file_handle:
        payload = json.load(file_handle)
    pages = payload.get("pages", [])
    return pages if isinstance(pages, list) else []


def parse_page_record(page: dict[str, Any], source_name: str) -> tuple[str, int, str] | None:
    """Validate and normalize one page record from processed JSON."""
    source_file = str(page.get("source_file", "")).strip()
    page_text = str(page.get("text", ""))
    try:
        page_number = int(page.get("page_number", 0))
    except (TypeError, ValueError):
        page_number = 0

    if not source_file or page_number < 1:
        logger.warning("Skipping malformed page record in %s", source_name)
        return None
    return source_file, page_number, page_text


def atomic_write_json(output_path: Path, payload: list[dict[str, Any]]) -> None:
    """Persist JSON payload using temporary file then atomic replace."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        mode="w",
        dir=output_path.parent,
        prefix=f".{output_path.stem}_",
        suffix=".tmp",
        encoding="utf-8",
        delete=False,
    ) as temp_file:
        temp_path = Path(temp_file.name)
        json.dump(payload, temp_file, ensure_ascii=False, indent=2)
    temp_path.replace(output_path)


def process_processed_files(
    processed_dir: Path = PROCESSED_DIR,
    output_path: Path = OUTPUT_JSON_PATH,
) -> Path:
    """Process parsed pages and save validated event list to final JSON."""
    processed_files = sorted(processed_dir.glob("*_hot_pages.json"))
    if not processed_files:
        logger.warning("No processed files found in %s", processed_dir)
        atomic_write_json(output_path, [])
        return output_path

    dry_run = is_dry_run_enabled()
    client = None if dry_run else create_instructor_client()
    all_events: list[YritysTapahtuma] = []
    logger.info("Found %d processed file(s)", len(processed_files))
    if dry_run:
        logger.info("EXTRACTOR_DRY_RUN enabled; skipping LLM extraction and writing empty output.")

    for processed_file in processed_files:
        logger.info("Reading %s", processed_file.name)
        for page in read_processed_pages(processed_file):
            page_record = parse_page_record(page, processed_file.name)
            if page_record is None:
                continue
            source_file, page_number, page_text = page_record
            if dry_run:
                logger.info("Dry-run skip for %s page %s", source_file, page_number)
                continue
            if client is None:
                logger.error("Instructor client not initialized.")
                continue
            extracted_events = extract_events_from_text(
                client=client,
                text=page_text,
                source_file=source_file,
                page_number=page_number,
            )
            all_events.extend(extracted_events)
            logger.info(
                "Extracted %d event(s) from %s page %s",
                len(extracted_events),
                source_file,
                page_number,
            )

    serialized_events = [item.model_dump(mode="json") for item in all_events]
    atomic_write_json(output_path, serialized_events)
    logger.info("Saved %d validated event(s) to %s", len(serialized_events), output_path)
    return output_path


def main() -> int:
    """Entrypoint for extraction command-line execution."""
    configure_logging()
    process_processed_files()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
