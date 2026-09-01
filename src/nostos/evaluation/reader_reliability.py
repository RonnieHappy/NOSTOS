"""Quantify inter- and intra-reader reliability from raw repository score tables."""
from __future__ import annotations
import argparse, json
from itertools import combinations
from pathlib import Path
import numpy as np
import pandas as pd
from nostos.evaluation.adjacent_replication import icc_a1

def score_long(raw: pd.DataFrame) -> pd.DataFrame:
    rows=[]
    for _, row in raw.iterrows():
        for read in (1,2,3):
            hh=[pd.to_numeric(row.get(f"{name}read{read}"),errors="coerce") for name in ("structure","cells","safo","tidemark")]
            grade=pd.to_numeric(row.get(f"graderead{read}"),errors="coerce"); stage=pd.to_numeric(row.get(f"stageread{read}"),errors="coerce")
            base={"participant_id":str(row.participant_id).zfill(3),"site":row.site,"scorer":int(row.scorer),"read":read,"source_provenance":"recovered_trash" if "files/.trash/" in row.source_csv else "active"}
            if np.all(np.isfinite(hh)): rows.append({**base,"outcome":"HHGS","score":float(sum(hh))})
            if np.isfinite(grade) and np.isfinite(stage): rows.append({**base,"outcome":"OARSI","score":float(grade*stage)})
    return pd.DataFrame(rows)

def icc_ak(matrix: np.ndarray) -> float:
    n,k=matrix.shape; grand=matrix.mean(); row=matrix.mean(1); col=matrix.mean(0)
    msr=k*np.sum((row-grand)**2)/(n-1); msc=n*np.sum((col-grand)**2)/(k-1); residual=matrix-row[:,None]-col[None,:]+grand; mse=np.sum(residual**2)/((n-1)*(k-1)); denominator=msr+(msc-mse)/n
    return float((msr-mse)/denominator) if denominator else np.nan

def matrix_icc(frame: pd.DataFrame, columns: str):
    matrix=frame.pivot_table(index=["participant_id","site"],columns=columns,values="score",aggfunc="first").dropna()
    values=matrix.to_numpy(float)
    if values.shape[1] == 2: single=icc_a1(values[:,0],values[:,1])
    else:
        # General ICC(A,1), McGraw-Wong two-way random absolute agreement.
        n,k=values.shape; grand=values.mean(); row=values.mean(1); col=values.mean(0); msr=k*np.sum((row-grand)**2)/(n-1); msc=n*np.sum((col-grand)**2)/(k-1); residual=values-row[:,None]-col[None,:]+grand; mse=np.sum(residual**2)/((n-1)*(k-1)); single=float((msr-mse)/(msr+(k-1)*mse+k*(msc-mse)/n))
    return matrix,single,icc_ak(values)

def run(source: Path, output: Path):
    output.mkdir(parents=True,exist_ok=True); raw=pd.read_csv(source,dtype={"participant_id":str}); long=score_long(raw); long.to_csv(output/"table_reader_scores_reconstructed.csv",index=False)
    summary=[]
    for outcome in ("HHGS","OARSI"):
        subset=long[long.outcome==outcome]
        for read in (1,2,3):
            matrix,single,average=matrix_icc(subset[subset.read==read],"scorer")
            pair_errors=[]
            for a,b in combinations(matrix.columns,2): pair_errors.extend(np.abs(matrix[a]-matrix[b]).tolist())
            summary.append({"reliability_type":"inter_reader","outcome":outcome,"stratum":f"read_{read}","complete_specimens":len(matrix),"raters_or_reads":matrix.shape[1],"icc_absolute_single":single,"icc_absolute_average":average,"median_pairwise_absolute_difference":np.median(pair_errors),"mean_pairwise_absolute_difference":np.mean(pair_errors)})
        for scorer in (1,2,3):
            matrix,single,average=matrix_icc(subset[subset.scorer==scorer],"read")
            pair_errors=[]
            for a,b in combinations(matrix.columns,2): pair_errors.extend(np.abs(matrix[a]-matrix[b]).tolist())
            summary.append({"reliability_type":"intra_reader","outcome":outcome,"stratum":f"scorer_{scorer}","complete_specimens":len(matrix),"raters_or_reads":matrix.shape[1],"icc_absolute_single":single,"icc_absolute_average":average,"median_pairwise_absolute_difference":np.median(pair_errors),"mean_pairwise_absolute_difference":np.mean(pair_errors)})
    summary=pd.DataFrame(summary); summary.to_csv(output/"table_reader_reliability.csv",index=False)
    provenance=raw.assign(source_provenance=np.where(raw.source_csv.str.contains("files/.trash/",regex=False),"recovered_trash","active")).groupby("source_provenance").size().to_dict()
    report={"raw_rows":len(raw),"reconstructed_ratings":len(long),"source_rows_by_provenance":provenance,"zero_without_components_excluded":True}; (output/"reader_reliability_report.json").write_text(json.dumps(report,indent=2)+"\n",encoding="utf-8"); return report

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument("scores",type=Path);p.add_argument("--output",type=Path,required=True);a=p.parse_args();print(json.dumps(run(a.scores,a.output),indent=2))
if __name__=="__main__":main()
