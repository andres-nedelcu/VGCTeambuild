from vgc.ids import to_id


def test_to_id_examples():
    assert to_id("Floette-Eternal") == "floetteeternal"
    assert to_id("Mr. Rime") == "mrrime"
    assert to_id("Salamence-Mega") == "salamencemega"
    assert to_id(None) is None
