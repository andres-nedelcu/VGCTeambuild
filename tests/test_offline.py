"""The app must work with no network at all.

This is not a general principle, it is a dated requirement: the tool gets used on
two 3-hour flights, and a visual that silently needs the internet is worthless
there. Everything the app renders comes from the local warehouse and local sprite
files; the only modules allowed to reach the network are under vgc.ingest, which
scripts/ calls and the app never imports.

The check works by making socket creation raise, then driving the read path behind
all four tabs. If any of it ever grows a network call, this fails.
"""

import socket

import pytest

from vgc import regulations
from vgc.defense import defense_matrix, flagged_types, mega_comparison, summarize
from vgc.freshness import sources as data_sources
from vgc.megas import load_dex, mega_options, resolve_team
from vgc.metafilter import MetaFilter, extent, sample_size
from vgc.offense import attackers, clear_cache as clear_offense_cache
from vgc.offense import coverage_matrix, holes, team_best, threats
from vgc.pressure import rank as rank_threats
from vgc.speed import clear_cache as clear_speed_cache
from vgc.speed import matchup, meta_speed, team_speeds
from vgc.sprites import data_uri
from vgc.team import list_pastes, load_team

REG = "M-C"


@pytest.fixture
def no_network(monkeypatch):
    """Make any socket use raise. Caches are cleared first so nothing is served
    from a value that was fetched before the block went up."""
    clear_offense_cache()
    clear_speed_cache()
    load_dex.cache_clear()

    def deny(*args, **kwargs):
        raise AssertionError("the app attempted a network call")

    for name in ("socket", "create_connection", "getaddrinfo", "gethostbyname"):
        monkeypatch.setattr(socket, name, deny)
    yield
    clear_offense_cache()
    clear_speed_cache()
    load_dex.cache_clear()


def test_the_block_actually_blocks(no_network):
    """Guards every test below, which would pass vacuously if this did nothing."""
    with pytest.raises(AssertionError, match="network call"):
        socket.create_connection(("example.com", 80))


def test_all_four_tabs_render_offline(no_network):
    pastes = list_pastes()
    if not pastes:
        pytest.skip("no teams loaded")
    paste_id = next(pid for pid, _name, mons in pastes if len(mons) > 1)

    dex = load_dex()
    team = load_team(paste_id)
    formes = resolve_team(team, None)
    assert dex and team and formes

    # Sidebar
    assert regulations.current()
    assert mega_options(team) is not None
    filt = MetaFilter()
    assert sample_size(REG, filt) > 0
    assert extent(REG).events > 0
    assert data_sources(REG)

    # Tab 1: defensive grid
    matrix = defense_matrix(formes)
    summary = summarize(matrix)
    assert not matrix.empty and flagged_types(summary) is not None
    assert mega_comparison(team, [f.slot for f in formes]) is not None

    # Tab 2: offensive coverage
    meta = threats(REG, 20, filt)
    assert meta
    cover = coverage_matrix(attackers(team, formes), meta)
    assert not cover.empty and team_best(cover) is not None and holes(cover) is not None

    # Tab 3: speed tiers
    speeds = team_speeds(team, formes)
    df = meta_speed(REG, 20, filt)
    assert speeds and not df.empty
    assert all(matchup(speeds[0].speed, row) for row in df.itertuples())

    # Tab 4: threat list
    assert rank_threats(REG, formes, 20, filt)


def test_sprites_resolve_offline(no_network):
    """Sprites are the newest thing that could have been hotlinked. They are not."""
    meta = threats(REG, 20)
    if not meta:
        pytest.skip("marts not built")
    rendered = [data_uri(t.forme_id) for t in meta]
    assert all(uri and uri.startswith("data:image/png;base64,") for uri in rendered)
