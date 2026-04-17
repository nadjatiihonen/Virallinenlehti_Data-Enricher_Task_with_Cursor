import json
import logging
import os
import tempfile
import time
from pathlib import Path
from typing import Any, TypedDict, cast

import pandas as pd
import requests
from dotenv import load_dotenv

INPUT_EXCEL_PATH = Path("data/final/konkurssitiedot_staging.xlsx")
REPORT_PATH = Path("data/final/upload_report.json")
CSV_FALLBACK_PATH = Path("data/final/konkurssitiedot_staging.csv")
REQUEST_TIMEOUT_SECONDS = 30
MAX_UPLOAD_ATTEMPTS = 3
UPLOAD_RETRY_BACKOFF_SECONDS = 1.5

logger = logging.getLogger(__name__)


class UploadRowResult(TypedDict, total=False):
    """Per-row API upload result payload."""

    row_number: int
    status_code: int | None
    response_body: str
    error: str


class UploadReport(TypedDict):
    """Full upload execution report payload."""

    total_rows: int
    successful_rows: list[UploadRowResult]
    failed_rows: list[UploadRowResult]
    mode: str
    reason: str
    csv_path: str
    success_count: int
    failed_count: int


def configure_logging() -> None:
    """Configure module-wide logging format and level."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    )


def load_env_settings() -> dict[str, str]:
    """Load runtime settings from .env file and process environment."""
    load_dotenv()
    return {
        "api_url": os.getenv("YRITYSDATA_API_URL", "").strip(),
        "api_token": os.getenv("YRITYSDATA_API_TOKEN", "").strip(),
    }


def normalize_record(record: dict[str, Any]) -> dict[str, Any]:
    """Normalize one row to JSON-safe values before exporting/uploading."""
    clean: dict[str, Any] = {}
    for key, value in record.items():
        if pd.isna(value):
            clean[key] = None
        elif key == "sivunumero" and value is not None:
            clean[key] = int(value)
        else:
            clean[key] = value
    return clean


def read_excel_rows(excel_path: Path) -> list[dict[str, Any]]:
    """Read staging Excel rows into list of dictionaries."""
    if not excel_path.exists():
        raise FileNotFoundError(f"Excel file not found: {excel_path}")

    dataframe = pd.read_excel(excel_path)
    if dataframe.empty:
        return []
    records = dataframe.to_dict(orient="records")
    return cast(list[dict[str, Any]], records)


def upload_rows(
    records: list[dict[str, Any]],
    api_url: str,
    token: str,
) -> UploadReport:
    """Upload rows one-by-one to target API and return detailed report."""
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    }
    report: UploadReport = {
        "total_rows": len(records),
        "successful_rows": [],
        "failed_rows": [],
        "mode": "api_upload",
        "reason": "",
        "csv_path": "",
        "success_count": 0,
        "failed_count": 0,
    }

    with requests.Session() as session:
        for row_number, record in enumerate(records, start=1):
            payload = normalize_record(record)
            for attempt in range(1, MAX_UPLOAD_ATTEMPTS + 1):
                try:
                    response = session.post(
                        api_url,
                        headers=headers,
                        json=payload,
                        timeout=REQUEST_TIMEOUT_SECONDS,
                    )
                    if 200 <= response.status_code < 300:
                        report["successful_rows"].append(
                            {
                                "row_number": row_number,
                                "status_code": response.status_code,
                            }
                        )
                        logger.info("Uploaded row %d successfully.", row_number)
                        break

                    is_retryable_status = response.status_code in {408, 429, 500, 502, 503, 504}
                    if attempt < MAX_UPLOAD_ATTEMPTS and is_retryable_status:
                        sleep_seconds = UPLOAD_RETRY_BACKOFF_SECONDS * attempt
                        time.sleep(sleep_seconds)
                        continue
                    report["failed_rows"].append(
                        {
                            "row_number": row_number,
                            "status_code": response.status_code,
                            "response_body": response.text,
                        }
                    )
                    logger.warning(
                        "Upload failed for row %d with status %d.",
                        row_number,
                        response.status_code,
                    )
                    break
                except requests.RequestException as exc:
                    if attempt < MAX_UPLOAD_ATTEMPTS:
                        sleep_seconds = UPLOAD_RETRY_BACKOFF_SECONDS * attempt
                        time.sleep(sleep_seconds)
                        continue
                    report["failed_rows"].append(
                        {
                            "row_number": row_number,
                            "status_code": None,
                            "error": str(exc),
                        }
                    )
                    logger.error("Upload request failed for row %d: %s", row_number, exc)
                    break

    return report


def finalize_report(report: UploadReport) -> UploadReport:
    """Populate report counters used for alerting and monitoring."""
    report["success_count"] = len(report["successful_rows"])
    report["failed_count"] = len(report["failed_rows"])
    return report


def save_report(report: UploadReport, report_path: Path = REPORT_PATH) -> Path:
    """Save report payload atomically as JSON file."""
    report_path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        mode="w",
        dir=report_path.parent,
        prefix=f".{report_path.stem}_",
        suffix=".tmp",
        encoding="utf-8",
        delete=False,
    ) as temp_file:
        temp_path = Path(temp_file.name)
        json.dump(report, temp_file, ensure_ascii=False, indent=2)
    temp_path.replace(report_path)
    return report_path


def save_csv_fallback(
    records: list[dict[str, Any]],
    csv_path: Path = CSV_FALLBACK_PATH,
) -> Path:
    """Persist rows as CSV when API endpoint is not configured."""
    normalized = [normalize_record(record) for record in records]
    dataframe = pd.DataFrame(normalized)
    csv_path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        mode="w",
        dir=csv_path.parent,
        prefix=f".{csv_path.stem}_",
        suffix=".tmp",
        encoding="utf-8",
        delete=False,
    ) as temp_file:
        temp_path = Path(temp_file.name)
        dataframe.to_csv(temp_file, index=False, encoding="utf-8")
    temp_path.replace(csv_path)
    return csv_path


def main() -> int:
    """Entrypoint for uploader command-line execution."""
    configure_logging()

    try:
        records = read_excel_rows(INPUT_EXCEL_PATH)
    except Exception as exc:
        logger.error("Initialization failed: %s", exc)
        return 1

    if not records:
        logger.info("No rows to upload from %s", INPUT_EXCEL_PATH)
        report: UploadReport = {
            "total_rows": 0,
            "successful_rows": [],
            "failed_rows": [],
            "mode": "empty_input",
            "reason": "",
            "csv_path": "",
            "success_count": 0,
            "failed_count": 0,
        }
        report_path = save_report(finalize_report(report))
        logger.info("Saved report to %s", report_path)
        return 0

    settings = load_env_settings()
    api_url = settings["api_url"]
    if not api_url:
        csv_path = save_csv_fallback(records)
        fallback_report: UploadReport = {
            "mode": "csv_fallback",
            "reason": "YRITYSDATA_API_URL not set",
            "total_rows": len(records),
            "csv_path": str(csv_path),
            "successful_rows": [],
            "failed_rows": [],
            "success_count": 0,
            "failed_count": 0,
        }
        report_path = save_report(finalize_report(fallback_report))
        logger.info("API URL not set. Saved CSV fallback to %s", csv_path)
        logger.info("Saved report to %s", report_path)
        return 0

    api_token = settings["api_token"]
    if not api_token:
        logger.error("Missing YRITYSDATA_API_TOKEN while API URL is configured.")
        return 1

    report = upload_rows(records=records, api_url=api_url, token=api_token)
    report = finalize_report(report)
    report_path = save_report(report)

    success_count = report["success_count"]
    failed_count = report["failed_count"]
    logger.info(
        "Upload completed. success=%d failed=%d report=%s",
        success_count,
        failed_count,
        report_path,
    )
    return 0 if failed_count == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
