#!/usr/bin/env python3
"""Пример: получить курсы основных валют из другого Python-скрипта.

Пакет converter работает как библиотека: get_rates() возвращает словарь
курсов (с кэшем на день и fallback при сбое сети) — то же, что видит CLI.
"""

from __future__ import annotations

import os
import sys

# Если скрипт лежит вне проекта — добавляем путь к проекту
# (при запуске из корня проекта или после pip-установки пакета это не нужно)
PROJECT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_DIR not in sys.path:
    sys.path.insert(0, PROJECT_DIR)

from converter.cache import get_rates  # noqa: E402
from converter.rates import get_rate  # noqa: E402  (Decimal-курс за 1 единицу)

# "Основные" валюты — настройте список под себя
MAJOR_CURRENCIES = ("USD", "EUR", "CNY", "GBP", "JPY", "CHF", "TRY", "KZT")


def main() -> int:
    sheet = get_rates(None)  # None = последние курсы; можно передать дату
    print(f"Курсы ЦБ РФ на {sheet.date:%d.%m.%Y} (руб. за 1 единицу):\n")

    for code in MAJOR_CURRENCIES:
        rate = sheet.rates.get(code)
        if rate is None:
            print(f"  {code}: нет в справочнике ЦБ РФ")
            continue
        # rate.value — float из XML; для денежных расчётов берите Decimal
        # через get_rate(sheet, code)
        print(f"  {code}: {get_rate(sheet, code):>10.4f}  {rate.name}")

    # Пример расчёта: сколько рублей в 100 USD
    from decimal import Decimal

    usd_rub = get_rate(sheet, "USD")
    print(f"\n  100 USD = {(Decimal('100') * usd_rub):.2f} RUB")
    return 0


if __name__ == "__main__":
    sys.exit(main())