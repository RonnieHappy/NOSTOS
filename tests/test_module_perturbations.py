from nostos.validation.module_perturbations import run_module_perturbation_matrix


def test_module_perturbation_matrix_writes_complete_receipt(tmp_path):
    payload = run_module_perturbation_matrix(tmp_path)
    assert payload["summary"]["required_tests"] >= 20
    assert {item["module"] for item in payload["results"]} == {"tensor", "hessian", "geometry", "network", "spatial"}
    assert (tmp_path / "module_perturbation_matrix.json").is_file()
    spatial = [item for item in payload["results"] if item["module"] == "spatial"]
    assert all(item["observed_anisotropy_ratio"] > 1 for item in spatial)
