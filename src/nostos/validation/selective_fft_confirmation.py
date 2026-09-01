"""Prospectively frozen confirmation of selective FFT measurement."""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
from scipy import ndimage
from sklearn.metrics import roc_auc_score

from nostos.validation.metrics import axial_angular_error_degrees, relative_scale_error
from nostos.validation.perturbations import _center_crop_or_pad
from nostos.validation.phantoms import generate_phantom
from nostos.validation.canonical_confirmation_v3 import _gamma, _illumination, _shot_noise
from nostos.validation.selective_fft_development import self_perturbation_score


PROTOCOL_SHA256="964ed403f81c9953faa9fe244e8266e6f5b64058f21b99c4407ee7e21258510d"
THRESHOLD=1.0943159403934886


def _degrade(image:np.ndarray,rng:np.random.Generator)->tuple[np.ndarray,float,dict]:
    gamma=float(rng.uniform(.45,1.95)); illumination=float(rng.uniform(-.65,.65)); angle=float(rng.uniform(0,2*np.pi)); sigma=tuple(rng.uniform((.2,.8),(2.0,4.2))); counts=float(rng.uniform(16,100)); impulse=float(rng.uniform(0,.025)); sampling=float(rng.uniform(.30,1.0)); crop=float(rng.uniform(.45,1.0)); dropout=int(rng.integers(0,12))
    values=_gamma(np.asarray(image,dtype=float),gamma); values=_illumination(values,illumination,angle); values=ndimage.gaussian_filter(values,sigma=sigma,mode="reflect"); values=_shot_noise(values,counts,rng)
    if impulse>0:
        selector=rng.random(values.shape); values[selector<impulse/2]=values.min(); values[(selector>=impulse/2)&(selector<impulse)]=values.max()
    if dropout:
        start=int(rng.integers(0,values.shape[0]-dropout+1)); values[start:start+dropout]=float(np.median(values))
    values=ndimage.zoom(values,sampling,order=1,mode="reflect"); values=_center_crop_or_pad(values,(128,128)); retained=max(32,int(round(128*crop))); values=_center_crop_or_pad(_center_crop_or_pad(values,(retained,retained)),(128,128))
    return values.astype(np.float32),1.0/sampling,{"gamma":gamma,"illumination":illumination,"illumination_angle":angle,"anisotropic_blur_sigma":sigma,"shot_counts":counts,"impulse_fraction":impulse,"sampling":sampling,"crop":crop,"dropout_rows":dropout}


def _wilson(invalid:int,total:int)->list[float]:
    if total<=0:return [0.0,1.0]
    z=1.959963984540054;p=invalid/total;den=1+z*z/total;center=(p+z*z/(2*total))/den;half=z*np.sqrt(p*(1-p)/total+z*z/(4*total*total))/den
    return [float(max(0,center-half)),float(min(1,center+half))]


def _risk_reduction_interval(rows:list[dict])->list[float]:
    rng=np.random.default_rng(61203);values=[];n=len(rows)
    for _ in range(10000):
        sample=[rows[i] for i in rng.integers(0,n,n)];accepted=[row for row in sample if row["accepted"]]
        if accepted:values.append(float(np.mean([row["invalid"] for row in sample])-np.mean([row["invalid"] for row in accepted])))
    return [float(value) for value in np.quantile(values,(.025,.975))]


def run_confirmation(output:Path,n_cases:int=600)->dict:
    rng=np.random.default_rng(61202);rows=[]
    for index in range(n_cases):
        angle=float(rng.uniform(0,180));wavelength=float(rng.uniform(6,34));phantom=generate_phantom("orientation",shape=(128,128),angle_degrees=angle,scale_um=wavelength,seed=int(rng.integers(1,2**31-1)))
        image,spacing,degradation=_degrade(phantom.image,rng);score,diagnostics=self_perturbation_score(image,spacing);measurement=diagnostics["measurement"];angle_error=axial_angular_error_degrees(measurement["orientation"],angle);scale_error=relative_scale_error(measurement["wavelength"],wavelength);invalid=angle_error>5 or scale_error>.15;accepted=score<=THRESHOLD;pixels_per_scale=measurement["wavelength"]/spacing;legacy_accepted=not(measurement["snr"]<3 or pixels_per_scale<4)
        rows.append({"case":index,"truth_angle":angle,"truth_wavelength":wavelength,"spacing":spacing,"degradation":degradation,"score":score,"accepted":accepted,"legacy_accepted":legacy_accepted,"invalid":invalid,"angle_error":angle_error,"scale_error":scale_error,"diagnostics":diagnostics})
    accepted=[row for row in rows if row["accepted"]];legacy=[row for row in rows if row["legacy_accepted"]];invalid_count=sum(row["invalid"] for row in accepted);coverage=len(accepted)/len(rows);risk=invalid_count/len(accepted);legacy_coverage=len(legacy)/len(rows);legacy_risk=float(np.mean([row["invalid"] for row in legacy])) if legacy else 1.0;auc=float(roc_auc_score([row["invalid"] for row in rows],[row["score"] for row in rows]));reduction=_risk_reduction_interval(rows);median_angle=float(np.median([row["angle_error"] for row in accepted]));median_scale=float(np.median([row["scale_error"] for row in accepted]));wilson=_wilson(invalid_count,len(accepted))
    gates={"coverage_ge_0.60":coverage>=.60,"selective_risk_wilson_upper_le_0.08":wilson[1]<=.08,"invalid_detection_auc_ge_0.90":auc>=.90,"risk_reduction_ci_lower_gt_0.10":reduction[0]>.10,"better_than_legacy_or_twice_coverage":risk<legacy_risk or legacy_coverage<coverage/2,"accepted_median_errors_within_limits":median_angle<=2 and median_scale<=.08}
    payload={"protocol_version":"nostos-selective-fft-confirmation/1.0","protocol_sha256":PROTOCOL_SHA256,"threshold":THRESHOLD,"status":"pass" if all(gates.values()) else "fail","case_count":len(rows),"summary":{"coverage":coverage,"accepted":len(accepted),"selective_risk":risk,"selective_risk_wilson95":wilson,"invalid_detection_auc":auc,"risk_all":float(np.mean([row["invalid"] for row in rows])),"risk_reduction_ci95":reduction,"legacy_coverage":legacy_coverage,"legacy_risk":legacy_risk,"accepted_median_angle_error":median_angle,"accepted_median_scale_error":median_scale},"success_gates":gates,"scope":"Analytic selective FFT measurement under frozen acquisition perturbations; not biological or clinical validation.","rows":rows}
    output.mkdir(parents=True,exist_ok=True);(output/"selective_fft_confirmation.json").write_text(json.dumps(payload,indent=2,allow_nan=False)+"\n",encoding="utf-8");return payload
