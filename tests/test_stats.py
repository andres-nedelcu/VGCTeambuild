import json
import pytest
from vgc.stats import calc_stat, nature_mod, sp_from_investment

# In-game values (paste b58a4fb249fb3cbf)
@pytest.mark.parametrize("name,base,sp,nature,expected", [
    ("Sneasler", 120, 32, "Adamant", 172),
    ("Pelipper", 65, 32, "Modest", 117),
    ("Basculegion-M", 78, 32, "Jolly", 143),
    ("Indeedee-F", 85, 0, "Calm", 105),
])
def test_speed_in_game(name, base, sp, nature, expected):
    assert calc_stat(base, sp, nature_mod(nature, "spe"), stat="spe") == expected

# Formula-derived (Showdown parity), swap for in-game values when available
def test_minus_speed_floors():
    assert calc_stat(85, 0, 0.9, stat="spe") == 94       # 105 * 0.9 = 94.5

def test_hp_ignores_nature():
    assert calc_stat(60, 0, 1.1, stat="hp") == 135

def test_nature_mod():
    assert nature_mod("Jolly", "spe") == 1.1
    assert nature_mod("jolly", "spa") == 0.9
    assert nature_mod("Adamant", "spe") == 1.0
    assert nature_mod("Hardy", "atk") == 1.0
    assert nature_mod(None, "spe") == 1.0
    with pytest.raises(ValueError):
        nature_mod("Spicy", "spe")

def test_level_other_than_50_rejected():
    with pytest.raises(ValueError):
        calc_stat(100, 0, level=100)

def test_ev_label_within_sp_limits_is_sp():
    inv = {"unit": "ev", "values": {"HP": 2, "Atk": 32, "Spe": 32}, "total": 66}
    sp = sp_from_investment(inv)
    assert sp["spe"] == 32 and sp["def"] == 0 and sum(sp.values()) == 66

def test_json_string_accepted():
    inv = json.dumps({"unit": "sp", "values": {"spe": 10}, "total": 10})
    assert sp_from_investment(inv)["spe"] == 10

def test_real_evs_rejected():
    with pytest.raises(ValueError, match="mainline EVs"):
        sp_from_investment({"unit": "ev", "values": {"Atk": 252, "Spe": 252}})

def test_sp_over_limit_rejected():
    with pytest.raises(ValueError):
        sp_from_investment({"unit": "sp", "values": {"spe": 33}})
    with pytest.raises(ValueError):
        sp_from_investment({"unit": "sp", "values": {"atk": 32, "spe": 32, "hp": 3}})
