import numpy as np

from nostos.segmentation.pseudo_labels import cluster_proposal


def test_cluster_proposal_separates_two_color_regions() -> None:
    image = np.zeros((64, 64, 3), dtype=np.uint8)
    image[:, :32] = [230, 20, 30]
    image[:, 32:] = [20, 30, 230]
    proposal = cluster_proposal(image, clusters=2, maximum_dimension=64, sample_pixels=4096)
    left = np.bincount(proposal.clusters[:, :32].ravel()).argmax()
    right = np.bincount(proposal.clusters[:, 32:].ravel()).argmax()
    assert left != right
