from pathlib import Path
from unittest.mock import Mock, patch

import requests

from src.downloader import build_pdf_url, download_pdf


def test_build_pdf_url() -> None:
    assert (
        build_pdf_url(year=2024, number="001")
        == "https://www.virallinenlehti.fi/fi/journal/pdf/2024001.pdf"
    )


@patch("src.downloader.time.sleep", return_value=None)
@patch("src.downloader.write_response_to_file")
@patch("src.downloader.requests.Session")
def test_download_pdf_retries_and_succeeds(
    mock_session_cls: Mock,
    mock_write_response: Mock,
    _mock_sleep: Mock,
    tmp_path: Path,
) -> None:
    response_error = Mock()
    response_error.status_code = 503
    response_error.raise_for_status.side_effect = requests.exceptions.RequestException(
        "temporary fail"
    )
    response_error.__enter__ = Mock(return_value=response_error)
    response_error.__exit__ = Mock(return_value=False)

    response_ok = Mock()
    response_ok.status_code = 200
    response_ok.raise_for_status.return_value = None
    response_ok.__enter__ = Mock(return_value=response_ok)
    response_ok.__exit__ = Mock(return_value=False)

    session = Mock()
    session.get.side_effect = [response_error, response_ok]
    session.__enter__ = Mock(return_value=session)
    session.__exit__ = Mock(return_value=False)
    mock_session_cls.return_value = session

    result = download_pdf(year=2024, number="001", output_dir=tmp_path)

    assert result == tmp_path / "2024001.pdf"
    assert session.get.call_count == 2
    mock_write_response.assert_called_once()
