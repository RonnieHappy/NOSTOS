"""Development of self-perturbation-based abstention for FFT measurements."""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
from scipy import ndimage

from nostos.features.spatial_fft import extract_spatial_fft
from nostos.validation.metrics import axial_angular_error_degrees, relative_scale_error
from nostos.validation.perturbations import _center_crop_or_pad
from nostos.validation.phantoms import generate_phantom


def _measure(image: np.ndarray, spacing: float) -> dict[str, float]:
    features = extract_spatial_fft(image, pixel_size_um=spacing)
    residual = image - ndimage.gaussian_filter(image, .7)
    noise = np.median(np.abs(residual - np.median(residual))) * 1.4826
    return {"orientation": features.orientation_degrees,
            "wavelength": 1000 / features.characteristic_frequency_cycles_per_mm,
            "anisotropy": features.anisotropy, "entropy": features.angular_entropy,
            "snr": float(np.std(image) / max(float(noise), 1e-6))}


def _degrade(image: np.ndarray, rng: np.random.Generator) -> tuple[np.ndarray, float, dict[str, float]]:
    contrast=float(rng.uniform(.08,1.2)); noise=float(rng.uniform(0,.85)); blur=float(rng.uniform(0,3.8)); sampling=float(rng.uniform(.32,1.0)); crop=float(rng.uniform(.48,1.0))
    values=contrast*np.asarray(image,dtype=float)
    values=ndimage.gaussian_filter(values,blur,mode="reflect")
    values += rng.normal(scale=noise*float(np.std(image)),size=values.shape)
    coarse=ndimage.zoom(values,sampling,order=1,mode="reflect"); values=_center_crop_or_pad(coarse,(128,128))
    retained=max(32,int(round(128*crop))); values=_center_crop_or_pad(_center_crop_or_pad(values,(retained,retained)),(128,128))
    return values.astype(np.float32),1.0/sampling,{"contrast":contrast,"noise":noise,"blur":blur,"sampling":sampling,"crop":crop}


def _axial_spread(values: list[float]) -> float:
    reference=values[0]
    return float(max(axial_angular_error_degrees(value,reference) for value in values[1:]))


def self_perturbation_score(image: np.ndarray, spacing: float=1.0) -> tuple[float,dict]:
    base=_measure(image,spacing); orientations=[base["orientation"]]; wavelengths=[base["wavelength"]]
    for angle in (-4.0,4.0):
        probe=ndimage.rotate(image,angle,reshape=False,order=1,mode="reflect"); measured=_measure(probe,spacing)
        orientations.append((measured["orientation"]+angle)%180); wavelengths.append(measured["wavelength"])
    for probe in (ndimage.gaussian_filter(image,.6,mode="reflect"), _center_crop_or_pad(_center_crop_or_pad(image,(112,112)),image.shape)):
        measured=_measure(probe,spacing); orientations.append(measured["orientation"]); wavelengths.append(measured["wavelength"])
    angle_instability=_axial_spread(orientations); scale_instability=float(np.std(wavelengths)/max(np.mean(wavelengths),np.finfo(float).eps))
    pixels_per_scale=base["wavelength"]/spacing
    components={"angle_instability":angle_instability/5,"scale_instability":scale_instability/.15,
                "low_anisotropy":max(0,(.45-base["anisotropy"])/.45),"high_entropy":max(0,(base["entropy"]-.72)/.28),
                "low_snr":max(0,(3-base["snr"])/3),"undersampling":max(0,(4-pixels_per_scale)/4)}
    return float(max(components.values())),{"measurement":base,"components":components,"angle_instability_degrees":angle_instability,"scale_instability_fraction":scale_instability}


def run_development(output: Path,n_cases:int=500) -> dict:
    rng=np.random.default_rng(51201); rows=[]
    for index in range(n_cases):
        angle=float(rng.uniform(0,180)); wavelength=float(rng.uniform(6,34)); phantom=generate_phantom("orientation",shape=(128,128),angle_degrees=angle,scale_um=wavelength,seed=int(rng.integers(1,2**31-1)))
        image,spacing,degradation=_degrade(phantom.image,rng); score,diagnostics=self_perturbation_score(image,spacing)
        measured=diagnostics["measurement"]; angle_error=axial_angular_error_degrees(measured["orientation"],angle); scale_error=relative_scale_error(measured["wavelength"],wavelength); invalid=angle_error>5 or scale_error>.15
        rows.append({"case":index,"truth_angle":angle,"truth_wavelength":wavelength,"degradation":degradation,"score":score,"angle_error":angle_error,"scale_error":scale_error,"invalid":invalid,"diagnostics":diagnostics})
    candidates=np.unique(np.asarray([row["score"] for row in rows])); selected=None
    for threshold in candidates:
        accepted=[row for row in rows if row["score"]<=threshold]
        if len(accepted)<50: continue
        risk=np.mean([row["invalid"] for row in accepted]); coverage=len(accepted)/len(rows)
        if risk<=.05 and (selected is None or coverage>selected["coverage"]): selected={"threshold":float(threshold),"coverage":coverage,"selective_risk":float(risk),"accepted":len(accepted)}
    payload={"protocol_version":"nostos-selective-fft-development/1.0","scope":"development only","seed":51201,"case_count":len(rows),"validity_rule":"angle error <=5 degrees and relative wavelength error <=0.15","selected_threshold":selected,"rows":rows}
    output.mkdir(parents=True,exist_ok=True); (output/"selective_fft_development.json").write_text(json.dumps(payload,indent=2,allow_nan=False)+"\n",encoding="utf-8"); return payload
