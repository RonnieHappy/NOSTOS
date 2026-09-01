"""Component-level biological discrimination for the NOSTOS entropy phenotype."""
from __future__ import annotations
import argparse, json
from pathlib import Path
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from scipy.stats import spearmanr
from nostos.evaluation.adjacent_replication import bh, bootstrap_spearman

COMPONENTS={"hhgs_structure":"structure","hhgs_cells":"cells","hhgs_safo_loss":"safo","hhgs_tidemark":"tidemark","oarsi_grade":"grade","oarsi_stage":"stage"}
PLM={"plm_superficial_disorganization":"plmsignalatsurfaceread1","plm_deep_disorganization":"plmsignalindzread1","plm_total_disorganization":"plmtotal"}
FEATURES=("angular_entropy_median","anisotropy_median")

def reconstruct(raw:pd.DataFrame):
 rows=[]
 for _,r in raw.iterrows():
  for read in (1,2,3):
   for outcome,stem in COMPONENTS.items():
    value=pd.to_numeric(r.get(f"{stem}read{read}"),errors="coerce")
    if np.isfinite(value): rows.append({"participant_id":str(r.participant_id).zfill(3),"site":r.site,"component":outcome,"value":float(value)})
 component_columns=["participant_id","site","component","value"]
 components=pd.DataFrame(rows,columns=component_columns)
 if not components.empty:
  components=components.groupby(["participant_id","site","component"],as_index=False).value.mean()
 plm=[]
 for _,r in raw.iterrows():
  for outcome,column in PLM.items():
   value=pd.to_numeric(r.get(column),errors="coerce")
   if np.isfinite(value):plm.append({"participant_id":str(r.participant_id).zfill(3),"component":outcome,"value":float(value)})
 plm_frame=pd.DataFrame(plm,columns=["participant_id","component","value"])
 if not plm_frame.empty:
  plm_frame=plm_frame.groupby(["participant_id","component"],as_index=False).value.mean()
 return components,plm_frame

def feature_table(path,site,rank):
 frame=pd.read_csv(path,dtype={"participant_id":str});frame.participant_id=frame.participant_id.str.zfill(3);frame=frame[frame.feature_success.astype(str).str.lower().eq("true")]
 return frame[["participant_id",*FEATURES]].assign(site=site,section_rank=rank)

def association(x,y,repeats=5000):
 rho,p=spearmanr(x,y);lo,hi=bootstrap_spearman(np.asarray(x,float),np.asarray(y,float),repeats,seed=260826);return rho,p,lo,hi

def run(scores,medial1,medial2,lateral1,lateral2,output,bootstrap=5000):
 output.mkdir(parents=True,exist_ok=True);raw=pd.read_csv(scores,dtype={"participant_id":str});components,plm=reconstruct(raw);components.to_csv(output/"table_component_scores.csv",index=False);plm.to_csv(output/"table_plm_components.csv",index=False)
 features=pd.concat([feature_table(medial1,"Medial",1),feature_table(medial2,"Medial",2),feature_table(lateral1,"Lateral",1),feature_table(lateral2,"Lateral",2)],ignore_index=True)
 rows=[]
 for (site,rank),image in features.groupby(["site","section_rank"]):
  for component,values in components[components.site==site].groupby("component"):
   merged=image.merge(values[["participant_id","value"]],on="participant_id",validate="one_to_one")
   for feature in FEATURES:
    rho,p,lo,hi=association(merged[feature],merged.value,bootstrap);rows.append({"site":site,"section_rank":rank,"feature":feature,"component":component,"n":len(merged),"spearman_rho":rho,"bootstrap_ci_lower":lo,"bootstrap_ci_upper":hi,"p_value":p,"anatomical_match":"same_site"})
  if site=="Medial":
   for component,values in plm.groupby("component"):
    merged=image.merge(values[["participant_id","value"]],on="participant_id",validate="one_to_one")
    for feature in FEATURES:
     rho,p,lo,hi=association(merged[feature],merged.value,bootstrap);rows.append({"site":site,"section_rank":rank,"feature":feature,"component":component,"n":len(merged),"spearman_rho":rho,"bootstrap_ci_lower":lo,"bootstrap_ci_upper":hi,"p_value":p,"anatomical_match":"participant_medial"})
 result=pd.DataFrame(rows);result["q_value_bh_global"]=bh(result.p_value);result.to_csv(output/"table_mechanistic_associations.csv",index=False)
 contrasts=[]
 wide=plm.pivot(index="participant_id",columns="component",values="value").reset_index()
 for rank in (1,2):
  image=features[(features.site=="Medial")&(features.section_rank==rank)];merged=image.merge(wide,on="participant_id").dropna(subset=["plm_superficial_disorganization","plm_deep_disorganization"])
  for feature in FEATURES:
   x=merged[feature].to_numpy(float);surface=merged.plm_superficial_disorganization.to_numpy(float);deep=merged.plm_deep_disorganization.to_numpy(float);observed=spearmanr(x,surface).statistic-spearmanr(x,deep).statistic;rng=np.random.default_rng(260826+rank);vals=[]
   for _ in range(bootstrap):
    idx=rng.integers(0,len(x),len(x));a=spearmanr(x[idx],surface[idx]).statistic;b=spearmanr(x[idx],deep[idx]).statistic
    if np.isfinite(a) and np.isfinite(b):vals.append(a-b)
   lo,hi=np.quantile(vals,[.025,.975]);contrasts.append({"section_rank":rank,"feature":feature,"n":len(x),"surface_rho_minus_deep_rho":observed,"bootstrap_ci_lower":lo,"bootstrap_ci_upper":hi})
 pd.DataFrame(contrasts).to_csv(output/"table_plm_zone_contrasts.csv",index=False)
 entropy=result[result.feature=="angular_entropy_median"].copy();order=["hhgs_safo_loss","hhgs_structure","oarsi_grade","oarsi_stage","hhgs_cells","hhgs_tidemark","plm_superficial_disorganization","plm_deep_disorganization","plm_total_disorganization"]
 entropy["column"]=entropy.site.str.slice(0,3)+" "+entropy.section_rank.astype(str);matrix=entropy.pivot(index="component",columns="column",values="spearman_rho").reindex(order);qmatrix=entropy.pivot(index="component",columns="column",values="q_value_bh_global").reindex(index=matrix.index,columns=matrix.columns);fig,ax=plt.subplots(figsize=(10,6),constrained_layout=True);im=ax.imshow(matrix,cmap="RdBu_r",vmin=-.6,vmax=.6);ax.set_xticks(range(len(matrix.columns)),matrix.columns);ax.set_yticks(range(len(matrix.index)),[x.replace("hhgs_","HHGS ").replace("oarsi_","OARSI ").replace("plm_","PLM ").replace("_"," ") for x in matrix.index]);
 for i in range(matrix.shape[0]):
  for j in range(matrix.shape[1]):
   if np.isfinite(matrix.iloc[i,j]):ax.text(j,i,f"{matrix.iloc[i,j]:.2f}{'*' if qmatrix.iloc[i,j] < .05 else ''}",ha="center",va="center",fontsize=8)
 fig.colorbar(im,ax=ax,label="Spearman ρ",shrink=.88);ax.set_title("Component-level biological associations",fontsize=14);ax.set_xlabel("Site and section rank (* global q<0.05)")
 for suffix in ("png","svg"):fig.savefig(output/f"figure_mechanistic_component_heatmap.{suffix}",dpi=300)
 plt.close(fig);report={"component_rows":len(components),"plm_rows":len(plm),"association_tests":len(result),"bootstrap_repeats":bootstrap,"protocol_sha256":"ea8660c566223c7ea149045f42eacea8204902b0cd979fee2d7ea535db8163f0"};(output/"mechanistic_report.json").write_text(json.dumps(report,indent=2)+"\n",encoding="utf-8");return report

def main():
 p=argparse.ArgumentParser(description=__doc__);p.add_argument("scores",type=Path);p.add_argument("medial_rank1",type=Path);p.add_argument("medial_rank2",type=Path);p.add_argument("lateral_rank1",type=Path);p.add_argument("lateral_rank2",type=Path);p.add_argument("--output",type=Path,required=True);p.add_argument("--bootstrap",type=int,default=5000);a=p.parse_args();print(json.dumps(run(a.scores,a.medial_rank1,a.medial_rank2,a.lateral_rank1,a.lateral_rank2,a.output,a.bootstrap),indent=2))
if __name__=="__main__":main()
