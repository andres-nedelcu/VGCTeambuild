"""The team store: files under data/teams/, one JSON per team.

These are the guarantees the app leans on — that a saved team reads back exactly,
that the picker opens on the most recent one, that a variant points at its parent,
and that validation refuses a broken team before it reaches disk.

Writes go to a tmp_path store, never the real one, so running the suite can never
touch a team you are actually using.
"""

from __future__ import annotations

import json

import pytest

from vgc.team import (MAX_SLOTS, Member, Team, _read, get, list_teams, load_team,
                      save, slugify, teams_dir, unique_id, validate, variant_of)
import vgc.team as team_mod


@pytest.fixture
def store(tmp_path, monkeypatch):
    """Point the store at a temporary directory for the duration of one test."""
    monkeypatch.setattr(team_mod, "teams_dir", lambda: tmp_path)
    return tmp_path


def a_team(team_id="probe", name="Probe", **kw) -> Team:
    members = [Member(slot=i, pokemon_id="rillaboom", item_id="miracleseed",
                      ability_id="grassysurge", nature="Adamant",
                      investment={"unit": "sp", "values": {"hp": 32, "atk": 32},
                                  "total": 64},
                      moves=["grassyglide", "fakeout", "woodhammer", "protect"])
               for i in range(1, 3)]
    return Team(id=team_id, name=name, members=members, **kw)


def test_a_saved_team_reads_back_identically(store):
    saved = save(a_team())
    back = get("probe")
    assert back.name == saved.name
    assert [m.pokemon_id for m in back.members] == [m.pokemon_id for m in saved.members]
    assert back.members[0].investment == saved.members[0].investment
    assert back.members[0].moves == saved.members[0].moves


def test_investment_survives_as_a_dict_not_a_string(store):
    """my_team handed back a JSON string and `sp_from_investment` had to parse it.
    Files hold the real object, and the rest of the app must keep working either
    way — so this pins which one the store produces."""
    save(a_team())
    assert isinstance(get("probe").members[0].investment, dict)


def test_teams_are_listed_newest_modified_first(store):
    save(a_team("older", "Older", created_at="2026-01-01T00:00:00",
                modified_at="2026-01-01T00:00:00"), touch=False)
    save(a_team("newer", "Newer", created_at="2026-02-01T00:00:00",
                modified_at="2026-02-01T00:00:00"), touch=False)
    assert [t.id for t in list_teams()] == ["newer", "older"]


def test_saving_touches_the_timestamp_and_migrating_does_not(store):
    stamped = save(a_team(created_at="2020-01-01T00:00:00",
                          modified_at="2020-01-01T00:00:00"), touch=False)
    assert stamped.modified_at == "2020-01-01T00:00:00"
    again = save(stamped)
    assert again.modified_at > stamped.modified_at
    assert again.created_at == "2020-01-01T00:00:00"


def test_a_variant_points_back_at_its_parent(store):
    parent = save(a_team("parent", "Parent"))
    child = save(variant_of(parent))
    assert child.derived_from == "parent"
    assert child.id != parent.id
    assert [m.pokemon_id for m in child.members] == [m.pokemon_id for m in parent.members]


def test_deleting_removes_only_that_team(store):
    save(a_team("keep", "Keep"))
    save(a_team("drop", "Drop"))
    team_mod.delete("drop")
    assert [t.id for t in list_teams()] == ["keep"]
    with pytest.raises(LookupError):
        get("drop")


def test_an_unreadable_file_does_not_take_the_picker_down(store):
    save(a_team("good", "Good"))
    (store / "broken.json").write_text("{not json")
    assert [t.id for t in list_teams()] == ["good"]


def test_save_is_atomic_leaving_no_temp_file(store):
    save(a_team())
    assert [p.name for p in store.iterdir()] == ["probe.json"]


def test_unique_id_does_not_collide(store):
    save(a_team("probe", "Probe"))
    assert unique_id("Probe", taken={"probe"}) == "probe-2"


@pytest.mark.parametrize("name,expected", [
    ("Team Mogbla", "team-mogbla"),
    ("Untitled 5 (OTS)", "untitled-5-ots"),
    ("  ", "team"),
    ("🔥🔥🔥", "team"),
])
def test_slugify(name, expected):
    assert slugify(name) == expected


def test_validate_refuses_an_unknown_move():
    """The check that kept scripts/load_paste.py honest, now shared with the app so
    neither route can write something the other would refuse."""
    bad = [Member(slot=1, pokemon_id="rillaboom", item_id=None,
                  ability_id="grassysurge", moves=["notamove"])]
    problems, _ = validate(bad)
    assert any("notamove" in p for p in problems)


def test_validate_accepts_a_real_saved_team():
    from helpers import full_team_id
    tid = full_team_id()
    if tid is None:
        pytest.skip("no six-member team saved")
    problems, _ = validate(load_team(tid))
    assert problems == []


def test_validate_refuses_more_than_six(store):
    many = a_team().members * 4
    problems, _ = validate(many)
    assert any(str(MAX_SLOTS) in p for p in problems)
