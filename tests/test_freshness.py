"""Data freshness reporting, used by refresh.py and the app header."""

from datetime import date, datetime

import pytest

from vgc.freshness import Source, sources


def test_age_is_measured_from_the_data_date_not_the_load_time():
    s = Source("x", date(2026, 9, 10), datetime(2026, 9, 18, 12), "")
    assert s.age_days(date(2026, 9, 18)) == 8


def test_static_sources_have_no_age():
    assert Source("static", None, None, "").age_days(date(2026, 9, 18)) is None
    assert Source("static", None, None, "").age_label(date(2026, 9, 18)) == "static"


@pytest.mark.parametrize("as_of,expected", [
    (date(2026, 9, 10), "8d old"),
    (date(2026, 9, 18), "today"),
    (date(2026, 9, 19), "today"),  # CBD's newest day can lead local time; never "-1d old"
])
def test_age_label_never_reads_negative(as_of, expected):
    assert Source("x", as_of, None, "").age_label(date(2026, 9, 18)) == expected


def test_every_source_is_reported_against_the_real_warehouse():
    try:
        found = sources("M-C")
    except FileNotFoundError:
        pytest.skip("warehouse not built")
    assert [s.name for s in found] == [
        "Limitless tournaments", "Champions Battle Data", "Showdown static data"]
    assert all(s.detail for s in found)  # never blank, even with nothing landed
