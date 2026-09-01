from scripts.extract_wound_healing_collagen_metadata import is_allowed


def test_metadata_whitelist_accepts_only_declared_roles() -> None:
    assert is_allowed("Wound_Healing_Collagen_Dataset/README.md")
    assert is_allowed("Wound_Healing_Collagen_Dataset/SHG_dataset/SHG_image_metadata.csv")
    assert is_allowed(
        "Wound_Healing_Collagen_Dataset/SHG_dataset/"
        "SHG_animal_level_cross_validation_splits/fold1_test.txt"
    )


def test_metadata_whitelist_rejects_images_and_unrelated_files() -> None:
    assert not is_allowed(
        "Wound_Healing_Collagen_Dataset/SHG_dataset/SHG_images/"
        "0day/mice1/0day_mice1_image1.png"
    )
    assert not is_allowed("Wound_Healing_Collagen_Dataset/SHG_dataset/notes.txt")
    assert not is_allowed("../README.md")
