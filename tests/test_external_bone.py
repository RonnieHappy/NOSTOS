import nibabel as nib
import numpy as np

from nostos.validation.external_bone import validate_bone_subset


def test_external_bone_receipt_uses_matched_reference(tmp_path):
    data = tmp_path / "data"
    data.mkdir()
    mask = np.zeros((20, 20, 20), dtype=np.int16)
    mask[5:15, 5:15, 5:15] = 127
    affine = np.diag((0.02, 0.02, 0.02, 1.0))
    segmentation = data / "BMLPL_TEST_17_SEG_SUB.nii"
    reference = data / "BMLPL_TEST_17_SEG_SUB_DT_THICK_CONVERT.nii"
    nib.save(nib.Nifti1Image(mask, affine), segmentation)
    reference_values = np.full(mask.shape, 0.01, dtype=float)
    reference_values[mask > 0] = 0.2
    nib.save(nib.Nifti1Image(reference_values, affine), reference)
    payload = validate_bone_subset(data, tmp_path / "output")
    assert payload["summary"]["n_volumes"] == 1
    assert payload["dataset"]["doi"] == "10.5281/zenodo.11061947"
    assert payload["validity"]["status"] == "preliminary_external_validation"
