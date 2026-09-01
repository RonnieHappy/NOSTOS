from nostos.validation.selective_shg_transfer import _cluster_interval


def test_cluster_interval_is_bounded():
    rows = [
        {"source_group": f"g{i // 2}", "accepted": True, "invalid": i % 7 == 0}
        for i in range(40)
    ]
    low, high = _cluster_interval(rows, draws=500)
    assert 0 <= low <= high <= 1

