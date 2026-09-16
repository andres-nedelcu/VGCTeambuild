"""Showdown ID normalization. Every ingest module calls to_id() before writing to staging."""

import re

_NON_ALNUM = re.compile(r"[^a-z0-9]")


def to_id(name: str | None) -> str | None:
    """'Floette-Eternal' -> 'floetteeternal', 'Mr. Rime' -> 'mrrime'."""
    if name is None:
        return None
    return _NON_ALNUM.sub("", name.lower())


# TODO(Phase 0): forme / Mega resolution once the rule is logged in DECISIONS.md
