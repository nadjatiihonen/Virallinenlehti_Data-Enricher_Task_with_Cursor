import argparse
import logging
import tempfile
import time
from pathlib import Path

import requests

BASE_URL = "https://www.virallinenlehti.fi/fi/journal/pdf/{year}{number}.pdf"
DEFAULT_OUTPUT_DIR = Path("data/raw")
REQUEST_TIMEOUT_SECONDS = 30
CHUNK_SIZE_BYTES = 8192
MAX_DOWNLOAD_ATTEMPTS = 3
RETRY_BACKOFF_SECONDS = 2.0

logger = logging.getLogger(__name__)


def configure_logging() -> None:
    """Configure module-wide logging format and level."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    )


def validate_inputs(year: int, number: str) -> str:
    """Validate download inputs and return normalized issue number."""
    normalized_number = str(number).strip()
    if year < 1900 or year > 2100:
        raise ValueError("Year must be between 1900 and 2100.")
    if not normalized_number:
        raise ValueError("Issue number cannot be empty.")
    return normalized_number


def build_pdf_url(year: int, number: str) -> str:
    """Build Official Gazette PDF URL for given year and issue number."""
    normalized_number = validate_inputs(year=year, number=number)
    return BASE_URL.format(year=year, number=normalized_number)


def write_response_to_file(response: requests.Response, target_path: Path) -> None:
    """Write HTTP response body to target path using atomic replace."""
    target_path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        mode="wb",
        dir=target_path.parent,
        prefix=f".{target_path.stem}_",
        suffix=".tmp",
        delete=False,
    ) as temp_file:
        temp_path = Path(temp_file.name)
        for chunk in response.iter_content(chunk_size=CHUNK_SIZE_BYTES):
            if chunk:
                temp_file.write(chunk)
    temp_path.replace(target_path)


def download_pdf(year: int, number: str, output_dir: Path = DEFAULT_OUTPUT_DIR) -> Path | None:
    """Download a single PDF and return local file path when successful."""
    normalized_number = validate_inputs(year=year, number=number)
    pdf_url = build_pdf_url(year=year, number=normalized_number)
    target_path = output_dir / f"{year}{normalized_number}.pdf"
    logger.info("Starting download from %s", pdf_url)

    with requests.Session() as session:
        for attempt in range(1, MAX_DOWNLOAD_ATTEMPTS + 1):
            try:
                with session.get(
                    pdf_url,
                    timeout=REQUEST_TIMEOUT_SECONDS,
                    stream=True,
                ) as response:
                    if response.status_code == 404:
                        logger.warning("PDF not found (404): %s", pdf_url)
                        return None
                    response.raise_for_status()
                    write_response_to_file(response=response, target_path=target_path)
                    logger.info("Download completed: %s", target_path)
                    return target_path
            except requests.exceptions.RequestException as exc:
                should_retry = attempt < MAX_DOWNLOAD_ATTEMPTS
                logger.warning(
                    "Download attempt %d/%d failed for %s: %s",
                    attempt,
                    MAX_DOWNLOAD_ATTEMPTS,
                    pdf_url,
                    exc,
                )
                if not should_retry:
                    logger.error("Download failed after retries for %s", pdf_url)
                    return None
                sleep_seconds = RETRY_BACKOFF_SECONDS * attempt
                time.sleep(sleep_seconds)
            except OSError as exc:
                logger.error("Failed to write file %s: %s", target_path, exc)
                return None

    return None


def parse_args() -> argparse.Namespace:
    """Parse CLI arguments for PDF downloader."""
    parser = argparse.ArgumentParser(
        description="Download Official Gazette PDF by year and issue number."
    )
    parser.add_argument("--year", type=int, required=True, help="Publication year, e.g. 2024.")
    parser.add_argument(
        "--number",
        type=str,
        required=True,
        help="Issue number as provided by archive URL, e.g. 001.",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=DEFAULT_OUTPUT_DIR,
        help="Output directory for downloaded PDFs (default: data/raw).",
    )
    return parser.parse_args()


def main() -> int:
    """Entrypoint for downloader command-line execution."""
    configure_logging()
    args = parse_args()
    downloaded_path = download_pdf(
        year=args.year,
        number=args.number,
        output_dir=args.output_dir,
    )

    if downloaded_path is None:
        logger.info("No file saved.")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
