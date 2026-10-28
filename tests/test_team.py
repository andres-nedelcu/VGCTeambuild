"""Which team the app lands on, and the ordering that decides it.

The sidebar selectbox takes the first row `list_pastes` returns, so that ordering
is the difference between opening the tool on the team just loaded and opening it
on whichever paste_id happens to sort first.
"""

import pytest

from vgc.db import session
from vgc.team import list_pastes


@pytest.fixture(scope="module")
def pastes():
    rows = list_pastes()
    if len(rows) < 2:
        pytest.skip("needs two loaded pastes to have an order at all")
    return rows


def test_pastes_are_listed_newest_first(pastes):
    """paste_id order is a hex hash, so the newest team could land anywhere in the
    list — including last. The app offers the first row by default."""
    with session() as con:
        loaded = dict(con.execute(
            "select paste_id, max(loaded_at) from my_team group by paste_id").fetchall())

    stamps = [loaded[pid] for pid, _name, _mons in pastes]
    assert stamps == sorted(stamps, reverse=True)


def test_every_listed_paste_carries_its_members(pastes):
    for _pid, _name, mons in pastes:
        assert mons and all(mons)
