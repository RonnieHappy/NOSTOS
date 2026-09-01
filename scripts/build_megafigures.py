"""Build image-first, Nature-style NOSTOS main figures from study data."""
from pathlib import Path
import json
import matplotlib as mpl
import matplotlib.pyplot as plt
from matplotlib.gridspec import GridSpec
from matplotlib.patches import FancyArrowPatch, Rectangle
import numpy as np
import pandas as pd
from PIL import Image
from scipy.stats import spearmanr

from nostos.app.server import _tile_features, _spectrum_preview
from nostos.segmentation.weak_labels import propose_semantic_mask, proposal_overlay

ROOT=Path(__file__).resolve().parents[1]; OUT=ROOT/'outputs'/'main_figures'; OUT.mkdir(parents=True,exist_ok=True)
DATA=Path(r'<DATA_ROOT>\data\public\human-knee-cartilage-histopathology\raw')
INK='#202124'; TEAL='#237A83'; GOLD='#D49B2A'; RED='#B84A32'; BLUE='#285F82'; LIGHT='#EEF2F3'
mpl.rcParams.update({'font.family':'serif','font.serif':['Times New Roman'],'font.size':7.2,'axes.labelsize':7.2,'axes.titlesize':7.4,'xtick.labelsize':6.4,'ytick.labelsize':6.4,'axes.linewidth':.55,'svg.fonttype':'none','savefig.dpi':600,'figure.facecolor':'white','axes.facecolor':'white'})

def panel(ax,label):
 fn=ax.text2D if hasattr(ax,'text2D') else ax.text
 fn(.012,.985,label,transform=ax.transAxes,fontsize=7.2,fontweight='bold',va='top',ha='left',zorder=30,bbox=dict(boxstyle='square,pad=.18',fc='white',ec='#D5D9DA',lw=.35,alpha=.96))
def clean(ax): ax.spines[['top','right']].set_visible(False); ax.tick_params(width=.6,length=2.5,direction='out')
def save(fig,name):
 for ext in ('png','svg'): fig.savefig(OUT/f'{name}.{ext}',bbox_inches='tight',facecolor='white')
 fig.savefig(OUT/f'{name}.jpg',bbox_inches='tight',facecolor='white',pil_kwargs={'quality':97});plt.close(fig)
def raw_path(pid,site='Medial',rank=1):
 f=pd.read_csv(ROOT/'outputs'/'cpu_pilot'/f'safo_{site.lower()}_features.csv',dtype={'participant_id':str}) if rank==1 else pd.read_csv(ROOT/'outputs'/'flagship'/f'safo_{site.lower()}_rank2_features.csv',dtype={'participant_id':str})
 rel=f.loc[f.participant_id.str.zfill(3)==pid,'relative_path'].iloc[0];return DATA/rel
def load(pid,rank=1):
 with Image.open(raw_path(pid,rank=rank)) as im: rgb=np.asarray(im.convert('RGB'))
 mask=propose_semantic_mask(rgb,'SafO');tiles,_=_tile_features(rgb,mask,1.72);tiles=pd.DataFrame(tiles)
 tissue=mask>0; yy,xx=np.where(tissue)
 if len(xx):
  pad=max(24,int(.02*max(rgb.shape[:2])));x0=max(0,int(xx.min())-pad);x1=min(rgb.shape[1],int(xx.max())+pad);y0=max(0,int(yy.min())-pad);y1=min(rgb.shape[0],int(yy.max())+pad)
  rgb=rgb[y0:y1,x0:x1];mask=mask[y0:y1,x0:x1];tiles=tiles.copy();tiles['x']-=x0;tiles['y']-=y0
  tiles=tiles[(tiles.x+256>0)&(tiles.y+256>0)&(tiles.x<rgb.shape[1])&(tiles.y<rgb.shape[0])]
 return rgb,mask,tiles
def thumb(arr,max_side=1500):
 im=Image.fromarray(arr);im.thumbnail((max_side,max_side),Image.Resampling.LANCZOS);return np.asarray(im)
def crop_foreground(arr, threshold=55, pad_fraction=.08):
 gray=np.asarray(Image.fromarray(arr).convert('L'));yy,xx=np.where(gray>threshold)
 if not len(xx):return arr
 pad=int(pad_fraction*max(xx.max()-xx.min(),yy.max()-yy.min()));x0=max(0,xx.min()-pad);x1=min(arr.shape[1],xx.max()+pad);y0=max(0,yy.min()-pad);y1=min(arr.shape[0],yy.max()+pad)
 return arr[y0:y1,x0:x1]
def show_tissue(ax,arr,title=None): ax.imshow(thumb(arr));ax.axis('off');ax.set_title(title or '',pad=2)
def entropy_map(ax,rgb,tiles,title,grid=False):
 show_tissue(ax,rgb,title); sx=ax.images[0].get_array().shape[1]/rgb.shape[1];sy=ax.images[0].get_array().shape[0]/rgb.shape[0]
 norm=mpl.colors.Normalize(.82,.99);cmap=mpl.colormaps['viridis']
 for r in tiles.itertuples():
  ax.add_patch(Rectangle((r.x*sx,r.y*sy),256*sx,256*sy,facecolor=cmap(norm(r.angular_entropy)),edgecolor='white' if grid else 'none',linewidth=.18,alpha=.68))
 return norm,cmap

def figure1():
 rgb,mask,tiles=load('076'); meta=pd.read_csv(ROOT/'manifests'/'metadata.csv',dtype={'participant_id':str}); score=meta.loc[meta.participant_id.str.zfill(3)=='076','mean_total_oarsi'].iloc[0]
 fig=plt.figure(figsize=(7.2,6.55));gs=GridSpec(4,14,figure=fig,height_ratios=[.62,1.8,1.72,1.9],hspace=.29,wspace=.56)
 ax=fig.add_subplot(gs[0,:]);ax.axis('off');steps=[('Public tissue','90 participants'),('Cartilage + bone','semantic proposal'),('Physical tiling','440 × 440 µm'),('2-D FFT','orientation spectrum'),('Participant phenotype','median entropy')]
 for i,(a,b) in enumerate(steps):
  x=.02+i*.2;ax.add_patch(Rectangle((x,.22),.15,.55,facecolor=LIGHT,edgecolor='#AAB5B8',lw=.7));ax.text(x+.075,.56,a,ha='center',fontweight='bold');ax.text(x+.075,.38,b,ha='center',fontsize=7,color='#555')
  if i<4:ax.add_patch(FancyArrowPatch((x+.152,.495),(x+.195,.495),arrowstyle='-|>',mutation_scale=9,color=TEAL,lw=1))
 panel(ax,'a')
 a1=fig.add_subplot(gs[1,:7]);show_tissue(a1,rgb,f'Whole osteochondral section · P076 · OARSI {score:g}');panel(a1,'b');a1.text(.06,.18,'articular cartilage',transform=a1.transAxes,color=INK,fontweight='bold',bbox=dict(facecolor='white',alpha=.8,pad=1,edgecolor='none'));a1.text(.66,.66,'trabecular bone',transform=a1.transAxes,color=INK,fontweight='bold',bbox=dict(facecolor='white',alpha=.8,pad=1,edgecolor='none'))
 a2=fig.add_subplot(gs[1,7:]);show_tissue(a2,proposal_overlay(rgb,mask,.52),'Segmentation overlay');panel(a2,'c');
 for text,color,x in [('cartilage','#24D17E',.03),('interface','#FFD43B',.36),('bone','#FF6B45',.74)]: a2.text(x,.05,text,transform=a2.transAxes,color=color,fontweight='bold',fontsize=7,bbox=dict(facecolor='black',alpha=.62,pad=.8,edgecolor='none'))
 a3=fig.add_subplot(gs[2,:5]);norm,cmap=entropy_map(a3,rgb,tiles,'Cartilage tile map',True);panel(a3,'d');cb=fig.colorbar(mpl.cm.ScalarMappable(norm=norm,cmap=cmap),ax=a3,fraction=.035,pad=.01);cb.set_label('entropy',fontsize=7);cb.ax.tick_params(labelsize=6)
 chosen=tiles.iloc[(tiles.angular_entropy-tiles.angular_entropy.median()).abs().argmin()];tile=rgb[int(chosen.y):int(chosen.y)+256,int(chosen.x):int(chosen.x)+256]
 a4=fig.add_subplot(gs[2,6:10]);a4.imshow(tile);a4.axis('off');a4.set_title('Representative cartilage tile');panel(a4,'e');a4.plot([18,76],[235,235],color='white',lw=2);a4.text(47,225,'100 µm',color='white',ha='center',fontsize=7)
 a5=fig.add_subplot(gs[2,10:]);spec=_spectrum_preview(tile,np.ones(tile.shape[:2],np.uint8));a5.imshow(spec);a5.axis('off');a5.set_title('Log FFT power');panel(a5,'f')
 a6=fig.add_subplot(gs[3,:5],projection='3d');x=tiles.x.values/1000;y=tiles.y.values/1000;z=tiles.angular_entropy.values;a6.plot_trisurf(x,y,z,cmap='viridis',linewidth=.15,antialiased=True);a6.view_init(32,-62);a6.set(xlabel='x position',ylabel='y position',zlabel='entropy',title='3-D spatial phenotype');a6.set_xticklabels([]);a6.set_yticklabels([]);panel(a6,'g')
 assoc=pd.read_csv(ROOT/'outputs'/'cpu_pilot'/'publication'/'table_2_entropy_associations.csv');a7=fig.add_subplot(gs[3,7:]);assoc['label']=assoc.site.str[0]+' · '+assoc.outcome;yy=np.arange(len(assoc))[::-1];lo=assoc.spearman_rho-assoc.bootstrap_ci_lower;hi=assoc.bootstrap_ci_upper-assoc.spearman_rho;a7.errorbar(assoc.spearman_rho,yy,xerr=[lo,hi],fmt='o',color=TEAL,ecolor='#82979C',capsize=2,ms=4);a7.axvline(0,color='#888',lw=.7);a7.set_yticks(yy,assoc.label,fontsize=7);a7.set_xlabel('Spearman ρ (95% bootstrap CI)');a7.set_title('Participant-level phenotype');clean(a7);panel(a7,'h')
 save(fig,'figure_1_mega')

def figure2():
 rgb1,m1,t1=load('076',1);rgb2,m2,t2=load('076',2);pairs=pd.read_csv(ROOT/'outputs'/'flagship'/'adjacent_replication'/'table_adjacent_section_pairs.csv');agree=pd.read_csv(ROOT/'outputs'/'flagship'/'adjacent_replication'/'table_adjacent_section_agreement.csv');repl=pd.read_csv(ROOT/'outputs'/'flagship'/'adjacent_replication'/'table_replication_section_associations.csv')
 fig=plt.figure(figsize=(7.2,6.05));gs=GridSpec(3,12,figure=fig,height_ratios=[1.72,1.72,1.9],hspace=.30,wspace=.52)
 a=fig.add_subplot(gs[0,:6]);show_tissue(a,rgb1,'P076 · serial section 1');panel(a,'a');b=fig.add_subplot(gs[0,6:]);show_tissue(b,rgb2,'P076 · serial section 2');panel(b,'b')
 c=fig.add_subplot(gs[1,:6]);norm,cmap=entropy_map(c,rgb1,t1,'Section 1 entropy map');panel(c,'c');d=fig.add_subplot(gs[1,6:]);entropy_map(d,rgb2,t2,'Section 2 entropy map');panel(d,'d');cb=fig.colorbar(mpl.cm.ScalarMappable(norm=norm,cmap=cmap),ax=[c,d],fraction=.018,pad=.015);cb.set_label('angular entropy')
 e=fig.add_subplot(gs[2,:4]);
 for site,color in [('Medial',TEAL),('Lateral',RED)]:
  q=pairs[pairs.replication_site==site];e.scatter(q.angular_entropy_median_rank1,q.angular_entropy_median_rank2,s=15,alpha=.65,label=site,color=color,edgecolor='white',lw=.25)
 e.plot([.82,1],[.82,1],ls='--',color='#777',lw=.8);e.set(xlabel='Section 1 entropy',ylabel='Section 2 entropy');e.legend(frameon=False);clean(e);panel(e,'e')
 f=fig.add_subplot(gs[2,4:8]);
 for site,color in [('Medial',TEAL),('Lateral',RED)]:
  q=pairs[pairs.replication_site==site];x=(q.angular_entropy_median_rank1+q.angular_entropy_median_rank2)/2;y=q.angular_entropy_median_rank2-q.angular_entropy_median_rank1;f.scatter(x,y,s=14,alpha=.55,color=color,label=site)
  f.axhline(y.mean(),color=color,lw=1)
 f.axhline(0,color='#777',lw=.6);f.set(xlabel='Mean entropy',ylabel='Section 2 − section 1');clean(f);panel(f,'f')
 g=fig.add_subplot(gs[2,9:]);r=repl[(repl.feature=='angular_entropy_median')].copy();r['label']=r.site.str[0]+' · '+r.outcome.str.replace('mean_total_','').str.upper();yy=np.arange(len(r))[::-1];g.errorbar(r.replication_rho,yy,xerr=[r.replication_rho-r.bootstrap_ci_lower,r.bootstrap_ci_upper-r.replication_rho],fmt='o',color=TEAL,ecolor='#82979C',capsize=2,ms=4);g.axvline(0,color='#777',lw=.7);g.set_yticks(yy,r.label,fontsize=6.2);g.set_xlabel('Section 2 Spearman ρ');clean(g);panel(g,'g')
 save(fig,'figure_2_mega')

def figure3():
 rgb,mask,tiles=load('076');plm=Image.open(Path(r'<DATA_ROOT>\data\annotations\images\076_Medial_PLM_PLM.png')).convert('RGB')
 data=pd.read_csv(ROOT/'outputs'/'flagship'/'mechanistic'/'table_mechanistic_associations.csv');data=data[data.feature=='angular_entropy_median'].copy();order=['hhgs_safo_loss','hhgs_structure','oarsi_grade','oarsi_stage','hhgs_cells','hhgs_tidemark','plm_superficial_disorganization','plm_deep_disorganization','plm_total_disorganization'];labels=['Safranin-O loss','HHGS structure','OARSI grade','OARSI stage','HHGS cells','HHGS tidemark','PLM superficial','PLM deep','PLM total'];data['col']=data.site.str[:3]+' '+data.section_rank.astype(str);mat=data.pivot(index='component',columns='col',values='spearman_rho').reindex(order);q=data.pivot(index='component',columns='col',values='q_value_bh_global').reindex(index=mat.index,columns=mat.columns)
 fig=plt.figure(figsize=(7.2,6.1));gs=GridSpec(3,12,figure=fig,height_ratios=[1.72,1.85,1.85],hspace=.34,wspace=.56)
 a=fig.add_subplot(gs[0,:6]);show_tissue(a,rgb,'Safranin-O bright field');panel(a,'a');b=fig.add_subplot(gs[0,6:]);show_tissue(b,crop_foreground(np.asarray(plm)),'Polarized-light microscopy');panel(b,'b')
 c=fig.add_subplot(gs[1,:6]);cmap=mpl.colors.LinearSegmentedColormap.from_list('nostos',[BLUE,'#F7F7F5',RED]);im=c.imshow(mat,cmap=cmap,vmin=-.5,vmax=.5,aspect='auto');c.set_xticks(range(4),mat.columns);c.set_yticks(range(9),labels);c.tick_params(length=0);c.spines[:].set_visible(False)
 for i in range(9):
  for j in range(4):
   v=mat.iloc[i,j]
   if np.isfinite(v):c.text(j,i,f'{v:.2f}{"*" if q.iloc[i,j]<.05 else ""}',ha='center',va='center',fontsize=7,color='white' if v<-.32 else INK)
 cb=fig.colorbar(im,ax=c,fraction=.035,pad=.02);cb.set_label('Spearman ρ');panel(c,'c')
 d=fig.add_subplot(gs[1,8:]);med=data[(data.site=='Medial')&(data.section_rank==2)].set_index('component').reindex(order);yy=np.arange(len(med))[::-1];d.errorbar(med.spearman_rho,yy,xerr=[med.spearman_rho-med.bootstrap_ci_lower,med.bootstrap_ci_upper-med.spearman_rho],fmt='o',color=TEAL,ecolor='#82979C',capsize=2,ms=4);d.axvline(0,color='#777',lw=.7);d.set_yticks(yy,['SafO loss','Structure','Grade','Stage','Cells','Tidemark','PLM superficial','PLM deep','PLM total'],fontsize=6.5);d.set_xlabel('Medial section 2 ρ');clean(d);panel(d,'d')
 e=fig.add_subplot(gs[2,:5]);norm,cmap2=entropy_map(e,rgb,tiles,'Spatial entropy landscape');panel(e,'e')
 f=fig.add_subplot(gs[2,5:]);f.axis('off');panel(f,'f');f.text(.02,.9,'Working biological model',fontsize=10,fontweight='bold')
 zones=[('Superficial zone','#DDEBF0'),('Middle zone','#F0DDBB'),('Deep zone','#D7C3A7'),('Subchondral bone','#C9B09A')]
 for i,(name,color) in enumerate(zones):f.add_patch(Rectangle((.05,.68-i*.15),.38,.13,facecolor=color,edgecolor='white'));f.text(.24,.745-i*.15,name,ha='center',va='center',fontsize=7)
 f.add_patch(FancyArrowPatch((.48,.67),(.68,.67),arrowstyle='-|>',mutation_scale=11,color=RED,lw=1.4));f.text(.58,.72,'OA lesions',ha='center',color=RED,fontweight='bold')
 f.text(.7,.78,'surface fissures',fontsize=8);f.text(.7,.64,'cell clusters',fontsize=8);f.text(.7,.50,'aligned boundaries',fontsize=8);f.text(.7,.34,'↓ angular entropy',fontsize=9,fontweight='bold',color=BLUE)
 f.text(.05,.08,'Supported: structural, cellular and superficial-zone associations\nNot established: collagen specificity, causality or mechanics',fontsize=7.5,color='#444')
 save(fig,'figure_3_mega')

def figure4():
 pred=pd.read_csv(ROOT/'outputs'/'cpu_pilot'/'validation'/'table_nested_cv_predictions.csv')
 abl=pd.read_csv(ROOT/'outputs'/'cpu_pilot'/'publication'/'table_4_nested_cv_ablations.csv')
 robust=pd.read_csv(ROOT/'outputs'/'cpu_pilot'/'robustness'/'tile_robustness_summary.csv')
 boundary=pd.read_csv(ROOT/'outputs'/'cpu_pilot'/'robustness'/'mask_sensitivity_summary.csv')
 severity=pd.read_csv(ROOT/'outputs'/'flagship'/'severity_benchmark'/'table_severity_nested_cv.csv')
 sevpred=pd.read_csv(ROOT/'outputs'/'flagship'/'severity_benchmark'/'table_severity_predictions.csv')
 feasible=pd.read_csv(ROOT/'outputs'/'flagship'/'severity_benchmark'/'table_prior_four_class_feasibility.csv')
 permutation=json.loads((ROOT/'outputs'/'cpu_pilot'/'validation'/'primary_permutation_test.json').read_text())
 fig=plt.figure(figsize=(7.2,6.15));gs=GridSpec(3,12,figure=fig,height_ratios=[1.75,1.65,1.7],hspace=.42,wspace=.76)
 a=fig.add_subplot(gs[0,:5]);q=pred[(pred.outcome=='mean_total_plm')&(pred.model=='fft_entropy')]
 a.scatter(q.observed,q.predicted,color=TEAL,s=23,alpha=.68,edgecolor='white',lw=.35)
 lo=min(q.observed.min(),q.predicted.min());hi=max(q.observed.max(),q.predicted.max());a.plot([lo,hi],[lo,hi],ls='--',color='#777',lw=.8)
 a.set(xlabel='Observed PLM score',ylabel='Out-of-fold predicted PLM',title='Participant-grouped prediction');clean(a);panel(a,'a')
 b=fig.add_subplot(gs[0,6:]);models=['FFT angular entropy','FFT multiscale','Conventional texture','Combined'];colors=[TEAL,BLUE,'#A7B2B5',GOLD]
 plm=abl[abl.outcome=='PLM'].set_index('model').reindex(models);yy=np.arange(4)[::-1]
 b.barh(yy,plm.mae,color=colors,height=.62);b.set_yticks(yy,['Entropy','Multiscale FFT','Conventional','Combined']);b.set_xlabel('Nested-CV MAE (lower is better)');b.set_title('Comparator ablation');b.set_xlim(0,1.42);clean(b);panel(b,'b')
 for y,v in zip(yy,plm.mae):b.text(v+.025,y,f'{v:.2f}',va='center',fontsize=7)
 c=fig.add_subplot(gs[1,:4]);null=permutation['null_mae_mean'];sd=permutation['null_mae_sd'];obs=permutation['observed_mae']
 c.errorbar([0],[null],yerr=[sd],fmt='o',color='#8A989C',capsize=4,label='Permutation null ± SD');c.scatter([1],[obs],s=38,color=TEAL,label='Observed FFT')
 c.set_xticks([0,1],['Null','Observed']);c.set_ylabel('PLM nested-CV MAE');c.set_title('Complete-pipeline falsification');c.set_ylim(1.05,1.42);c.text(.5,1.075,'p=0.001',ha='center',fontsize=8,fontweight='bold',color=TEAL);clean(c);panel(c,'c')
 d=fig.add_subplot(gs[1,4:7]);robust=robust.sort_values('angular_entropy_relative_drift_median');y=np.arange(len(robust));labels=robust.perturbation.str.replace('_',' ')
 d.barh(y,100*robust.angular_entropy_relative_drift_median,color=TEAL,height=.58,label='median');d.scatter(100*robust.angular_entropy_relative_drift_p95,y,color=RED,s=14,label='95th percentile',zorder=3)
 d.set_yticks(y,labels,fontsize=6.5);d.set_xlabel('Absolute entropy drift (%)');d.set_title('Acquisition perturbations');d.legend(frameon=False,fontsize=6,loc='lower right');clean(d);panel(d,'d')
 e=fig.add_subplot(gs[1,8:]);e.plot(boundary.delta_um,100*boundary.entropy_drift_median,'o-',color=TEAL,lw=1.2,ms=4,label='median');e.plot(boundary.delta_um,100*boundary.entropy_drift_p95,'s-',color=RED,lw=1.0,ms=3.5,label='95th percentile')
 e.axvline(0,color='#999',lw=.6);e.set(xlabel='Mask-boundary change (µm)',ylabel='Absolute entropy drift (%)',title='Boundary sensitivity');e.legend(frameon=False,fontsize=6);clean(e);panel(e,'e')
 f=fig.add_subplot(gs[2,:6]);sev=severity.set_index('model').reindex(['fft_entropy','fft_multiscale','conventional_texture','combined']);x=np.arange(4);w=.23
 f.bar(x-w,sev.balanced_accuracy,w,color=TEAL,label='balanced accuracy');f.bar(x,sev.macro_f1,w,color=BLUE,label='macro-F1');f.bar(x+w,sev.roc_auc,w,color=GOLD,label='ROC area')
 f.axhline(.5,color='#888',ls='--',lw=.7);f.set_xticks(x,['Entropy','Multiscale','Conventional','Combined']);f.set_ylim(0,1);f.set_ylabel('Participant-grouped performance');f.set_title('Moderate-or-greater severity benchmark');f.legend(frameon=False,ncol=3,fontsize=6,loc='upper center');clean(f);f.text(.01,.98,'f',transform=f.transAxes,fontsize=9,fontweight='bold',va='top')
 g=fig.add_subplot(gs[2,7:]);bins=np.linspace(0,1,9);neg=sevpred[(sevpred.model=='fft_entropy')&(sevpred.outcome==0)].probability;pos=sevpred[(sevpred.model=='fft_entropy')&(sevpred.outcome==1)].probability
 g.hist(neg,bins=bins,color='#AAB6B9',alpha=.8,label='lower severity');g.hist(pos,bins=bins,color=RED,alpha=.72,label='moderate+');g.set(xlabel='Out-of-fold probability',ylabel='Participants',title='Prediction distribution');g.legend(frameon=False,fontsize=6);clean(g);panel(g,'g')
 counts=feasible.iloc[0][['early','mild','moderate','severe']].astype(int).tolist();g.text(.98,.96,'Four-class counts\n'+ ' / '.join(map(str,counts))+'\nnot fivefold-feasible',transform=g.transAxes,ha='right',va='top',fontsize=7,bbox=dict(facecolor='white',edgecolor='#C4CCCE',pad=2))
 save(fig,'figure_4_mega')

def figure1_nature():
 rgb,mask,tiles=load('076');valid=tiles[(tiles.x>=0)&(tiles.y>=0)&(tiles.x+256<=rgb.shape[1])&(tiles.y+256<=rgb.shape[0])].copy()
 fig=plt.figure(figsize=(7.2,7.15));gs=GridSpec(5,24,figure=fig,height_ratios=[.64,2.05,1.18,1.18,2.0],hspace=.28,wspace=.34)
 # a: compact image-led pipeline; the same specimen persists through every operation.
 ax=fig.add_subplot(gs[0,:]);ax.axis('off');panel(ax,'a')
 stages=[('section',rgb),('semantic mask',proposal_overlay(rgb,mask,.56))]
 for i,(lab,img) in enumerate(stages):
  x=.025+i*.165;ia=ax.inset_axes([x,.08,.12,.82]);ia.imshow(thumb(img,420));ia.axis('off');ax.text(x+.06,.01,lab,ha='center',fontsize=6.2)
 for i,(lab,sym) in enumerate([('physical tiles','440 µm'),('2-D FFT','F(kx,ky)'),('angular profile','p(θ)'),('participant value','median H')]):
  x=.37+i*.155;ax.text(x+.055,.58,sym,ha='center',va='center',fontsize=8,fontweight='bold',color=TEAL)
  ax.text(x+.055,.16,lab,ha='center',fontsize=6.2,color='#4F585C')
 for x in [.15,.315,.46,.615,.77]:ax.add_patch(FancyArrowPatch((x,.49),(x+.038,.49),arrowstyle='-|>',mutation_scale=7,color='#718086',lw=.7))
 # b-c: specimen and segmentation; no decorative framing.
 b=fig.add_subplot(gs[1,:10]);show_tissue(b,rgb);b.text(.02,.97,'whole osteochondral section',transform=b.transAxes,va='top',fontsize=7,bbox=dict(fc='white',ec='none',alpha=.86,pad=1));panel(b,'b')
 c=fig.add_subplot(gs[1,10:17]);show_tissue(c,proposal_overlay(rgb,mask,.58));c.text(.02,.97,'semantic overlay',transform=c.transAxes,va='top',fontsize=7,bbox=dict(fc='white',ec='none',alpha=.86,pad=1));panel(c,'c')
 vals=[v for v in np.unique(mask) if v!=0][:3];cols=['#2CB67D','#F2C14E','#E85D3F'];names=['cartilage','interface','bone']
 for j,(v,col,name) in enumerate(zip(vals,cols,names)):
  m=fig.add_subplot(gs[1,17+j*2:19+j*2]);layer=np.full((*mask.shape,3),248,np.uint8);layer[mask==v]=(np.asarray(mpl.colors.to_rgb(col))*255).astype(np.uint8);m.imshow(layer);m.axis('off');m.set_title(name,fontsize=6,pad=1);panel(m,chr(ord('d')+j))
 # g-l: three real tiles spanning the entropy distribution and their paired Fourier domains.
 picks=[]
 for q in [.12,.50,.88]:
  target=valid.angular_entropy.quantile(q);picks.append(valid.iloc[(valid.angular_entropy-target).abs().argmin()])
 for j,row in enumerate(picks):
  tile=rgb[int(row.y):int(row.y)+256,int(row.x):int(row.x)+256];x0=j*8
  im=fig.add_subplot(gs[2,x0:x0+4]);im.imshow(tile);im.axis('off');im.set_title(['low entropy','median entropy','high entropy'][j],fontsize=6.4,pad=1);panel(im,chr(ord('g')+j*2));im.plot([14,72],[237,237],color='white',lw=1.5);im.text(43,227,'100 µm',color='white',ha='center',fontsize=5.5)
  sp=fig.add_subplot(gs[2,x0+4:x0+8]);sp.imshow(_spectrum_preview(tile,np.ones(tile.shape[:2],np.uint8)));sp.axis('off');sp.set_title(f'H = {row.angular_entropy:.3f}',fontsize=6.4,pad=1);panel(sp,chr(ord('h')+j*2))
 # m-o: spatial field, black terrain inset, and participant inference.
 m=fig.add_subplot(gs[3:,:8]);norm,cmap=entropy_map(m,rgb,tiles,'measured spatial field',True);panel(m,'m');cb=fig.colorbar(mpl.cm.ScalarMappable(norm=norm,cmap=cmap),ax=m,fraction=.033,pad=.012);cb.set_label('angular entropy',fontsize=6);cb.ax.tick_params(labelsize=5.5,length=2)
 n=fig.add_subplot(gs[3:,8:15],projection='3d');x=tiles.x.values/1000;y=tiles.y.values/1000;z=tiles.angular_entropy.values;n.plot_trisurf(x,y,z,cmap='magma',linewidth=.05,antialiased=True);n.view_init(35,-58);n.set_facecolor('#07080B');n.xaxis.pane.fill=False;n.yaxis.pane.fill=False;n.zaxis.pane.fill=False;n.grid(False);n.set_xticks([]);n.set_yticks([]);n.tick_params(labelsize=5,colors='#444');n.set_zlabel('entropy',fontsize=6,labelpad=1);n.set_title('same field · feature-height terrain',fontsize=6.5,pad=1);panel(n,'n')
 assoc=pd.read_csv(ROOT/'outputs'/'cpu_pilot'/'publication'/'table_2_entropy_associations.csv');o=fig.add_subplot(gs[3:,16:]);assoc['label']=assoc.site.str[0]+' · '+assoc.outcome;yy=np.arange(len(assoc))[::-1];o.errorbar(assoc.spearman_rho,yy,xerr=[assoc.spearman_rho-assoc.bootstrap_ci_lower,assoc.bootstrap_ci_upper-assoc.spearman_rho],fmt='o',color=TEAL,ecolor='#84969B',capsize=1.7,ms=3.2,lw=.8);o.axvline(0,color='#777',lw=.6);o.set_yticks(yy,assoc.label,fontsize=5.8);o.set_xlabel('Spearman ρ (95% CI)',fontsize=6.5);o.set_title('participant-level convergence',fontsize=6.5,pad=2);clean(o);panel(o,'o')
 save(fig,'figure_1_mega')

def figure1_reference():
 rgb,mask,tiles=load('076');valid=tiles[(tiles.x>=0)&(tiles.y>=0)&(tiles.x+256<=rgb.shape[1])&(tiles.y+256<=rgb.shape[0])].copy()
 fig=plt.figure(figsize=(7.2,5.65));gs=GridSpec(3,30,figure=fig,height_ratios=[2.15,1.38,2.25],hspace=.26,wspace=.30)
 def scale(ax,um=1000,color='black'):
  shown=ax.images[0].get_array();px=um*1.72*shown.shape[1]/rgb.shape[1];y=shown.shape[0]*.94;x=shown.shape[1]*.05;ax.plot([x,x+px],[y,y],color=color,lw=1.7,solid_capstyle='butt');ax.text(x+px/2,y-shown.shape[0]*.025,f'{um/1000:g} mm' if um>=1000 else f'{um:g} µm',ha='center',va='bottom',fontsize=5.4,color=color,bbox=dict(fc='white',ec='none',alpha=.75,pad=.3))
 a=fig.add_subplot(gs[0,:10]);show_tissue(a,rgb,'osteochondral specimen');panel(a,'a');scale(a)
 b=fig.add_subplot(gs[0,10:20]);show_tissue(b,proposal_overlay(rgb,mask,.60),'segmentation overlay');panel(b,'b');scale(b)
 b.text(.03,.97,'green = cartilage proposal',transform=b.transAxes,color='#087D57',fontsize=5.5,fontweight='bold',va='top',bbox=dict(fc='white',ec='none',alpha=.78,pad=.5))
 layer=np.full((*mask.shape,3),250,np.uint8);layer[mask==1]=(np.asarray(mpl.colors.to_rgb('#2CB67D'))*255).astype(np.uint8)
 c=fig.add_subplot(gs[0,20:25]);c.imshow(layer);c.axis('off');c.set_title('cartilage proposal',pad=1);panel(c,'c')
 from scipy import ndimage
 edge=ndimage.binary_dilation(mask==1,iterations=5)^ndimage.binary_erosion(mask==1,iterations=5);outlined=rgb.copy();outlined[edge]=np.asarray([15,77,146],np.uint8)
 d=fig.add_subplot(gs[0,25:]);show_tissue(d,outlined,'proposal boundary');panel(d,'d')
 picks=[]
 for q in [.12,.50,.88]:target=valid.angular_entropy.quantile(q);picks.append(valid.iloc[(valid.angular_entropy-target).abs().argmin()])
 for j,row in enumerate(picks):
  tile=rgb[int(row.y):int(row.y)+256,int(row.x):int(row.x)+256];x0=j*10
  ia=fig.add_subplot(gs[1,x0:x0+5]);ia.imshow(tile);ia.axis('off');ia.set_title(['low H','median H','high H'][j],pad=1);panel(ia,chr(ord('e')+j*2));ia.plot([14,72],[237,237],color='white',lw=1.4);ia.text(43,226,'100 µm',color='white',ha='center',fontsize=5.2)
  sp=fig.add_subplot(gs[1,x0+5:x0+10]);sp.imshow(_spectrum_preview(tile,np.ones(tile.shape[:2],np.uint8)));sp.axis('off');sp.set_title(f'FFT power · H={row.angular_entropy:.3f}',pad=1);panel(sp,chr(ord('f')+j*2))
 k=fig.add_subplot(gs[2,:11]);norm,cmap=entropy_map(k,rgb,tiles,'spatial entropy map',True);panel(k,'k');cb=fig.colorbar(mpl.cm.ScalarMappable(norm=norm,cmap=cmap),ax=k,fraction=.031,pad=.01);cb.set_label('H',fontsize=6);cb.ax.tick_params(labelsize=5.2,length=2)
 l=fig.add_subplot(gs[2,11:21],projection='3d');x=tiles.x.values/1000;y=tiles.y.values/1000;z=tiles.angular_entropy.values;l.plot_trisurf(x,y,z,cmap='magma',linewidth=.04,antialiased=True);l.view_init(36,-60);l.set_facecolor('#07080A');l.xaxis.pane.fill=False;l.yaxis.pane.fill=False;l.zaxis.pane.fill=False;l.grid(False);l.set_xticks([]);l.set_yticks([]);l.set_zticks([]);l.text2D(.06,.08,'feature height  H ↑',transform=l.transAxes,color='white',fontsize=5.6);l.set_title('feature-height terrain',pad=1);panel(l,'l')
 assoc=pd.read_csv(ROOT/'outputs'/'cpu_pilot'/'publication'/'table_2_entropy_associations.csv');m=fig.add_subplot(gs[2,22:]);assoc['label']=assoc.site.str[0]+' · '+assoc.outcome;yy=np.arange(len(assoc))[::-1];m.errorbar(assoc.spearman_rho,yy,xerr=[assoc.spearman_rho-assoc.bootstrap_ci_lower,assoc.bootstrap_ci_upper-assoc.spearman_rho],fmt='o',color=TEAL,ecolor='#84969B',capsize=1.6,ms=3,lw=.75);m.axvline(0,color='#777',lw=.55);m.set_yticks(yy,assoc.label,fontsize=5.6);m.set_xlabel('Spearman ρ (95% CI)',fontsize=6.2);m.set_title('participant-level associations',pad=1);clean(m);panel(m,'m')
 save(fig,'figure_1_mega')

if __name__=='__main__': figure1_reference();figure2();figure3();figure4()
