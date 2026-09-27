"""Кэш курсов ЦБ РФ: один JSON-файл на день, чтобы не дёргать API при каждом запуске.

- Курсы на конкретную дату (`--date`) кэшируются бессрочно — архив не меняется.
- Свежие курсы (без `--date`) действительны только в день загрузки: ЦБ РФ
  обновляет их в течение дня. На следующий день кэш перезапрашивается.
- Если API недоступен, а свежего кэша нет, используется устаревший кэш
  с предупреждением — утилита остаётся работоспособной без сети.
"""

from __future__ import annotations

import json
import os
from datetime import date
from pathlib import Path

from .api import ApiError, Rate, RatesSheet, fetch_rates
from .output import print_warning

LATEST_FILE = "latest.json"


def get_cache_dir() -> Path:
    """Каталог кэша: переменная CBR_CACHE_DIR или ~/.cache/currency_converter."""
    override = os.environ.get("CBR_CACHE_DIR")
    return Path(override) if override else Path.home() / ".cache" / "currency_converter"


def _day_file(cache_dir: Path, day: date) -> Path:
    return cache_dir / f"rates-{day.isoformat()}.json"


def _encode(sheet: RatesSheet, fetched_on: date) -> dict:
    return {
        "date": sheet.date.isoformat(),
        "fetched_on": fetched_on.isoformat(),
        "rates": {
            code: {"nominal": rate.nominal, "value": rate.value, "name": rate.name}
            for code, rate in sheet.rates.items()
        },
    }


def _decode(payload: dict) -> RatesSheet:
    return RatesSheet(
        date=date.fromisoformat(payload["date"]),
        rates={
            code: Rate(
                char_code=code,
                nominal=int(item["nominal"]),
                value=float(item["value"]),
                name=item["name"],
            )
            for code, item in payload["rates"].items()
        },
    )


def load_cached(day: date | None, *, allow_stale: bool = False) -> RatesSheet | None:
    """Читает кэш; возвращает None, если файла нет, он повреждён или устарел."""
    path = _day_file(get_cache_dir(), day) if day else get_cache_dir() / LATEST_FILE
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    if day is None and not allow_stale and payload.get("fetched_on") != date.today().isoformat():
        return None
    try:
        return _decode(payload)
    except (KeyError, TypeError, ValueError):
        return None


def save_cached(sheet: RatesSheet, requested_day: date | None) -> None:
    """Сохраняет курсы; latest.json обновляется только для запросов без даты,
    чтобы исторический запрос не подменил собой свежие курсы."""
    cache_dir = get_cache_dir()
    try:
        cache_dir.mkdir(parents=True, exist_ok=True)
        payload = json.dumps(_encode(sheet, fetched_on=date.today()), ensure_ascii=False)
        _day_file(cache_dir, requested_day or sheet.date).write_text(payload, encoding="utf-8")
        if requested_day is None:
            (cache_dir / LATEST_FILE).write_text(payload, encoding="utf-8")
    except OSError:
        pass  # кэш не критичен: недоступный диск не должен ломать утилиту


def get_rates(day: date | None, use_cache: bool = True) -> RatesSheet:
    """Возвращает курсы: кэш → API → устаревший кэш (с предупреждением)."""
    if use_cache:
        cached = load_cached(day)
        if cached is not None:
            return cached

    try:
        sheet = fetch_rates(day)
    except ApiError as exc:
        stale = load_cached(day, allow_stale=True) if use_cache else None
        if stale is None:
            raise
        print_warning(
            f"ЦБ РФ недоступен ({exc}); использую кэш от {stale.date.strftime('%d.%m.%Y')}"
        )
        return stale

    if use_cache:
        save_cached(sheet, requested_day=day)
    return sheet