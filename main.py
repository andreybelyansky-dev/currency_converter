#!/usr/bin/env python3
"""Конвертация валют по курсам ЦБ РФ.

Примеры:
    python main.py USD RUB 100
    python main.py EUR USD 50 --date 2025-01-15
    python main.py --list
    python main.py            # диалоговый режим (последовательный ввод)
"""

from __future__ import annotations

import argparse
import sys

from converter.api import ApiError, parse_user_date
from converter.cache import get_rates
from converter.interactive import run_interactive
from converter.output import print_error, print_rates_table, print_result
from converter.rates import CurrencyNotFoundError, convert, parse_amount, validate_code

EXIT_OK = 0
EXIT_ERROR = 1


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="currency-converter",
        description="Конвертация валют по официальным курсам ЦБ РФ. "
        "Без аргументов запускается диалоговый режим.",
    )
    parser.add_argument("from_currency", nargs="?", default=None,
                        help="код валюты, из которой конвертируем (USD)")
    parser.add_argument("to_currency", nargs="?", default=None,
                        help="код валюты, в которую конвертируем (RUB)")
    parser.add_argument("amount", nargs="?", default=None,
                        help="сумма для конвертации (100 или 100.50)")
    parser.add_argument(
        "--date", dest="day", default=None, metavar="ГГГГ-ММ-ДД",
        help="курсы на конкретную дату (по умолчанию — последние)",
    )
    parser.add_argument(
        "--list", action="store_true",
        help="показать курсы всех валют ЦБ РФ за 1 единицу в рублях",
    )
    parser.add_argument(
        "--no-cache", action="store_true",
        help="игнорировать кэш и запросить ЦБ РФ заново",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    given = [args.from_currency, args.to_currency, args.amount]
    has_any = any(given)
    has_all = all(given)

    if args.list and has_any:
        print_error("С флагом --list позиционные аргументы не используются")
        return EXIT_ERROR

    try:
        if not has_any and not args.list:
            if args.day:
                print_error(
                    "С флагом --date укажите FROM TO AMOUNT. "
                    "Для диалогового режима запускайте без аргументов и флагов."
                )
                return EXIT_ERROR
            return run_interactive()  # EOF и прерывание обрабатываются внутри

        if args.list:
            day = parse_user_date(args.day) if args.day else None
            sheet = get_rates(day, use_cache=not args.no_cache)
            print_rates_table(sheet)
            return EXIT_OK

        if not has_all:
            print_error(
                "Укажите валюту и сумму: FROM TO AMOUNT, либо флаг --list, "
                "либо запустите без аргументов для диалогового режима. "
                "Пример: python main.py USD RUB 100"
            )
            return EXIT_ERROR

        day = parse_user_date(args.day) if args.day else None
        from_code = validate_code(args.from_currency, "from_currency")
        to_code = validate_code(args.to_currency, "to_currency")
        amount = parse_amount(args.amount)

        sheet = get_rates(day, use_cache=not args.no_cache)
        result = convert(sheet, amount, from_code, to_code)
    except ApiError as exc:  # сеть, XML, формат аргументов
        print_error(str(exc))
        return EXIT_ERROR
    except CurrencyNotFoundError as exc:
        print_error(str(exc))
        return EXIT_ERROR

    print_result(sheet, amount, from_code, to_code, result)
    return EXIT_OK


if __name__ == "__main__":
    sys.exit(main())