"""Логика конвертации валют через рублёвые курсы ЦБ РФ."""

from __future__ import annotations

from decimal import Decimal, InvalidOperation, ROUND_HALF_UP

from .api import ApiError, Rate, RatesSheet

# В таблице ЦБ РФ рубля нет: считаем его курс всегда 1:1.
RUB_RATE = Rate(char_code="RUB", nominal=1, value=1.0, name="Российский рубль")


class CurrencyNotFoundError(Exception):
    """ЦБ РФ не публикует курс указанной валюты."""


def get_rate(sheet: RatesSheet, char_code: str) -> Decimal:
    """Возвращает рублей за 1 единицу валюты.

    api.py уже хранит курс за 1 единицу (VunitRate или Value/Nominal),
    поэтому здесь делить на номинал второй раз не нужно.
    """
    if char_code == "RUB":
        return Decimal(str(RUB_RATE.value))
    rate = sheet.rates.get(char_code)
    if rate is None:
        available = ", ".join(sorted(sheet.rates)) or "нет"
        raise CurrencyNotFoundError(
            f"Валюта {char_code!r} не найдена в справочнике ЦБ РФ. "
            f"Доступные коды: {available}"
        )
    return Decimal(str(rate.value))


def convert(
    sheet: RatesSheet, amount: Decimal, from_code: str, to_code: str
) -> Decimal:
    """Переводит amount из from_code в to_code по перекрёстному курсу через рубль.

    Например USD→EUR: (amount × USD_в_рублях) / EUR_в_рублях.
    """
    rub_amount = amount * get_rate(sheet, from_code)
    return rub_amount / get_rate(sheet, to_code)


def parse_amount(raw: str) -> Decimal:
    """Разбирает сумму; запятая допустима как десятичный разделитель."""
    try:
        amount = Decimal(raw.replace(",", "."))
    except InvalidOperation:
        raise ApiError(f"Неверная сумма: {raw!r}. Ожидается число, например 100 или 100.50")
    if not amount.is_finite() or amount <= 0:
        raise ApiError("Сумма должна быть положительным числом")
    return amount


def validate_code(raw: str, arg_name: str = "код валюты") -> str:
    """Проверяет и нормализует трёхбуквенный код ISO 4217 (usd → USD)."""
    code = raw.strip().upper()
    if not (len(code) == 3 and code.isalpha()):
        raise ApiError(
            f"Неверный код валюты в параметре {arg_name}: {raw!r}. "
            f"Ожидается трёхбуквенный код ISO 4217, например USD"
        )
    return code


def format_amount(value: Decimal | float | int, places: int = 2) -> str:
    """Форматирует число: заданное число знаков, пробелы между разрядами."""
    if not isinstance(value, Decimal):
        value = Decimal(str(value))
    quantum = Decimal(1).scaleb(-places)
    quantized = value.quantize(quantum, rounding=ROUND_HALF_UP)
    integer, _, frac = f"{quantized:f}".partition(".")
    grouped = f"{int(integer):,}".replace(",", " ")
    return f"{grouped}.{frac}" if frac else grouped