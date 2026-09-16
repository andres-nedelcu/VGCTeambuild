import pytest

from vgc.ingest.pokepaste import paste_id, parse

PASTE = (
    "Lady (Indeedee-F) (F) @ Psychic Seed  \r\n"
    "Ability: Psychic Surge  \r\n"
    "Level: 50  \r\n"
    "EVs: 32 HP / 2 Def / 32 SpD  \r\n"
    "Relaxed Nature  \r\n"
    "IVs: 0 Spe  \r\n"
    "- Follow Me  \r\n"
    "- Trick Room  \r\n"
    "- Helping Hand  \r\n"
    "- Protect  \r\n"
    "\r\n"
    "Garchomp @ Garchompite Z  \r\n"
    "Ability: Rough Skin  \r\n"
    "EVs: 2 HP / 32 Atk / 32 Spe  \r\n"
    "Jolly Nature  \r\n"
    "- Dragon Claw  \r\n"
    "- Earthquake / Stomping Tantrum  \r\n"
    "- Rock Slide  \r\n"
    "- Protect  \r\n"
    "\r\n"
    "Incineroar (M) @ Sitrus Berry  \r\n"
    "Ability: Intimidate  \r\n"
    "EVs: 252 HP / 4 Atk / 252 SpD  \r\n"
    "Careful Nature  \r\n"
    "- Fake Out  \r\n"
)


def test_paste_id_forms():
    assert paste_id("https://pokepast.es/5C46F9EC443664CB") == "5c46f9ec443664cb"
    assert paste_id("https://pokepast.es/5c46f9ec443664cb/raw") == "5c46f9ec443664cb"
    assert paste_id("5c46f9ec443664cb") == "5c46f9ec443664cb"
    with pytest.raises(ValueError):
        paste_id("https://pokepast.es/")


def test_parse_header_and_fields():
    lady, chomp, roar = parse(PASTE)
    assert (lady["nickname"], lady["species"], lady["gender"], lady["item"]) == ("Lady", "Indeedee-F", "F", "Psychic Seed")
    assert lady["ability"] == "Psychic Surge" and lady["nature"] == "Relaxed"
    assert lady["ivs"] == {"spe": 0}
    assert lady["moves"] == ["Follow Me", "Trick Room", "Helping Hand", "Protect"]
    assert chomp["nickname"] is None and chomp["species"] == "Garchomp" and chomp["item"] == "Garchompite Z"
    assert chomp["moves"][1] == "Earthquake"
    assert roar["gender"] == "M" and roar["species"] == "Incineroar"


def test_investment_units():
    lady, chomp, roar = parse(PASTE)
    assert lady["investment"] == {"unit": "sp", "values": {"hp": 32, "def": 2, "spd": 32}, "total": 66}
    assert chomp["investment"]["unit"] == "sp"
    assert roar["investment"]["unit"] == "ev"
