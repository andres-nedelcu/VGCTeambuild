"""Your teams: a file-backed store under data/teams/, one JSON file per team.

WHY NOT THE WAREHOUSE. `my_team` used to live in DuckDB beside the marts, and it was
the only hand-authored table in a warehouse of derived data — the one thing that
would not survive deleting the file and rerunning the pipeline. That misplacement is
what made the app rigid: DuckDB allows exactly one writer, so an app that could save
a team would block `refresh.py`, and the app therefore had to be read-only, so spread
edits lived in session state and died on a browser refresh.

Teams are not derived data. They are the user's own input, they are tiny, and they
need to be writable from the app. So they are files, and the single-writer rule goes
on protecting the thing it was written for.

WHY STRUCTURED, NOT THE PASTE TEXT. A Showdown paste is lossy in both directions:
`vgc.edit.to_paste` drops nicknames, gender never had a column to land in, and IVs
are parsed and discarded. A store that silently strips a field on every save is the
wrong foundation, so the sets are held structurally and the paste is regenerated on
demand by `to_paste`.

VARIANTS. A variant is an ordinary team with `derived_from` set to the id it was
copied from. No nesting, no special case: "save as variant" is a copy with a new id,
which is what comparing two spreads actually needs.
"""

from __future__ import annotations

import json
import os
import re
import unicodedata
from dataclasses import asdict, dataclass, field, replace
from datetime import datetime
from pathlib import Path
from typing import Any, Iterable, Sequence

from vgc import REPO_ROOT
from vgc.db import load_settings, session
from vgc.ids import to_id

SCHEMA = 1
MAX_SLOTS = 6


@dataclass(frozen=True)
class Member:
    slot: int
    pokemon_id: str
    item_id: str | None
    ability_id: str | None
    nickname: str | None = None
    nature: str | None = None
    investment: str | dict | None = None
    moves: list[str] | None = None
    gender: str | None = None


@dataclass(frozen=True)
class Team:
    id: str
    name: str
    members: list[Member]
    source: dict[str, Any] = field(default_factory=dict)
    derived_from: str | None = None
    created_at: str | None = None
    modified_at: str | None = None

    @property
    def pokemon_ids(self) -> list[str]:
        return [m.pokemon_id for m in sorted(self.members, key=lambda m: m.slot)]


def teams_dir() -> Path:
    """Where teams live. Created on demand; gitignored, because a team is secret
    until the event is over and this repository is public."""
    path = REPO_ROOT / load_settings().get("teams_dir", "data/teams")
    path.mkdir(parents=True, exist_ok=True)
    return path


# --- identity -------------------------------------------------------------------

def slugify(name: str) -> str:
    """A filename-safe, readable id. Falls back to 'team' for names with nothing
    usable in them, which is what an all-emoji paste title leaves behind."""
    text = unicodedata.normalize("NFKD", name or "")
    text = text.encode("ascii", "ignore").decode("ascii").lower()
    text = re.sub(r"[^a-z0-9]+", "-", text).strip("-")
    return text[:48] or "team"


def unique_id(name: str, taken: Iterable[str] | None = None) -> str:
    taken = set(taken if taken is not None else (t.id for t in list_teams()))
    base = slugify(name)
    if base not in taken:
        return base
    for n in range(2, 1000):
        candidate = f"{base}-{n}"
        if candidate not in taken:
            return candidate
    raise ValueError(f"Could not find a free id for {name!r}")


# --- reading --------------------------------------------------------------------

def normalise_investment(inv: str | dict | None) -> dict | None:
    """One shape for investment, whichever route wrote it.

    A paste arrives with `total` because the parser computes one; the in-app editor
    builds a Spread and does not. Nothing reads `total` today, which is exactly why
    the two shapes could drift unnoticed — so both are normalised on the way in and
    on the way out, and the store never holds two spellings of the same thing.
    """
    if inv is None:
        return None
    if isinstance(inv, str):
        inv = json.loads(inv)
    values = {k: int(v) for k, v in (inv.get("values") or {}).items() if v}
    return {"unit": (inv.get("unit") or "sp").lower(), "values": values,
            "total": sum(values.values())}


def _member(row: dict) -> Member:
    return Member(
        slot=row["slot"], pokemon_id=row["pokemon_id"], item_id=row.get("item_id"),
        ability_id=row.get("ability_id"), nickname=row.get("nickname"),
        nature=row.get("nature"),
        investment=normalise_investment(row.get("investment")),
        moves=list(row.get("moves") or []), gender=row.get("gender"),
    )


def _read(path: Path) -> Team:
    data = json.loads(path.read_text())
    members = [_member(m) for m in data.get("members", [])]
    members.sort(key=lambda m: m.slot)
    return Team(
        id=data.get("id") or path.stem, name=data.get("name") or path.stem,
        members=members, source=data.get("source") or {},
        derived_from=data.get("derived_from"),
        created_at=data.get("created_at"), modified_at=data.get("modified_at"),
    )


def list_teams() -> list[Team]:
    """Every saved team, most recently modified first.

    Newest first because the team you just saved or imported is the one you want to
    look at; a slug is alphabetical, i.e. arbitrary with respect to that.
    """
    out = []
    for path in teams_dir().glob("*.json"):
        try:
            out.append(_read(path))
        except (json.JSONDecodeError, KeyError, TypeError) as e:
            # One unreadable file must not take the picker down with it.
            print(f"warning: skipping {path.name}: {e}")
    out.sort(key=lambda t: (t.modified_at or "", t.id), reverse=True)
    return out


def get(team_id: str) -> Team:
    path = teams_dir() / f"{team_id}.json"
    if not path.exists():
        raise LookupError(f"No team {team_id!r} in {teams_dir()}")
    return _read(path)


def load_team(team_id: str) -> list[Member]:
    """The members alone. Kept because every visual takes a list of Members and has
    no business knowing about team metadata."""
    return get(team_id).members


# --- writing --------------------------------------------------------------------

def save(team: Team, *, touch: bool = True) -> Team:
    """Write atomically, so an interrupted save cannot leave a half-written team.

    Returns the team as stored, with `modified_at` set. `touch=False` keeps the
    team's existing timestamp, which is what a migration wants: it is copying teams,
    not modifying them, and stamping them all with one import time would flatten the
    ordering `list_teams` reads.
    """
    now = datetime.now().isoformat(timespec="seconds")
    stamped = replace(team, created_at=team.created_at or now,
                      modified_at=(team.modified_at or team.created_at or now)
                      if not touch else now)
    payload = {
        "schema": SCHEMA, "id": stamped.id, "name": stamped.name,
        "source": stamped.source, "derived_from": stamped.derived_from,
        "created_at": stamped.created_at, "modified_at": stamped.modified_at,
        "members": [{**asdict(m), "investment": normalise_investment(m.investment)}
                    for m in sorted(stamped.members, key=lambda m: m.slot)],
    }
    path = teams_dir() / f"{stamped.id}.json"
    tmp = path.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(payload, ensure_ascii=False, indent=1))
    os.replace(tmp, path)
    return stamped


def delete(team_id: str) -> None:
    path = teams_dir() / f"{team_id}.json"
    if not path.exists():
        raise LookupError(f"No team {team_id!r} to delete")
    path.unlink()


def variant_of(team: Team, name: str | None = None) -> Team:
    """A copy with a new id, pointing back at what it came from.

    The whole point of spread work is comparing two builds of the same team, so this
    is a first-class operation rather than something to rebuild by hand.
    """
    label = name or f"{team.name} (variant)"
    return Team(id=unique_id(label), name=label, members=list(team.members),
                source=dict(team.source), derived_from=team.id)


# --- validation -----------------------------------------------------------------

def validate(members: Sequence[Member]) -> tuple[list[str], list[str]]:
    """(problems, warnings) for a team about to be saved.

    Nothing is written while a reference does not resolve — the rule
    scripts/load_paste.py has enforced since the beginning, moved here so the app
    gets it too rather than reimplementing a weaker copy.
    """
    with session() as con:
        pokemon = {r[0]: r[1:] for r in con.execute(
            "SELECT pokemon_id, base_species_id, is_mega, is_nonstandard FROM dim_pokemon").fetchall()}
        moves = {r[0] for r in con.execute("SELECT move_id FROM dim_move").fetchall()}
        items = {r[0]: r[1:] for r in con.execute(
            "SELECT item_id, is_mega_stone, mega_forme_id FROM dim_item").fetchall()}
        abilities = {to_id(r[0]) for r in con.execute(
            "SELECT DISTINCT unnest(abilities) FROM dim_pokemon").fetchall()}

    problems, warnings = [], []
    for m in sorted(members, key=lambda m: m.slot):
        label = f"slot {m.slot} {m.pokemon_id}"
        if m.pokemon_id not in pokemon:
            problems.append(f"{label}: species not in dim_pokemon")
        elif pokemon[m.pokemon_id][2]:
            warnings.append(f"{label}: flagged {pokemon[m.pokemon_id][2]} in Showdown's Champions data")
        if m.item_id and m.item_id not in items:
            problems.append(f"{label}: item {m.item_id!r} not in dim_item")
        if m.ability_id and m.ability_id not in abilities:
            problems.append(f"{label}: ability {m.ability_id!r} unknown")
        if not m.ability_id:
            warnings.append(f"{label}: no ability line")
        for move in (m.moves or []):
            if move not in moves:
                problems.append(f"{label}: move {move!r} not in dim_move")
        if len(m.moves or []) != 4:
            warnings.append(f"{label}: {len(m.moves or [])} moves")
        inv = m.investment
        if isinstance(inv, str):
            inv = json.loads(inv)
        if inv and (inv.get("unit") or "").lower() not in ("sp", "ev"):
            problems.append(f"{label}: unknown investment unit {inv.get('unit')!r}")
        # A Mega stone that belongs to another species is the one build error the
        # dim tables cannot catch on their own, since both halves resolve fine.
        if m.item_id in items and items[m.item_id][0]:
            forme = items[m.item_id][1]
            mine = (pokemon.get(m.pokemon_id) or (None,))[0]
            if forme and forme in pokemon and pokemon[forme][0] != mine:
                problems.append(f"{label}: {m.item_id} does not belong to this species")
    if len(members) > MAX_SLOTS:
        problems.append(f"{len(members)} members, {MAX_SLOTS} allowed")
    return problems, warnings


# --- building from a paste ------------------------------------------------------

def members_from_sets(sets: Sequence[dict]) -> list[Member]:
    """Turn vgc.ingest.pokepaste.parse output into Members, ids normalised."""
    out = []
    for slot, s in enumerate(sets, 1):
        out.append(Member(
            slot=slot, pokemon_id=to_id(s["species"]),
            item_id=to_id(s["item"]) or None if s.get("item") else None,
            ability_id=to_id(s["ability"]) or None if s.get("ability") else None,
            nickname=s.get("nickname"), nature=s.get("nature"),
            investment=s.get("investment"),
            moves=[to_id(m) for m in s.get("moves") or []],
            gender=s.get("gender"),
        ))
    return out
