from nostos.data.split import participant_split


def test_participant_split_is_complete_disjoint_and_reproducible() -> None:
    participants = [f"{index:03d}" for index in range(1, 91)]
    first = participant_split(participants)
    second = participant_split(participants)

    assert first == second
    assert set(first["train"]).isdisjoint(first["validation"])
    assert set(first["train"]).isdisjoint(first["test"])
    assert set(first["validation"]).isdisjoint(first["test"])
    assert set().union(*map(set, first.values())) == set(participants)
    assert {name: len(ids) for name, ids in first.items()} == {
        "train": 63,
        "validation": 14,
        "test": 13,
    }
