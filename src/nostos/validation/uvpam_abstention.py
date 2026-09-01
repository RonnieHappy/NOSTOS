"""Frozen UV-PAM calibration and semantic-abstention benchmark."""
from __future__ import annotations

import hashlib
import io
import json
import re
import zipfile
from pathlib import Path

import numpy as np
from PIL import Image
from scipy.ndimage import gaussian_filter

from nostos.features.spatial_fft import extract_spatial_fft
from nostos.validation.metrics import axial_angular_error_degrees


def _sha256(path: Path) -> str:
    h=hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda:stream.read(1<<20),b""): h.update(block)
    return h.hexdigest()


def _normalise(image: np.ndarray) -> np.ndarray:
    values=np.asarray(image,dtype=np.float32); lo,hi=np.percentile(values,(1,99))
    return np.clip((values-lo)/max(float(hi-lo),np.finfo(np.float32).eps),0,1)


def measure_pixel_domain(image: np.ndarray) -> dict:
    data=_normalise(image); result=extract_spatial_fft(data,pixel_size_um=1.0)
    wavelength_pixels=1000.0/max(result.characteristic_frequency_cycles_per_mm,np.finfo(float).eps)
    return {"orientation_degrees":float(result.orientation_degrees),"anisotropy":float(result.anisotropy),
            "angular_entropy":float(result.angular_entropy),"characteristic_wavelength_pixels":float(wavelength_pixels),
            "units":"pixels","dynamic_range":float(np.percentile(data,99)-np.percentile(data,1)),
            "saturation_fraction":float(np.mean((data<=0)|(data>=1)))}


def _sample(names: list[str], count: int) -> list[str]:
    if len(names)<=count:return sorted(names)
    indexes=np.linspace(0,len(names)-1,count,dtype=int)
    return [sorted(names)[index] for index in sorted(set(indexes))]


def run(archive: Path, config_path: Path, output: Path) -> dict:
    config=json.loads(config_path.read_text(encoding="utf-8")); rows=[]
    with zipfile.ZipFile(archive) as z:
        names=[name for name in z.namelist() if "/trainA/" in name and name.lower().endswith(".png")]
        groups={}
        for name in names:
            match=re.search(r"/A_(\d{4})_",name)
            if match:groups.setdefault(match.group(1),[]).append(name)
        for group in sorted(groups):
            for name in _sample(groups[group],int(config["tiles_per_source_group"])):
                with Image.open(io.BytesIO(z.read(name))) as opened:
                    metadata=dict(opened.info); image=np.asarray(opened.convert("L"),dtype=np.float32)
                data=_normalise(image); measurement=measure_pixel_domain(data)
                probes=[np.power(data,1.1),gaussian_filter(data,0.75)]
                drifts=[axial_angular_error_degrees(measurement["orientation_degrees"],measure_pixel_domain(p)["orientation_degrees"]) for p in probes]
                stable=max(drifts)<=config["maximum_dimensionless_orientation_drift_degrees"]
                image_qc=(measurement["dynamic_range"]>=config["minimum_dynamic_range_fraction"] and
                          measurement["saturation_fraction"]<=config["maximum_saturation_fraction"])
                calibrated=bool(config["physical_spacing_available"] and metadata.get("dpi"))
                semantic=bool(config["requested_semantics_supported"])
                accepts={"always_emit":True,"image_qc_only":image_qc,
                         "partial_no_calibration":image_qc and stable and semantic,
                         "partial_no_semantics":image_qc and stable and calibrated,
                         "full_contract":image_qc and stable and calibrated and semantic}
                rows.append({"source_group":group,"file":name,"png_metadata":metadata,
                             "pixel_domain_measurement":measurement,"maximum_probe_orientation_drift_degrees":float(max(drifts)),
                             "generic_pixel_descriptor_emitted":bool(image_qc and stable),"physical_endpoint_invalid":True,
                             "abstention_reasons":[reason for flag,reason in ((calibrated,"missing_physical_spacing"),(semantic,"unsupported_requested_semantics")) if not flag],
                             "accept":accepts})
    summary={}
    for condition in rows[0]["accept"]:
        accepted=[r for r in rows if r["accept"][condition]]
        summary[condition]={"tiles":len(rows),"accepted":len(accepted),"coverage":len(accepted)/len(rows),
                            "silent_invalid":sum(r["physical_endpoint_invalid"] for r in accepted),
                            "silent_invalid_risk":float(np.mean([r["physical_endpoint_invalid"] for r in accepted])) if accepted else None}
    payload={"protocol_version":config["protocol_version"],"config_sha256":_sha256(config_path),"archive_sha256":_sha256(archive),
             "dataset_doi":config["dataset_doi"],"archive_uvpam_tiles":len(names),"source_filename_groups":len(groups),
             "sampled_tiles":len(rows),"generic_pixel_descriptors_emitted":sum(r["generic_pixel_descriptor_emitted"] for r in rows),
             "summary":summary,"status":"pass" if summary["full_contract"]["coverage"]==0 and summary["image_qc_only"]["silent_invalid"]>0 else "fail",
             "claim_boundary":config["claim_boundary"]}
    output.mkdir(parents=True,exist_ok=True)
    (output/"case_rows.json").write_text(json.dumps(rows,indent=2,allow_nan=False)+"\n",encoding="utf-8")
    (output/"uvpam_abstention.json").write_text(json.dumps(payload,indent=2,allow_nan=False)+"\n",encoding="utf-8")
    return payload
