"""Build eight microscopy-led NOSTOS megafigures with distinct visual grammars."""
from __future__ import annotations
import sys
from pathlib import Path
import numpy as np
import pandas as pd
from PIL import Image, ImageFilter
import matplotlib as mpl
import matplotlib.pyplot as plt
from matplotlib.gridspec import GridSpec
from matplotlib.patches import Rectangle
from scipy import ndimage
from scipy.interpolate import griddata
from scipy.spatial import Delaunay
from scipy.stats import gaussian_kde
from sklearn.decomposition import PCA
from sklearn.preprocessing import StandardScaler

sys.path.insert(0,str(Path(__file__).resolve().parent))
import build_megafigures as base

ROOT=base.ROOT;OUT=base.OUT;TEAL='#237A83';BLUE='#0F4D92';RED='#B64342';GOLD='#D49B2A';GRAY='#87969B';LIGHT='#F4F6F5'
mpl.rcParams.update({'font.family':'serif','font.serif':['Times New Roman'],'font.size':6.6,'axes.titlesize':6.8,'axes.labelsize':6.4,'xtick.labelsize':5.6,'ytick.labelsize':5.6,'axes.linewidth':.5,'svg.fonttype':'none','savefig.dpi':600,'figure.facecolor':'white','axes.facecolor':'white'})

def p(ax,s):
 fn=ax.text2D if hasattr(ax,'text2D') else ax.text
 fn(.012,.985,s,transform=ax.transAxes,fontsize=7.2,fontweight='bold',va='top',ha='left',zorder=30,bbox=dict(boxstyle='square,pad=.18',fc='white',ec='#D5D9DA',lw=.35,alpha=.96))
def clean(ax):ax.spines[['top','right']].set_visible(False);ax.tick_params(width=.5,length=2)
def save(fig,n):
 for ext in ('png','svg'):fig.savefig(OUT/f'figure_{n}_mega.{ext}',bbox_inches='tight',facecolor='white',pad_inches=.03)
 fig.savefig(OUT/f'figure_{n}_mega.jpg',bbox_inches='tight',facecolor='white',pad_inches=.03,pil_kwargs={'quality':97});plt.close(fig)
def tile_at(rgb,row):return rgb[int(row.y):int(row.y)+256,int(row.x):int(row.x)+256]
def usable(t,rgb):return t[(t.x>=0)&(t.y>=0)&(t.x+256<=rgb.shape[1])&(t.y+256<=rgb.shape[0])]
def field(t,key='angular_entropy',n=80):
 x=t.x.to_numpy()+128;y=t.y.to_numpy()+128;gx,gy=np.meshgrid(np.linspace(x.min(),x.max(),n),np.linspace(y.min(),y.max(),n));gz=griddata((x,y),t[key],(gx,gy),method='linear');return gx,gy,gz
def spectrum(tile):
 g=np.asarray(Image.fromarray(tile).convert('L'),float);g-=g.mean();s=np.log1p(np.abs(np.fft.fftshift(np.fft.fft2(g))));return s

def figure1():base.figure1_reference()

def figure2():
 rgb,mask,t=base.load('076');t=usable(t,rgb);qs=[]
 for q in [.15,.5,.85]:v=t.angular_entropy.quantile(q);qs.append(t.iloc[(t.angular_entropy-v).abs().argmin()])
 fig=plt.figure(figsize=(7.2,3.45));gs=GridSpec(3,12,figure=fig,hspace=.06,wspace=.08)
 scales=[1,.5,.25,.125]
 for i,row in enumerate(qs):
  im=tile_at(rgb,row)
  for j,s in enumerate(scales):
   a=fig.add_subplot(gs[i,j*2]);small=Image.fromarray(im).resize((max(8,int(256*s)),)*2,Image.Resampling.LANCZOS).resize((256,256),Image.Resampling.NEAREST);a.imshow(small);a.axis('off')
   b=fig.add_subplot(gs[i,j*2+1]);b.imshow(spectrum(np.asarray(small)),cmap='magma');b.axis('off')
   if j==0:p(a,chr(97+i))
  if i==0:
   c=fig.add_subplot(gs[:,8:],projection='3d');x=np.linspace(-1,1,256);xx,yy=np.meshgrid(x,x)
   for k,s in enumerate(scales):
    sm=Image.fromarray(im).resize((max(8,int(256*s)),)*2,Image.Resampling.LANCZOS).resize((256,256),Image.Resampling.BILINEAR);sp=spectrum(np.asarray(sm));prof=sp.mean(0);c.plot(np.arange(256),np.full(256,k),prof/prof.max(),color=[TEAL,BLUE,GOLD,RED][k],lw=.9)
   c.view_init(28,-62);c.set(xticks=[],yticks=[],zticks=[]);c.grid(False);c.set_title('');p(c,'d')
 save(fig,2)

def figure3():
 rgb,mask,t=base.load('076');fig=plt.figure(figsize=(7.2,5.45));gs=GridSpec(2,4,figure=fig,hspace=.22,wspace=.26)
 a=fig.add_subplot(gs[0,:2]);a.imshow(rgb);sx=1;sy=1
 for r in t.itertuples():
  th=np.deg2rad(r.orientation_degrees);L=58*(.35+r.anisotropy);cx=r.x+128;cy=r.y+128;a.plot([cx-L*np.cos(th),cx+L*np.cos(th)],[cy-L*np.sin(th),cy+L*np.sin(th)],color=GOLD,lw=.65,alpha=.78)
 a.axis('off');p(a,'a')
 b=fig.add_subplot(gs[0,2],projection='polar');ang=np.deg2rad(t.orientation_degrees.to_numpy());w=t.anisotropy.to_numpy();bins=np.linspace(0,np.pi,25);h,_=np.histogram(ang,bins,weights=w);b.bar((bins[:-1]+bins[1:])/2,h,width=np.diff(bins),color=TEAL,alpha=.8,edgecolor='white',lw=.25);b.set_theta_zero_location('E');b.set_thetamin(0);b.set_thetamax(180);b.set_yticks([]);p(b,'b')
 c=fig.add_subplot(gs[0,3],projection='polar');order=np.argsort(t.angular_entropy.to_numpy());theta=np.linspace(0,4*np.pi,len(t));rad=np.linspace(.15,1,len(t));c.scatter(theta,rad,c=t.angular_entropy.to_numpy()[order],cmap='viridis',s=8+40*t.anisotropy.to_numpy()[order],alpha=.8,edgecolor='none');c.set_axis_off();p(c,'c')
 d=fig.add_subplot(gs[1,:2]);gx,gy,gz=field(t,'orientation_degrees',55);u=np.cos(np.deg2rad(gz));v=np.sin(np.deg2rad(gz));speed=griddata((t.x+128,t.y+128),t.anisotropy,(gx,gy),method='linear');d.streamplot(gx[0],gy[:,0],u,v,color=speed,cmap='magma',density=1.35,linewidth=.5,arrowsize=.45);d.invert_yaxis();d.axis('off');p(d,'d')
 e=fig.add_subplot(gs[1,2:]);x=t.x+128;y=t.y+128;e.scatter(x,y,c=t.orientation_degrees,cmap='twilight',s=20+90*t.anisotropy,alpha=.82,edgecolor='white',lw=.2);e.set_aspect('equal');e.invert_yaxis();e.axis('off');p(e,'e')
 save(fig,3)

def figure4():
 rgb,mask,t=base.load('076');gx,gy,gz=field(t);fig=plt.figure(figsize=(7.2,4.85));gs=GridSpec(2,8,figure=fig,hspace=.12,wspace=.12)
 a=fig.add_subplot(gs[0,:2]);a.imshow(rgb);a.imshow(gz,cmap='magma',alpha=.62,extent=[gx.min(),gx.max(),gy.max(),gy.min()]);a.axis('off');p(a,'a')
 b=fig.add_subplot(gs[0,2:4]);b.contour(gx,gy,gz,levels=12,cmap='viridis',linewidths=.7);b.invert_yaxis();b.set_aspect('equal');b.axis('off');p(b,'b')
 c=fig.add_subplot(gs[0,4:],projection='3d');c.plot_surface(gx,gy,gz,cmap='magma',rstride=2,cstride=2,linewidth=0,antialiased=True);c.view_init(34,-58);c.set_facecolor('#07080A');c.set_xticks([]);c.set_yticks([]);c.set_zticks([]);c.grid(False);p(c,'c')
 d=fig.add_subplot(gs[1,:3]);pts=np.column_stack([t.x+128,t.y+128]);tri=Delaunay(pts);d.scatter(pts[:,0],pts[:,1],c=t.angular_entropy,cmap='viridis',s=12,zorder=2)
 for s in tri.simplices:
  for u,v in [(s[0],s[1]),(s[1],s[2]),(s[2],s[0])]:d.plot(pts[[u,v],0],pts[[u,v],1],color='#AAB4B7',lw=.3,alpha=.45)
 d.invert_yaxis();d.set_aspect('equal');d.axis('off');p(d,'d')
 e=fig.add_subplot(gs[1,3:6]);thr=np.linspace(np.nanmin(gz),np.nanmax(gz),44);stack=[]
 for q in thr:stack.append(np.nan_to_num(gz)>q)
 binary=np.asarray(stack).reshape(len(thr),-1);order=np.argsort(binary.sum(axis=0));sel=order[np.linspace(0,len(order)-1,120,dtype=int)];e.imshow(binary[:,sel],cmap=mpl.colors.ListedColormap([LIGHT,GOLD]),aspect='auto',origin='lower',interpolation='nearest');e.set_xticks([]);e.set_yticks([]);e.spines[:].set_visible(False);p(e,'e')
 f=fig.add_subplot(gs[1,6:]);counts=[]
 for q in thr:counts.append(ndimage.label(np.nan_to_num(gz)>q)[1])
 f.plot(thr,counts,color=TEAL,lw=1.1);f.fill_between(thr,0,counts,color=TEAL,alpha=.16);clean(f);f.set_yticks([]);p(f,'f')
 save(fig,4)

def figure5():
 rgb,mask,t=base.load('076');plm=np.asarray(Image.open(Path(r'<DATA_ROOT>\data\annotations\images\076_Medial_PLM_PLM.png')).convert('RGB'));fig=plt.figure(figsize=(7.2,4.45));gs=GridSpec(3,8,figure=fig,hspace=.10,wspace=.10)
 a=fig.add_subplot(gs[0,:4]);a.imshow(rgb);a.axis('off');p(a,'a');b=fig.add_subplot(gs[0,4:]);b.imshow(plm);b.axis('off');p(b,'b')
 ys=[.18,.42,.66,.84]
 for i,q in enumerate(ys):
  yy=int(q*rgb.shape[0]);xx=int(.38*rgb.shape[1]);crop=rgb[max(0,yy-150):yy+150,max(0,xx-220):xx+220];c=fig.add_subplot(gs[1,i*2]);c.imshow(crop);c.axis('off')
  yp=int(q*plm.shape[0]);xp=int(.38*plm.shape[1]);crop2=plm[max(0,yp-150):yp+150,max(0,xp-220):xp+220];d=fig.add_subplot(gs[1,i*2+1]);d.imshow(crop2);d.axis('off')
  if i==0:p(c,'c')
 data=pd.read_csv(ROOT/'outputs'/'flagship'/'mechanistic'/'table_mechanistic_associations.csv');data=data[data.feature=='angular_entropy_median'];data['col']=data.site.str[0]+data.section_rank.astype(str);mat=data.pivot(index='component',columns='col',values='spearman_rho');e=fig.add_subplot(gs[2,:5]);e.imshow(mat,cmap=mpl.colors.LinearSegmentedColormap.from_list('x',[BLUE,'white',RED]),vmin=-.5,vmax=.5,aspect='auto');e.set_xticks([]);e.set_yticks([]);e.spines[:].set_visible(False);p(e,'d')
 f=fig.add_subplot(gs[2,5:]);med=data[(data.site=='Medial')&(data.section_rank==2)];f.scatter(med.spearman_rho,np.arange(len(med)),c=med.spearman_rho,cmap='coolwarm',vmin=-.5,vmax=.5,s=30);f.hlines(np.arange(len(med)),med.bootstrap_ci_lower,med.bootstrap_ci_upper,color=GRAY,lw=.8);f.axvline(0,color='#777',lw=.5);f.set_yticks([]);clean(f);p(f,'e')
 save(fig,5)

def figure6():
 r1,m1,t1=base.load('076',1);r2,m2,t2=base.load('076',2);fig=plt.figure(figsize=(7.2,5.45));gs=GridSpec(3,8,figure=fig,hspace=.18,wspace=.2)
 for ax,img,lab in [(fig.add_subplot(gs[0,:3]),r1,'a'),(fig.add_subplot(gs[0,3:6]),r2,'b')]:ax.imshow(img);ax.axis('off');p(ax,lab)
 ov=Image.blend(Image.fromarray(r1).resize((r2.shape[1],r2.shape[0])),Image.fromarray(r2),.5);c=fig.add_subplot(gs[0,6:]);c.imshow(ov);c.axis('off');p(c,'c')
 for j,(img,t) in enumerate([(r1,t1),(r2,t2)]):d=fig.add_subplot(gs[1,j*4:(j+1)*4]);base.entropy_map(d,img,t,'',False);p(d,chr(100+j))
 pairs=pd.read_csv(ROOT/'outputs'/'flagship'/'adjacent_replication'/'table_adjacent_section_pairs.csv');f=fig.add_subplot(gs[2,:3]);f.hexbin(pairs.angular_entropy_median_rank1,pairs.angular_entropy_median_rank2,gridsize=18,cmap='viridis',mincnt=1);f.plot([.82,1],[.82,1],color='white',lw=.7);clean(f);p(f,'f')
 g=fig.add_subplot(gs[2,3:6]);x=(pairs.angular_entropy_median_rank1+pairs.angular_entropy_median_rank2)/2;y=pairs.angular_entropy_median_rank2-pairs.angular_entropy_median_rank1;g.scatter(x,y,c=np.abs(y),cmap='magma',s=10,alpha=.75);g.axhline(0,color='#777',lw=.5);clean(g);p(g,'g')
 h=fig.add_subplot(gs[2,6:]);for_site=[pairs[pairs.replication_site==s] for s in ['Medial','Lateral']]
 for q,col in zip(for_site,[TEAL,RED]):
  for _,r in q.sample(min(35,len(q)),random_state=4).iterrows():h.plot([0,1],[r.angular_entropy_median_rank1,r.angular_entropy_median_rank2],color=col,alpha=.22,lw=.6)
 h.set_xticks([0,1],['1','2']);clean(h);p(h,'h')
 save(fig,6)

def figure7():
 rgb,mask,t=base.load('076');t=usable(t,rgb);row=t.iloc[(t.angular_entropy-t.angular_entropy.median()).abs().argmin()];tile=Image.fromarray(tile_at(rgb,row));variants=[tile,tile.filter(ImageFilter.GaussianBlur(1)),tile.filter(ImageFilter.GaussianBlur(2)),tile.resize((64,64)).resize((256,256)),tile.rotate(15),Image.fromarray(np.clip(np.asarray(tile,dtype=float)+np.random.default_rng(5).normal(0,8,(256,256,1)),0,255).astype(np.uint8))]
 fig=plt.figure(figsize=(7.2,4.15));gs=GridSpec(2,12,figure=fig,hspace=.12,wspace=.14)
 for i,img in enumerate(variants):a=fig.add_subplot(gs[0,i*2:i*2+2]);a.imshow(img);a.axis('off');p(a,chr(97+i))
 bnd=pd.read_csv(ROOT/'outputs'/'cpu_pilot'/'robustness'/'mask_sensitivity_summary.csv');g=fig.add_subplot(gs[1,:4]);colors=mpl.colormaps['viridis'](np.linspace(.1,.9,len(bnd)))
 for d,col in zip(bnd.delta_um,colors):edge=ndimage.binary_dilation(mask==1,iterations=max(1,int(abs(d)/25))) if d>=0 else ndimage.binary_erosion(mask==1,iterations=max(1,int(abs(d)/25)));g.contour(edge,levels=[.5],colors=[col],linewidths=.6)
 g.invert_yaxis();g.set_aspect('equal');g.axis('off');p(g,'g')
 rob=pd.read_csv(ROOT/'outputs'/'cpu_pilot'/'robustness'/'tile_robustness_summary.csv');h=fig.add_subplot(gs[1,4:9]);metrics=['orientation_degrees_absolute_drift_p95','anisotropy_relative_drift_p95','angular_entropy_relative_drift_p95','spectral_slope_relative_drift_p95','characteristic_frequency_cycles_per_mm_relative_drift_p95'];mat=rob[metrics].to_numpy(float).T;mat=mat/np.maximum(mat.max(axis=1,keepdims=True),1e-12);h.imshow(mat,cmap=mpl.colors.LinearSegmentedColormap.from_list('rob',[LIGHT,TEAL,GOLD]),vmin=0,vmax=1,aspect='auto');h.set_xticks([]);h.set_yticks([]);h.spines[:].set_visible(False);p(h,'h')
 import json;perm=json.loads((ROOT/'outputs'/'cpu_pilot'/'validation'/'primary_permutation_test.json').read_text());i=fig.add_subplot(gs[1,9:]);mu=perm['null_mae_mean'];sd=perm['null_mae_sd'];xx=np.linspace(mu-4*sd,mu+4*sd,400);yy=np.exp(-.5*((xx-mu)/sd)**2)/(sd*np.sqrt(2*np.pi));i.fill_between(xx,0,yy,color='#C8D0D2');i.plot(xx,yy,color=GRAY,lw=.8);i.axvline(perm['observed_mae'],color=RED,lw=1.4);i.set_yticks([]);clean(i);p(i,'i')
 save(fig,7)

def figure8():
 med=pd.read_csv(ROOT/'outputs'/'cpu_pilot'/'safo_medial_features.csv');lat=pd.read_csv(ROOT/'outputs'/'cpu_pilot'/'safo_lateral_features.csv');features=['angular_entropy_median','anisotropy_median','spectral_slope_median','tensor_coherence_median','glcm_contrast_median','glcm_homogeneity_median'];both=pd.concat([med.assign(site='M'),lat.assign(site='L')],ignore_index=True);X=both[features].replace([np.inf,-np.inf],np.nan).fillna(both[features].median());Z=PCA(2,random_state=4).fit_transform(StandardScaler().fit_transform(X));both['p1']=Z[:,0];both['p2']=Z[:,1]
 fig=plt.figure(figsize=(7.2,5.35));gs=GridSpec(2,4,figure=fig,hspace=.28,wspace=.28)
 a=fig.add_subplot(gs[0,:2]);a.scatter(both.p1,both.p2,c=both.angular_entropy_median,cmap='viridis',s=15,alpha=.78,edgecolor='white',lw=.2);clean(a);p(a,'a')
 b=fig.add_subplot(gs[0,2:]);xy=np.vstack([both.p1,both.p2]);k=gaussian_kde(xy);xx,yy=np.meshgrid(np.linspace(both.p1.min(),both.p1.max(),100),np.linspace(both.p2.min(),both.p2.max(),100));zz=k(np.vstack([xx.ravel(),yy.ravel()])).reshape(xx.shape);b.contourf(xx,yy,zz,levels=14,cmap='magma');b.set_xticks([]);b.set_yticks([]);b.spines[:].set_visible(False);p(b,'b')
 c=fig.add_subplot(gs[1,:2]);wide=both.pivot_table(index='participant_id',columns='site',values=['p1','p2']).dropna();
 for _,r in wide.iterrows():c.plot([r[('p1','M')],r[('p1','L')]],[r[('p2','M')],r[('p2','L')]],color=GRAY,alpha=.25,lw=.45)
 c.scatter(wide[('p1','M')],wide[('p2','M')],s=9,color=TEAL);c.scatter(wide[('p1','L')],wide[('p2','L')],s=9,color=RED);clean(c);p(c,'c')
 pred=pd.read_csv(ROOT/'outputs'/'flagship'/'severity_benchmark'/'table_severity_predictions.csv');q=pred[pred.model=='fft_entropy'];d=fig.add_subplot(gs[1,2]);bins=np.linspace(0,1,6);idx=np.digitize(q.probability,bins)-1;xp=[];yp=[]
 for j in range(5):z=q[idx==j];xp.append(z.probability.mean() if len(z) else np.nan);yp.append(z.outcome.mean() if len(z) else np.nan)
 d.plot([0,1],[0,1],ls='--',color='#999',lw=.6);d.plot(xp,yp,'o-',color=BLUE,lw=1,ms=3);d.set_xlim(0,1);d.set_ylim(0,1);clean(d);p(d,'d')
 e=fig.add_subplot(gs[1,3]);e.hist(q[q.outcome==0].probability,bins=10,color='#BFC8CA',alpha=.8);e.hist(q[q.outcome==1].probability,bins=10,color=RED,alpha=.7);e.set_yticks([]);clean(e);p(e,'e')
 save(fig,8)

if __name__=='__main__':
 for fn in (figure1,figure2,figure3,figure4,figure5,figure6,figure7,figure8):fn()
