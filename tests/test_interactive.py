"""Тесты диалогового режима и маршрутизации CLI (ввод подменяется, сеть не используется)."""

from datetime import date

import pytest

from converter import interactive
from converter.api import Rate, RatesSheet

EXIT_OK = interactive.EXIT_OK
EXIT_ERROR = interactive.EXIT_ERROR


@pytest.fixture
def sheet():
    return RatesSheet(
        date=date(2026, 9, 26),
        rates={
            "USD": Rate(char_code="USD", nominal=1, value=84.3414, name="Доллар США"),
            "EUR": Rate(char_code="EUR", nominal=1, value=95.8709, name="Евро"),
        },
    )


def make_input(lines):
    """input_fn, отдающий строки по очереди; по исчерпании — EOFError (как у input())."""
    iterator = iter(lines)

    def input_fn():
        try:
            return next(iterator)
        except StopIteration:
            raise EOFError

    return input_fn


@pytest.fixture(autouse=True)
def rates(monkeypatch, sheet):
    monkeypatch.setattr(interactive, "get_rates", lambda day=None, use_cache=True: sheet)


class TestDialog:
    def test_happy_path(self, capsys):
        rc = interactive.run_interactive(make_input(["USD", "RUB", "100", ""]))
        assert rc == EXIT_OK
        assert "8 434.14" in capsys.readouterr().out

    def test_case_and_spaces_accepted(self, capsys):
        rc = interactive.run_interactive(make_input([" usd ", "rub", "1", "нет"]))
        assert rc == EXIT_OK

    def test_repeat_loop(self, capsys):
        lines = ["USD", "RUB", "1", "да", "EUR", "USD", "1", "нет"]
        rc = interactive.run_interactive(make_input(lines))
        assert rc == EXIT_OK
        out = capsys.readouterr().out
        assert "84.3414" in out
        assert "1.1367" in out  # EUR→USD: 95.8709 / 84.3414 ≈ 1.1367

    def test_invalid_code_reasks(self, capsys):
        rc = interactive.run_interactive(make_input(["XYZ", "usd", "RUB", "100", "нет"]))
        assert rc == EXIT_OK
        assert "нет в справочнике" in capsys.readouterr().err

    def test_invalid_format_reasks(self, capsys):
        rc = interactive.run_interactive(make_input(["USDD", "USD", "RUB", "100", "нет"]))
        assert rc == EXIT_OK
        assert "Неверный код валюты" in capsys.readouterr().err

    def test_bad_amount_reasks(self, capsys):
        rc = interactive.run_interactive(make_input(["USD", "RUB", "abc", "100", "нет"]))
        assert rc == EXIT_OK
        assert "Неверная сумма" in capsys.readouterr().err

    def test_empty_amount_reasks(self, capsys):
        rc = interactive.run_interactive(make_input(["USD", "RUB", "", "100", "нет"]))
        assert rc == EXIT_OK

    def test_empty_first_question_exits(self):
        assert interactive.run_interactive(make_input([""])) == EXIT_OK

    def test_enter_on_repeat_exits(self):
        assert interactive.run_interactive(make_input(["USD", "RUB", "5", ""])) == EXIT_OK

    def test_eof_at_start_hints_tty(self, capsys):
        rc = interactive.run_interactive(make_input([]))
        assert rc == EXIT_ERROR
        assert "TTY" in capsys.readouterr().err

    def test_eof_mid_dialog_hints_tty(self, capsys):
        rc = interactive.run_interactive(make_input(["USD"]))
        assert rc == EXIT_ERROR
        assert "TTY" in capsys.readouterr().err

    def test_ctrl_c_exits_cleanly(self, capsys):
        def interrupted():
            raise KeyboardInterrupt

        assert interactive.run_interactive(interrupted) == EXIT_OK
        assert "Прервано" in capsys.readouterr().out


class TestMainRouting:
    @pytest.fixture(autouse=True)
    def no_rates_sheet(self, monkeypatch, sheet):
        monkeypatch.setattr("main.get_rates", lambda day=None, use_cache=True: sheet)

    def test_no_args_starts_interactive(self, monkeypatch):
        import main as main_module

        monkeypatch.setattr(main_module, "run_interactive", lambda: 7)
        assert main_module.main([]) == 7

    def test_args_mode_unchanged(self):
        import main as main_module

        assert main_module.main(["USD", "RUB", "100"]) == EXIT_OK

    def test_date_without_args_is_error(self):
        import main as main_module

        assert main_module.main(["--date", "2025-01-15"]) == EXIT_ERROR

    def test_list_with_positional_is_error(self):
        import main as main_module

        assert main_module.main(["--list", "USD"]) == EXIT_ERROR

    def test_partial_args_is_usage_error(self):
        import main as main_module

        assert main_module.main(["USD", "RUB"]) == EXIT_ERROR