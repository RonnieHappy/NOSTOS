from pathlib import Path

from scripts.index_wound_healing_collagen_archive import MT_PATTERN, SHG_PATTERN


def test_shg_member_pattern_recovers_independent_animal_key_components() -> None:
    name = (
        "Wound_Healing_Collagen_Dataset/SHG_dataset/SHG_images/"
        "7day/mice12/7day_mice12_image10.png"
    )
    match = SHG_PATTERN.match(name)
    assert match is not None
    assert match.group("day") == "7day"
    assert match.group("animal") == "mice12"


def test_mt_member_pattern_does_not_accept_shg_images() -> None:
    shg = (
        "Wound_Healing_Collagen_Dataset/SHG_dataset/SHG_images/"
        "0day/mice1/0day_mice1_image1.png"
    )
    assert MT_PATTERN.match(shg) is None


def test_patterns_reject_unsafe_nested_member_names() -> None:
    unsafe = (
        "Wound_Healing_Collagen_Dataset/SHG_dataset/SHG_images/"
        "7day/mice1/nested/7day_mice1_image1.png"
    )
    assert SHG_PATTERN.match(unsafe) is None
