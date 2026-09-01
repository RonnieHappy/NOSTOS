"""Physical-scale-indexed 3D directional response for nanoCT development."""
from __future__ import annotations

import hashlib,itertools,json
from pathlib import Path
import numpy as np
from scipy.ndimage import gaussian_filter

from nostos.validation.human_nanoct_transfer import _case,_normalise,_relative,_sha256,axial_error_3d


def measure_at_scale(volume:np.ndarray,spacing:tuple[float,float,float],scale_um:float)->dict:
    sigma=tuple(scale_um/value for value in spacing)
    smooth=gaussian_filter(np.asarray(volume,dtype=np.float32),sigma=sigma,mode="reflect")
    gradients=np.gradient(smooth,*spacing)
    tensor=np.asarray([[float(np.mean(a*b)) for b in gradients] for a in gradients])
    values,vectors=np.linalg.eigh(tensor);values=np.maximum(values,0);spectrum=values/max(float(values.sum()),np.finfo(float).eps)
    axis=vectors[:,0];axis=axis/max(float(np.linalg.norm(axis)),np.finfo(float).eps)
    return {"scale_um":scale_um,"normalised_eigenvalues":spectrum.tolist(),"principal_structural_axis_zyx":axis.tolist(),
            "anisotropy":float((values[-1]-values[0])/max(float(values.sum()),np.finfo(float).eps))}


def measure_curve(volume:np.ndarray,spacing:tuple[float,float,float],scales:list[float])->list[dict]:
    return [measure_at_scale(volume,spacing,float(scale)) for scale in scales]


def run(data_root:Path,config_path:Path,output:Path)->dict:
    config=json.loads(config_path.read_text(encoding="utf-8"));shape=tuple(config["volume_shape_zyx"]);crop_shape=tuple(config["crop_shape_zyx"])
    spacing=tuple(config["spacing_um_zyx"]);scales=config["response_scales_um"];centers=config["crop_centers_per_axis"];rows=[]
    for path in sorted(data_root.glob("*.raw")):
        volume=np.memmap(path,dtype=np.dtype(config["dtype"]),mode="r",shape=shape)
        for center in itertools.product(centers,repeat=3):
            slices=tuple(slice(c-s//2,c-s//2+s) for c,s in zip(center,crop_shape));clean=_normalise(volume[slices]);reference=measure_curve(clean,spacing,scales)
            crop_id="-".join(map(str,center));seed=int(hashlib.sha256(f"{path.stem}:{crop_id}".encode()).hexdigest()[:8],16)
            for perturbation in config["case_perturbations"]:
                case=_case(clean,perturbation,seed);curve=measure_curve(case,spacing,scales)
                gamma_curve=measure_curve(np.power(np.clip(case,0,1),1.1),spacing,scales)
                permutation=(2,1,0);permuted_curve=measure_curve(np.transpose(case,permutation),tuple(spacing[i] for i in permutation),scales)
                dynamic=float(np.percentile(case,99)-np.percentile(case,1));saturation=float(np.mean((case<=0)|(case>=1)))
                for index,(measurement,truth) in enumerate(zip(curve,reference,strict=True)):
                    adjacent=index+1 if index<len(scales)-1 else index-1;neighbor=curve[adjacent]
                    scale_axis=axial_error_3d(measurement["principal_structural_axis_zyx"],neighbor["principal_structural_axis_zyx"])
                    scale_anisotropy=_relative(neighbor["anisotropy"],measurement["anisotropy"])
                    gamma_axis=axial_error_3d(measurement["principal_structural_axis_zyx"],gamma_curve[index]["principal_structural_axis_zyx"])
                    expected=np.asarray(measurement["principal_structural_axis_zyx"])[list(permutation)]
                    permutation_axis=axial_error_3d(expected,permuted_curve[index]["principal_structural_axis_zyx"])
                    resolved=measurement["scale_um"]/min(spacing)>=config["minimum_supported_voxels_per_scale"]
                    signal=dynamic>=config["minimum_dynamic_range_fraction"] and saturation<=config["maximum_saturation_fraction"]
                    scale_stable=scale_axis<=config["maximum_adjacent_scale_axis_drift_degrees"] and scale_anisotropy<=config["maximum_adjacent_scale_anisotropy_relative_drift"]
                    equivariant=max(gamma_axis,permutation_axis)<=config["maximum_adjacent_scale_axis_drift_degrees"]
                    accepts={"always_emit":True,"endpoint_qc":signal,"nyquist_qc":signal and resolved,
                             "scale_convergence":signal and resolved and scale_stable,
                             "full_contract":signal and resolved and scale_stable and equivariant}
                    axis_error=axial_error_3d(truth["principal_structural_axis_zyx"],measurement["principal_structural_axis_zyx"])
                    anisotropy_error=_relative(measurement["anisotropy"],truth["anisotropy"])
                    rows.append({"case_id":f"{path.stem}:{crop_id}:{perturbation}:{measurement['scale_um']}","volume":path.stem,
                                 "crop_center_zyx":center,"perturbation":perturbation,"scale_um":measurement["scale_um"],"measurement":measurement,
                                 "adjacent_scale_axis_drift_degrees":scale_axis,"adjacent_scale_anisotropy_relative_drift":scale_anisotropy,
                                 "gamma_axis_drift_degrees":gamma_axis,"permutation_axis_drift_degrees":permutation_axis,
                                 "withheld_axis_error_degrees":axis_error,"withheld_anisotropy_relative_error":anisotropy_error,
                                 "invalid":bool(axis_error>config["withheld_maximum_axis_drift_degrees"] or anisotropy_error>config["withheld_maximum_anisotropy_relative_error"]),
                                 "accept":accepts})
    summaries={};gates={}
    for scale in scales:
        subset=[r for r in rows if r["scale_um"]==scale];summaries[str(scale)]={}
        for condition in subset[0]["accept"]:
            accepted=[r for r in subset if r["accept"][condition]]
            summaries[str(scale)][condition]={"cases":len(subset),"accepted":len(accepted),"coverage":len(accepted)/len(subset),
                                             "silent_invalid":sum(r["invalid"] for r in accepted),"silent_invalid_risk":float(np.mean([r["invalid"] for r in accepted])) if accepted else None}
        full=summaries[str(scale)]["full_contract"];always=summaries[str(scale)]["always_emit"]
        gates[str(scale)]={"coverage_at_least_0_80":full["coverage"]>=config["minimum_success_coverage"],
                           "risk_below_always_emit":full["silent_invalid_risk"] is not None and full["silent_invalid_risk"]<always["silent_invalid_risk"]}
    payload={"protocol_version":config["protocol_version"],"config_sha256":_sha256(config_path),"dataset_doi":config["dataset_doi"],
             "deposited_volumes":len({r["volume"] for r in rows}),"scale_case_rows":len(rows),"summary_by_scale_um":summaries,"gates_by_scale_um":gates,
             "status":"development_complete","claim_boundary":config["claim_boundary"]}
    output.mkdir(parents=True,exist_ok=True);(output/"case_rows.json").write_text(json.dumps(rows,indent=2,allow_nan=False)+"\n",encoding="utf-8");(output/"human_nanoct_scale_response.json").write_text(json.dumps(payload,indent=2,allow_nan=False)+"\n",encoding="utf-8");return payload

