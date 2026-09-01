"""Participant-safe severity classification benchmark and prior-task feasibility audit."""
from __future__ import annotations
import argparse, json
from pathlib import Path
import numpy as np
import pandas as pd
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import average_precision_score, balanced_accuracy_score, f1_score, roc_auc_score
from sklearn.model_selection import GridSearchCV, StratifiedKFold, cross_val_predict
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

SETS={
 "fft_entropy":["angular_entropy_median"],
 "fft_multiscale":["angular_entropy_median","anisotropy_median","spectral_slope_median","characteristic_frequency_cycles_per_mm_median"],
 "conventional_texture":["tensor_coherence_median","glcm_contrast_median","glcm_homogeneity_median"],
 "combined":["angular_entropy_median","anisotropy_median","spectral_slope_median","characteristic_frequency_cycles_per_mm_median","tensor_coherence_median","glcm_contrast_median","glcm_homogeneity_median"]}

def model():
 return Pipeline([("impute",SimpleImputer(strategy="median")),("scale",StandardScaler()),("model",LogisticRegression(max_iter=5000,class_weight="balanced",solver="liblinear",random_state=260825))])

def nested_probabilities(x,y):
 outer=StratifiedKFold(5,shuffle=True,random_state=260825); probabilities=np.zeros(len(y)); folds=np.zeros(len(y),int)
 for fold,(train,test) in enumerate(outer.split(x,y),1):
  inner=StratifiedKFold(4,shuffle=True,random_state=260825+fold); search=GridSearchCV(model(),{"model__C":[.01,.1,1,10,100]},scoring="balanced_accuracy",cv=inner,n_jobs=1); search.fit(x.iloc[train],y[train]); probabilities[test]=search.predict_proba(x.iloc[test])[:,1]; folds[test]=fold
 return probabilities,folds

def metrics(y,p):
 pred=(p>=.5).astype(int)
 return {"balanced_accuracy":balanced_accuracy_score(y,pred),"macro_f1":f1_score(y,pred,average="macro"),"roc_auc":roc_auc_score(y,p),"average_precision":average_precision_score(y,p)}

def run(table:Path,output:Path,permutations=1000):
 output.mkdir(parents=True,exist_ok=True); data=pd.read_csv(table); score=data.mean_total_oarsi.to_numpy(float)
 feasibility=[]
 for name,early in (("published_text",2.4),("nonoverlap_typo_sensitivity",3.4)):
  labels=np.select([score<early,score<8.6,score<15.4],["early","mild","moderate"],default="severe")
  counts=pd.Series(labels).value_counts(); feasibility.append({"rule":name,"early_upper":early,"mild_upper":8.6,"moderate_upper":15.4,**{label:int(counts.get(label,0)) for label in ("early","mild","moderate","severe")},"participant_safe_fivefold_feasible":bool(counts.min()>=5)})
 pd.DataFrame(feasibility).to_csv(output/"table_prior_four_class_feasibility.csv",index=False)
 y=(score>=8.6).astype(int); rows=[]; predictions=[]
 for name,features in SETS.items():
  p,folds=nested_probabilities(data[features],y); rows.append({"model":name,"n":len(y),"moderate_or_greater":int(y.sum()),**metrics(y,p)})
  predictions.append(pd.DataFrame({"participant_id":data.participant_id,"outcome":y,"probability":p,"outer_fold":folds,"model":name}))
 result=pd.DataFrame(rows); result.to_csv(output/"table_severity_nested_cv.csv",index=False); pd.concat(predictions).to_csv(output/"table_severity_predictions.csv",index=False)
 observed=float(result.loc[result.model=="fft_multiscale","balanced_accuracy"].iloc[0]); rng=np.random.default_rng(260825); null=[]
 for _ in range(permutations):
  yp=rng.permutation(y); p,_=nested_probabilities(data[SETS["fft_multiscale"]],yp); null.append(balanced_accuracy_score(yp,p>=.5))
 pvalue=(1+np.sum(np.asarray(null)>=observed))/(permutations+1); receipt={"binary_definition":"OARSI >= 8.6","observed_fft_multiscale_balanced_accuracy":observed,"permutations":permutations,"null_mean":float(np.mean(null)),"permutation_p":float(pvalue),"four_class_conclusion":"not participant-safe because at least one class has fewer than five participants"}; (output/"severity_permutation.json").write_text(json.dumps(receipt,indent=2)+"\n",encoding="utf-8"); return receipt

def main():
 p=argparse.ArgumentParser(description=__doc__);p.add_argument("table",type=Path);p.add_argument("--output",type=Path,required=True);p.add_argument("--permutations",type=int,default=1000);a=p.parse_args();print(json.dumps(run(a.table,a.output,a.permutations),indent=2))
if __name__=="__main__":main()
