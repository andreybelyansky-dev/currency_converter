"""Тесты логики конвертации и разбора XML ЦБ РФ (без обращений к сети)."""

import xml.etree.ElementTree as ET
from datetime import date
from decimal import Decimal

import pytest

from converter.api import ApiError, parse_user_date, parse_xml
from converter.rates import CurrencyNotFoundError, convert, format_amount, get_rate

SAMPLE_XML = """<?xml version="1.0" encoding="windows-1251"?>
<ValCurs Date="25.09.2026" name="Foreign Currency Market">
  <Valute ID="R01035"><NumCode>826</NumCode><CharCode>GBP</CharCode>
    <Nominal>1</Nominal><Name>Фунт стерлингов</Name>
    <Value>112,6274</Value><VunitRate>112,6274</VunitRate></Valute>
  <Valute ID="R01235"><NumCode>840</NumCode><CharCode>USD</CharCode>
    <Nominal>1</Nominal><Name>Доллар США</Name>
    <Value>74,5346</Value><VunitRate>74,5346</VunitRate></Valute>
  <Valute ID="R01239"><NumCode>978</NumCode><CharCode>EUR</CharCode>
    <Nominal>1</Nominal><Name>Евро</Name>
    <Value>87,4210</Value><VunitRate>87,4210</VunitRate></Valute>
  <Valute ID="R01150"><NumCode>704</NumCode><CharCode>VND</CharCode>
    <Nominal>10000</Nominal><Name>Вьетнамских донгов</Name>
    <Value>33,1210</Value></Valute>
</ValCurs>"""


@pytest.fixture()
def sheet():
    return parse_xml(SAMPLE_XML.encode("windows-1251"))


class TestParseXml:
    def test_date_from_response(self, sheet):
        assert sheet.date == date(2026, 9, 25)

    def test_known_currencies(self, sheet):
        assert set(sheet.rates) == {"GBP", "USD", "EUR", "VND"}

    def test_vunit_rate_used(self, sheet):
        assert sheet.rates["USD"].value == pytest.approx(74.5346)

    def test_value_divided_by_nominal(self, sheet):
        # VND: 33,1210 за 10 000 единиц → 0,0033121 за 1
        assert sheet.rates["VND"].value == pytest.approx(0.0033121)

    def test_broken_xml_raises(self):
        with pytest.raises(ApiError):
            parse_xml(b"<ValCurs Date=")


class TestConvert:
    def test_usd_to_rub(self, sheet):
        result = convert(sheet, Decimal("100"), "USD", "RUB")
        assert float(result) == pytest.approx(7453.46)

    def test_rub_to_usd(self, sheet):
        result = convert(sheet, Decimal("7453.46"), "RUB", "USD")
        assert float(result) == pytest.approx(100)

    def test_cross_rate_usd_to_eur(self, sheet):
        result = convert(sheet, Decimal("100"), "USD", "EUR")
        expected = Decimal("100") * Decimal("74.5346") / Decimal("87.4210")
        assert float(result) == pytest.approx(float(expected), rel=1e-9)

    def test_same_currency(self, sheet):
        result = convert(sheet, Decimal("42"), "EUR", "EUR")
        assert float(result) == pytest.approx(42)

    def test_nominal_greater_than_one(self, sheet):
        # VND: 0,0033121 RUB за 1 ед. → 10 000 VND = 33,121 RUB.
        # Защита от повторного деления на номинал.
        result = convert(sheet, Decimal("10000"), "VND", "RUB")
        assert float(result) == pytest.approx(33.121)

    def test_rub_to_nominal_currency(self, sheet):
        result = convert(sheet, Decimal("33.121"), "RUB", "VND")
        assert float(result) == pytest.approx(10000)

    def test_unknown_currency_raises(self, sheet):
        with pytest.raises(CurrencyNotFoundError):
            convert(sheet, Decimal("1"), "XYZ", "USD")

    def test_get_rate_rub_is_one(self, sheet):
        assert get_rate(sheet, "RUB") == 1


class TestFormatAmount:
    def test_groups_thousands(self):
        assert format_amount(Decimal("7453.46")) == "7 453.46"

    def test_rounds_half_up(self):
        assert format_amount(Decimal("1.005")) == "1.01"

    def test_places(self):
        assert format_amount(Decimal("74.5346"), places=4) == "74.5346"


class TestParseUserDate:
    def test_iso_format(self):
        assert parse_user_date("2025-01-15") == date(2025, 1, 15)

    def test_invalid_format_raises(self):
        with pytest.raises(ApiError):
            parse_user_date("15.01.2025")