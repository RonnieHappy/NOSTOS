from nostos.validation.consensus_reliability import _partition


def test_group_partition_is_deterministic_and_binary():
    assert _partition("round_1_42") == _partition("round_1_42")
    assert {_partition(f"group_{i}") for i in range(30)} == {"development", "confirmation"}

