import json
import logging
import tempfile
from pathlib import Path
from typing import Any

import pandas as pd

INPUT_JSON_PATH = Path("data/final/yritystapahtumat.json")
OUTPUT_EXCEL_PATH = Path("data/final/konkurssitiedot_staging.xlsx")

logger = logging.getLogger(__name__)


def configure_logging() -> None:
    """Configure module-wide logging format and level."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    )


def read_events(json_path: Path) -> list[dict[str, Any]]:
    """Load event list from JSON; return empty list when missing/invalid."""
    if not json_path.exists():
        logger.warning("Input JSON file does not exist: %s", json_path)
        return []

    with json_path.open("r", encoding="utf-8") as file_handle:
        payload = json.load(file_handle)

    if not isinstance(payload, list):
        logger.error("Expected JSON array in %s", json_path)
        return []
    return payload


def atomic_write_excel(dataframe: pd.DataFrame, output_excel_path: Path) -> None:
    """Write Excel output safely via temporary file replacement."""
    output_excel_path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        mode="wb",
        dir=output_excel_path.parent,
        prefix=f".{output_excel_path.stem}_",
        suffix=".tmp",
        delete=False,
    ) as temp_file:
        temp_path = Path(temp_file.name)
    try:
        dataframe.to_excel(temp_path, index=False)
        temp_path.replace(output_excel_path)
    finally:
        if temp_path.exists():
            temp_path.unlink(missing_ok=True)


def export_events_to_excel(
    input_json_path: Path = INPUT_JSON_PATH,
    output_excel_path: Path = OUTPUT_EXCEL_PATH,
) -> Path:
    """Export validated events to a stable staging Excel file."""
    events = read_events(input_json_path)
    expected_columns = [
        "tapahtuma_tyyppi",
        "y_tunnus",
        "yrityksen_nimi",
        "tapahtuman_pvm",
        "lahdetiedosto",
        "sivunumero",
    ]
    dataframe = pd.DataFrame(events)
    dataframe = dataframe.reindex(columns=expected_columns)
    atomic_write_excel(dataframe=dataframe, output_excel_path=output_excel_path)

    logger.info("Exported %d row(s) to %s", len(dataframe.index), output_excel_path)
    return output_excel_path


def main() -> int:
    """Entrypoint for exporter command-line execution."""
    configure_logging()
    export_events_to_excel()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
