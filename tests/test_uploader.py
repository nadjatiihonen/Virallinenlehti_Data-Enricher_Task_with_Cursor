from pathlib import Path
from unittest.mock import Mock, patch

import pandas as pd
import requests

from src.uploader import save_csv_fallback, upload_rows


@patch("src.uploader.time.sleep", return_value=None)
@patch("src.uploader.requests.Session")
def test_upload_rows_retries_then_succeeds(
    mock_session_cls: Mock,
    _mock_sleep: Mock,
) -> None:
    response_retry = Mock()
    response_retry.status_code = 503
    response_retry.text = "temporary"

    response_ok = Mock()
    response_ok.status_code = 201
    response_ok.text = "created"

    session = Mock()
    session.post.side_effect = [response_retry, response_ok]
    session.__enter__ = Mock(return_value=session)
    session.__exit__ = Mock(return_value=False)
    mock_session_cls.return_value = session

    report = upload_rows(
        records=[{"sivunumero": 1, "yrityksen_nimi": "Testi Oy"}],
        api_url="https://example.test/events",
        token="token",
    )

    assert len(report["successful_rows"]) == 1
    assert len(report["failed_rows"]) == 0
    assert session.post.call_count == 2


@patch("src.uploader.time.sleep", return_value=None)
@patch("src.uploader.requests.Session")
def test_upload_rows_fails_after_retries(
    mock_session_cls: Mock,
    _mock_sleep: Mock,
) -> None:
    session = Mock()
    session.post.side_effect = requests.RequestException("network down")
    session.__enter__ = Mock(return_value=session)
    session.__exit__ = Mock(return_value=False)
    mock_session_cls.return_value = session

    report = upload_rows(
        records=[{"sivunumero": 1, "yrityksen_nimi": "Testi Oy"}],
        api_url="https://example.test/events",
        token="token",
    )

    assert len(report["successful_rows"]) == 0
    assert len(report["failed_rows"]) == 1
    assert report["failed_rows"][0]["status_code"] is None


def test_save_csv_fallback_creates_file(tmp_path: Path) -> None:
    target_csv = tmp_path / "fallback.csv"
    rows = [{"sivunumero": 2, "yrityksen_nimi": "Fallback Oy"}]

    result = save_csv_fallback(rows, csv_path=target_csv)

    assert result == target_csv
    dataframe = pd.read_csv(target_csv)
    assert len(dataframe.index) == 1
