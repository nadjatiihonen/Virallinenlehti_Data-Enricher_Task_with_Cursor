from datetime import date
from unittest.mock import Mock

import pytest
from pydantic import ValidationError

from src.extractor import (
    TapahtumaTyyppi,
    YritysTapahtuma,
    YritysTapahtumaLista,
    extract_events_from_text,
)


def test_y_tunnus_validation_accepts_valid_format() -> None:
    event = YritysTapahtuma(
        tapahtuma_tyyppi=TapahtumaTyyppi.KONKURSSIN_ALKAMINEN,
        y_tunnus="1234567-8",
        yrityksen_nimi="Testiyritys Oy",
        tapahtuman_pvm=date(2024, 1, 31),
        lahdetiedosto="2024001.pdf",
        sivunumero=5,
    )
    assert event.y_tunnus == "1234567-8"


@pytest.mark.parametrize(
    "invalid_y_tunnus",
    [
        "12345678",
        "1234567-A",
        "123456-7",
        "ABCDEFG-H",
        "",
    ],
)
def test_y_tunnus_validation_rejects_invalid_formats(invalid_y_tunnus: str) -> None:
    with pytest.raises(ValidationError):
        YritysTapahtuma(
            tapahtuma_tyyppi=TapahtumaTyyppi.KONKURSSIN_ALKAMINEN,
            y_tunnus=invalid_y_tunnus,
            yrityksen_nimi="Testiyritys Oy",
            tapahtuman_pvm=date(2024, 1, 31),
            lahdetiedosto="2024001.pdf",
            sivunumero=5,
        )


def test_extract_events_from_text_with_mocked_openai_response() -> None:
    expected_event = YritysTapahtuma(
        tapahtuma_tyyppi=TapahtumaTyyppi.KONKURSSIN_ALKAMINEN,
        y_tunnus="1234567-8",
        yrityksen_nimi="Konkurssi Testi Oy",
        tapahtuman_pvm=date(2024, 2, 1),
        lahdetiedosto="2024001.pdf",
        sivunumero=2,
    )
    mocked_response = YritysTapahtumaLista(tapahtumat=[expected_event])

    mocked_client = Mock()
    mocked_client.chat.completions.create.return_value = mocked_response

    events = extract_events_from_text(
        client=mocked_client,
        text="Konkurssi alkaminen 1234567-8 Konkurssi Testi Oy",
        source_file="2024001.pdf",
        page_number=2,
    )

    assert events == [expected_event]
    mocked_client.chat.completions.create.assert_called_once()
