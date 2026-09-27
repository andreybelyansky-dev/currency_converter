"""Цветной вывод результата с помощью rich."""

from __future__ import annotations

from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from .api import RatesSheet
from .rates import format_amount

console = Console()
err_console = Console(stderr=True)


def print_result(
    sheet: RatesSheet,
    amount: float,
    from_code: str,
    to_code: str,
    result: float,
) -> None:
    """Печатает результат конвертации и справку о курсе."""
    title = f"[bold cyan]Конвертация валют · ЦБ РФ[/bold cyan]"
    table = Table.grid(padding=(0, 2))
    table.add_column(justify="right", style="dim")
    table.add_column()

    table.add_row(
        "Результат",
        f"[bold green]{format_amount(amount)} {from_code} "
        f"= [reverse]{format_amount(result)} {to_code}[/reverse][/bold green]",
    )
    table.add_row(
        "Курс",
        f"1 {from_code} = {format_amount(result / amount if amount else 0, 4)} {to_code}",
    )
    table.add_row("Данные ЦБ РФ", f"на {sheet.date.strftime('%d.%m.%Y')}")

    console.print(Panel(table, title=title, border_style="cyan"))


def print_warning(message: str) -> None:
    """Печатает предупреждение в stderr жёлтым."""
    err_console.print(f"[bold yellow]Предупреждение:[/bold yellow] {message}")


def print_rates_table(sheet: RatesSheet) -> None:
    """Печатает таблицу всех курсов ЦБ РФ за 1 единицу в рублях."""
    table = Table(
        title=f"[bold cyan]Курсы ЦБ РФ на {sheet.date.strftime('%d.%m.%Y')}[/bold cyan]",
        border_style="cyan",
    )
    table.add_column("Код", style="bold cyan")
    table.add_column("Валюта")
    table.add_column("Курс, RUB за 1 ед.", justify="right", style="green")
    for code in sorted(sheet.rates):
        rate = sheet.rates[code]
        text = format_amount(rate.value, 4)
        if text == "0.0000" and rate.value > 0:  # очень мелкие курсы (IRR и т.п.)
            text = format_amount(rate.value, 8)
        table.add_row(code, rate.name or "—", text)
    console.print(table)


def print_error(message: str) -> None:
    """Печатает ошибку в stderr красным."""
    err_console.print(f"[bold red]Ошибка:[/bold red] {message}")