"""Тесты кэша курсов: tmp_path как каталог кэша, сеть не используется."""

import json
from datetime import date, timedelta

import pytest

from converter import cache
from converter.api import ApiError, Rate, RatesSheet

TODAY = date(2026, 9, 26)


@pytest.fixture(autouse=True)
def cache_dir(tmp_path, monkeypatch):
    monkeypatch.setenv("CBR_CACHE_DIR", str(tmp_path))
    return tmp_path


def make_sheet(day: date = TODAY) -> RatesSheet:
    return RatesSheet(
        date=day,
        rates={
            "USD": Rate(char_code="USD", nominal=1, value=74.5346, name="Доллар США"),
            "VND": Rate(char_code="VND", nominal=10000, value=0.0033121, name="Вьетнамских донгов"),
        },
    )


class TestRoundtrip:
    def test_save_and_load_for_date(self, cache_dir):
        cache.save_cached(make_sheet(), requested_day=date(2025, 1, 15))
        loaded = cache.load_cached(date(2025, 1, 15))
        assert loaded.date == TODAY
        assert loaded.rates["USD"].value == 74.5346
        assert loaded.rates["VND"].nominal == 10000
        assert loaded.rates["USD"].name == "Доллар США"

    def test_save_without_date_writes_latest(self, cache_dir):
        cache.save_cached(make_sheet(), requested_day=None)
        assert (cache_dir / "latest.json").exists()
        assert cache.load_cached(None).date == TODAY

    def test_save_with_date_does_not_touch_latest(self, cache_dir):
        cache.save_cached(make_sheet(), requested_day=date(2025, 1, 15))
        assert not (cache_dir / "latest.json").exists()

    def test_missing_cache_returns_none(self, cache_dir):
        assert cache.load_cached(date(2025, 1, 15)) is None

    def test_corrupt_cache_returns_none(self, cache_dir):
        (cache_dir / f"rates-{TODAY.isoformat()}.json").write_text("{oops", encoding="utf-8")
        assert cache.load_cached(TODAY) is None


class TestFreshness:
    def test_latest_is_fresh_only_on_fetch_day(self, cache_dir):
        cache.save_cached(make_sheet(), requested_day=None)

        # Сделаем кэш "вчерашним"
        path = cache_dir / "latest.json"
        payload = json.loads(path.read_text(encoding="utf-8"))
        payload["fetched_on"] = (TODAY - timedelta(days=1)).isoformat()
        path.write_text(json.dumps(payload), encoding="utf-8")

        assert cache.load_cached(None) is None
        assert cache.load_cached(None, allow_stale=True) is not None

    def test_day_cache_has_no_staleness(self, cache_dir):
        # Архивная дата не устаревает
        cache.save_cached(make_sheet(), requested_day=date(2020, 1, 1))
        path = cache_dir / "rates-2020-01-01.json"
        payload = json.loads(path.read_text(encoding="utf-8"))
        payload["fetched_on"] = "2000-01-01"
        path.write_text(json.dumps(payload), encoding="utf-8")
        assert cache.load_cached(date(2020, 1, 1)) is not None


class TestGetRates:
    def test_fetches_once_then_uses_cache(self, monkeypatch):
        calls = []

        def fake_fetch(day=None, session=None):
            calls.append(day)
            return make_sheet()

        monkeypatch.setattr(cache, "fetch_rates", fake_fetch)
        cache.get_rates(None)
        cache.get_rates(None)
        assert calls == [None]

    def test_stale_cache_fallback_on_api_error(self, monkeypatch, cache_dir):
        # Предварительно кладём устаревший кэш
        path = cache_dir / "latest.json"
        payload = cache._encode(make_sheet(), fetched_on=TODAY - timedelta(days=1))
        path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")

        def broken_fetch(day=None, session=None):
            raise ApiError("сеть недоступна")

        monkeypatch.setattr(cache, "fetch_rates", broken_fetch)
        sheet = cache.get_rates(None)
        assert sheet.date == TODAY

    def test_api_error_without_cache_raises(self, monkeypatch):
        def broken_fetch(day=None, session=None):
            raise ApiError("сеть недоступна")

        monkeypatch.setattr(cache, "fetch_rates", broken_fetch)
        with pytest.raises(ApiError):
            cache.get_rates(None)

    def test_no_cache_forces_fetch(self, monkeypatch):
        calls = []

        def fake_fetch(day=None, session=None):
            calls.append(day)
            return make_sheet()

        monkeypatch.setattr(cache, "fetch_rates", fake_fetch)
        cache.save_cached(make_sheet(), requested_day=None)
        cache.get_rates(None, use_cache=False)
        assert len(calls) == 1