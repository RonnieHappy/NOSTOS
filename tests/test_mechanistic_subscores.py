import pandas as pd
from nostos.evaluation.mechanistic_subscores import reconstruct

def test_reconstruction_does_not_treat_ambiguous_value_as_zero():
 raw=pd.DataFrame([{"participant_id":"001","site":"Medial","structure_read_unused":"","structureread1":"0?","cellsread1":"1","saforead1":"2","tidemarkread1":"0","graderead1":"2","stageread1":"1","scorer":"1","source_csv":"x"}])
 components,_=reconstruct(raw)
 assert "hhgs_structure" not in set(components.component)
 assert components.loc[components.component=="hhgs_cells","value"].item()==1
