"""Brief 6.2 Phase B: sprite lookup and the fallback composite."""

import base64
import json

from PIL import Image

from vgc import REPO_ROOT
from vgc.ingest.sprites import BADGE_COLOR, MISMATCH_RING, build_fallback
from vgc.sprites import SPRITE_DIR, data_uri, sprite_path

COVERAGE = json.loads((REPO_ROOT / "data" / "sprites" / "coverage.json").read_text())


def test_every_covered_forme_has_a_cached_sprite():
    """Everything Phase A checked — real or fallback — is on disk and committed."""
    for pokemon_id in {**COVERAGE["sprites"], **COVERAGE["missing"]}:
        assert sprite_path(pokemon_id) is not None, f"missing cached sprite for {pokemon_id}"


def test_sprite_path_none_for_unknown_id():
    assert sprite_path("not-a-real-pokemon-id") is None


def test_data_uri_is_a_base64_png():
    uri = data_uri("rillaboom")
    assert uri is not None
    assert uri.startswith("data:image/png;base64,")
    raw = base64.b64decode(uri.split(",", 1)[1])
    assert raw[:8] == b"\x89PNG\r\n\x1a\n"


def test_data_uri_none_for_unknown_id():
    assert data_uri("not-a-real-pokemon-id") is None


def colours(img: Image.Image) -> set:
    """Distinct RGBA pixels. getcolors() rather than the deprecated getdata():
    it is a histogram, so it allocates one entry per colour instead of per pixel."""
    rgba = img.convert("RGBA")
    return {pixel for _count, pixel in rgba.getcolors(maxcolors=rgba.width * rgba.height)}


def test_fallback_sprites_carry_the_gold_badge():
    """Every one of Phase A's 10 misses got a composited stand-in, not a blank."""
    for pokemon_id in COVERAGE["missing"]:
        img = Image.open(SPRITE_DIR / f"{pokemon_id}.png")
        assert BADGE_COLOR in colours(img), f"{pokemon_id} fallback has no badge"


def test_fallback_ring_only_when_typing_differs_from_base():
    """Staraptor-Mega and Barbaracle-Mega are the two whose Mega typing differs
    from the base species the fallback art borrows from; only they get the ring.
    """
    for pokemon_id in COVERAGE["missing"]:
        img = Image.open(SPRITE_DIR / f"{pokemon_id}.png")
        has_ring = MISMATCH_RING in colours(img)
        expected = pokemon_id in {"staraptormega", "barbaraclemega"}
        assert has_ring == expected, f"{pokemon_id}: ring={has_ring}, expected={expected}"


def test_build_fallback_is_deterministic(tmp_path):
    base = tmp_path / "base.png"
    Image.new("RGBA", (96, 96), (10, 20, 30, 255)).save(base)

    out_a = tmp_path / "a.png"
    out_b = tmp_path / "b.png"
    build_fallback(base, out_a, mismatched=False)
    build_fallback(base, out_b, mismatched=True)

    assert out_a.read_bytes() != out_b.read_bytes()
    assert BADGE_COLOR in colours(Image.open(out_a))
    assert MISMATCH_RING in colours(Image.open(out_b))
    assert MISMATCH_RING not in colours(Image.open(out_a))
