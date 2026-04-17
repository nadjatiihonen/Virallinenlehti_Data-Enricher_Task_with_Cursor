import json
from pathlib import Path

import pandas as pd

from src.exporter import export_events_to_excel


def test_export_events_to_excel_writes_expected_columns(tmp_path: Path) -> None:
    input_json = tmp_path / "events.json"
    output_excel = tmp_path / "staging.xlsx"
    payload = [
        {
            "tapahtuma_tyyppi": "konkurssin_alkaminen",
            "y_tunnus": "1234567-8",
            "yrityksen_nimi": "Testi Oy",
            "tapahtuman_pvm": "2024-01-02",
            "lahdetiedosto": "2024001.pdf",
            "sivunumero": 10,
            "extra_field": "ignored",
        }
    ]
    input_json.write_text(json.dumps(payload), encoding="utf-8")

    result_path = export_events_to_excel(
        input_json_path=input_json,
        output_excel_path=output_excel,
    )

    assert result_path == output_excel
    dataframe = pd.read_excel(output_excel)
    assert list(dataframe.columns) == [
        "tapahtuma_tyyppi",
        "y_tunnus",
        "yrityksen_nimi",
        "tapahtuman_pvm",
        "lahdetiedosto",
        "sivunumero",
    ]
    assert len(dataframe.index) == 1
