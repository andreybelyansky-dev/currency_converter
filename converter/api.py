"""Клиент официального API ЦБ РФ (XML_daily.asp).

Источник: https://cbr.ru/development/SXML/
Ответ приходит в кодировке windows-1251, парсим из байтов —
ElementTree сам прочитает кодировку из XML-декларации.
"""

from __future__ import annotations

import xml.etree.ElementTree as ET
from dataclasses import dataclass
from datetime import date, datetime

import requests

CBR_XML_URL = "https://www.cbr.ru/scripts/XML_daily.asp"
REQUEST_TIMEOUT = 10  # секунд
USER_DATE_FORMAT = "%Y-%m-%d"  # формат даты, который понимает пользователь


class ApiError(Exception):
    """Ошибка запроса к API ЦБ РФ или разбора его ответа."""


@dataclass(frozen=True)
class Rate:
    """Курс одной валюты: value рублей за 1 единицу (VunitRate или Value/Nominal).

    nominal — справочное поле из XML (сколько единиц входит в номинал).
    """

    char_code: str
    nominal: int
    value: float
    name: str


@dataclass(frozen=True)
class RatesSheet:
    """Балансовые курсы ЦБ РФ на дату (Date из ответа, а не из запроса)."""

    date: date
    rates: dict[str, Rate]


def parse_user_date(raw: str) -> date:
    """Разбирает дату в формате ISO (ГГГГ-ММ-ДД)."""
    try:
        return datetime.strptime(raw, USER_DATE_FORMAT).date()
    except ValueError as exc:
        raise ApiError(
            f"Неверный формат даты: {raw!r}. Ожидается ГГГГ-ММ-ДД, например 2025-01-15"
        ) from exc


def _parse_decimal(raw: str) -> float:
    """ЦБ РФ использует запятую как десятичный разделитель."""
    return float(raw.replace(",", "."))


def parse_xml(content: bytes) -> RatesSheet:
    """Разбирает XML-ответ ЦБ РФ в RatesSheet."""
    try:
        root = ET.fromstring(content)
    except ET.ParseError as exc:
        raise ApiError(f"Не удалось разобрать XML-ответ ЦБ РФ: {exc}") from exc

    raw_date = root.attrib.get("Date", "")
    try:
        sheet_date = datetime.strptime(raw_date, "%d.%m.%Y").date()
    except ValueError as exc:
        raise ApiError(f"Неизвестный формат даты в ответе ЦБ РФ: {raw_date!r}") from exc

    rates: dict[str, Rate] = {}
    for valute in root.findall("Valute"):
        char_code = valute.findtext("CharCode", default="").strip().upper()
        if not char_code:
            continue
        nominal = int(valute.findtext("Nominal", default="1"))
        # VunitRate — курс за 1 единицу; в старых ответах его нет,
        # тогда делим Value (за nominal) на nominal.
        vunit = valute.findtext("VunitRate")
        if vunit:
            value = _parse_decimal(vunit)
        else:
            value = _parse_decimal(valute.findtext("Value", default="0")) / nominal
        rates[char_code] = Rate(
            char_code=char_code,
            nominal=nominal,
            value=value,
            name=valute.findtext("Name", default="").strip(),
        )

    if not rates:
        raise ApiError("Ответ ЦБ РФ не содержит курсов валют")
    return RatesSheet(date=sheet_date, rates=rates)


def fetch_rates(day: date | None = None, session: requests.Session | None = None) -> RatesSheet:
    """Запрашивает курсы ЦБ РФ; для прошедших дат — архив по параметру date_req."""
    params = {}
    if day is not None:
        params["date_req"] = day.strftime("%d/%m/%Y")

    try:
        response = (session or requests).get(
            CBR_XML_URL, params=params, timeout=REQUEST_TIMEOUT
        )
        response.raise_for_status()
    except requests.RequestException as exc:
        target = f" на {day.isoformat()}" if day else ""
        raise ApiError(f"Ошибка запроса к ЦБ РФ{target}: {exc}") from exc

    return parse_xml(response.content)