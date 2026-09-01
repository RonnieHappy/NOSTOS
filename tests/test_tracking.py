import numpy as np

from nostos.features.tracking import extract_objects, track_instance_series


def disk(labels: np.ndarray, center: tuple[int, int], radius: int, value: int) -> None:
    yy, xx = np.mgrid[: labels.shape[0], : labels.shape[1]]
    labels[(yy - center[0]) ** 2 + (xx - center[1]) ** 2 <= radius**2] = value


def test_source_labels_are_discarded_and_motion_is_calibrated() -> None:
    first = np.zeros((64, 64), dtype=np.uint16); second = np.zeros_like(first)
    disk(first, (20, 20), 4, 99); disk(first, (45, 42), 5, 3)
    disk(second, (22, 17), 4, 7); disk(second, (44, 44), 5, 88)
    objects, _ = extract_objects(first, 0)
    assert [obj.local_id for obj in objects] == [1, 2]
    result = track_instance_series(np.stack((first, second)), spacing=(2.0, 4.0), temporal_spacing=2.0, use_flow=False)
    assert result["status"] == "valid"
    assert len(result["edges"]) == 2
    first_edge = result["edges"][0]
    assert first_edge["displacement_y"] == 4.0
    assert first_edge["displacement_x"] == -12.0


def test_division_edges_are_explicit() -> None:
    first = np.zeros((64, 64), dtype=np.uint16); second = np.zeros_like(first)
    disk(first, (32, 32), 7, 1)
    disk(second, (29, 28), 5, 10); disk(second, (35, 36), 5, 20)
    result = track_instance_series(np.stack((first, second)), spacing=(1.0, 1.0), temporal_spacing=1.0, use_flow=False)
    assert len(result["edges"]) == 2
    assert {edge["edge_type"] for edge in result["edges"]} == {"division"}


def test_empty_transition_abstains() -> None:
    result = track_instance_series(np.zeros((2, 32, 32), dtype=np.uint16), spacing=(1.0, 1.0), temporal_spacing=1.0, use_flow=False)
    assert result["status"] == "abstain"
    assert result["abstentions"][0]["code"] == "FRAME_WITHOUT_VALID_OBJECTS"
