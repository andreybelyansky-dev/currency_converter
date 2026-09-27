"""Диалоговый режим: программа по очереди запрашивает параметры конвертации.

Запускается, когда не передано ни одного позиционного аргумента:
    python main.py                          # локально
    docker run -it --rm currency-converter  # в Docker (нужен TTY)

Неверный ввод переспрашивается; пустой ввод на первом вопросе или на вопросе
о повторе завершает работу. Конец ввода (EOF) в Docker без -it обрабатывается
подсказкой, а не падением.
"""

from __future__ import annotations

from decimal import Decimal
from typing import Callable

from .api import ApiError
from .cache import get_rates
from .output import console, print_error, print_result, print_warning
from .rates import CurrencyNotFoundError, convert, parse_amount, validate_code

EXIT_OK = 0
EXIT_ERROR = 1

YES_ANSWERS = {"да", "д", "y", "yes", "1"}
NO_ANSWERS = {"", "нет", "н", "n", "no", "0"}

TTY_HINT = (
    "Диалогу нужен ввод с клавиатуры (TTY). В Docker запускайте с -it: "
    "docker run -it --rm currency-converter"
)


def _ask(prompt: str, input_fn: Callable[[], str]) -> str:
    console.print(f"[bold cyan]{prompt}[/bold cyan]")
    return input_fn().strip()  # EOFError/KeyboardInterrupt обрабатывает run_interactive


def _ask_currency(
    sheet, prompt: str, *, allow_exit: bool, input_fn: Callable[[], str]
) -> str | None:
    """Спрашивает код валюты, переспрашивая при неверном вводе.

    Возвращает None, если allow_exit и пользователь нажал Enter (выход).
    """
    while True:
        raw = _ask(prompt, input_fn)
        if not raw:
            if allow_exit:
                return None
            print_warning("Пустой ввод. Повторите.")
            continue
        try:
            code = validate_code(raw, "код валюты")
        except ApiError as exc:
            print_warning(str(exc))
            continue
        if code != "RUB" and code not in sheet.rates:
            print_warning(f"Валюты {code} нет в справочнике ЦБ РФ. Список кодов: python main.py --list")
            continue
        return code


def _ask_amount(input_fn: Callable[[], str]) -> Decimal:
    while True:
        raw = _ask("Сколько пересчитываем (число, например 100 или 100,50):", input_fn)
        if not raw:
            print_warning("Пустой ввод. Повторите.")
            continue
        try:
            return parse_amount(raw)
        except ApiError as exc:
            print_warning(str(exc))


def _ask_repeat(input_fn: Callable[[], str]) -> bool:
    while True:
        raw = _ask("Ещё одна конвертация? (да/нет, Enter — нет):", input_fn).lower()
        if raw in YES_ANSWERS:
            return True
        if raw in NO_ANSWERS:
            return False
        print_warning("Ответьте «да» или «нет» (пустой ввод — нет).")


def run_interactive(input_fn: Callable[[], str] = input) -> int:
    """Диалоговый цикл: параметры → результат → вопрос о повторе."""
    try:
        sheet = get_rates(None)

        while True:
            from_code = _ask_currency(
                sheet,
                "Из какой валюты (код, например USD; пусто — выход):",
                allow_exit=True,
                input_fn=input_fn,
            )
            if from_code is None:
                console.print("[dim]Готово.[/dim]")
                return EXIT_OK

            to_code = _ask_currency(
                sheet, "В какую валюту (код, например RUB):",
                allow_exit=False, input_fn=input_fn,
            )
            amount = _ask_amount(input_fn)
            result = convert(sheet, amount, from_code, to_code)
            print_result(sheet, amount, from_code, to_code, result)

            if not _ask_repeat(input_fn):
                console.print("[dim]Готово.[/dim]")
                return EXIT_OK
    except EOFError:
        print_warning(TTY_HINT)
        return EXIT_ERROR
    except KeyboardInterrupt:
        console.print("[dim]Прервано пользователем.[/dim]")
        return EXIT_OK
    except (ApiError, CurrencyNotFoundError) as exc:
        print_error(str(exc))
        return EXIT_ERROR