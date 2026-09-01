"""Build tissue-first experiential figures without inventing measurements."""
from __future__ import annotations

from pathlib import Path
import json

import matplotlib as mpl
import matplotlib.pyplot as plt
from matplotlib.gridspec import GridSpec
from matplotlib.patches import Circle, FancyArrowPatch, Rectangle
import numpy as np
import pandas as pd
from PIL import Image
from scipy.interpolate import griddata

import build_megafigures as base


ROOT = base.ROOT
OUT = base.OUT
BG = "#05060A"
WHITE = "#F4F5F4"
MUTED = "#AEB6BF"
TEAL = "#42D4C5"
GOLD = "#FFD166"
RED = "#FF6B5E"
PURPLE = "#9B5DE5"

mpl.rcParams.update({
    "font.family": "serif",
    "font.serif": ["Times New Roman"],
    "font.size": 8,
    "axes.labelsize": 8,
    "axes.titlesize": 9,
    "xtick.labelsize": 7,
    "ytick.labelsize": 7,
    "text.color": WHITE,
    "axes.labelcolor": WHITE,
    "axes.edgecolor": "#89939C",
    "xtick.color": MUTED,
    "ytick.color": MUTED,
    "savefig.dpi": 600,
    "svg.fonttype": "none",
})


def panel(ax, label):
    fn = ax.text2D if hasattr(ax, "text2D") else ax.text
    fn(-.045, 1.03, label, transform=ax.transAxes, fontsize=12, fontweight="bold", va="top", color=WHITE)


def dark(ax):
    ax.set_facecolor(BG)
    for spine in ax.spines.values():
        spine.set_color("#59636D")
    ax.tick_params(colors=MUTED, width=.6, length=2.5)


def save(fig, name):
    for ext in ("png", "svg"):
        fig.savefig(OUT / f"{name}.{ext}", bbox_inches="tight", facecolor=BG)
    fig.savefig(OUT / f"{name}.jpg", bbox_inches="tight", facecolor=BG, pil_kwargs={"quality": 98})
    plt.close(fig)


def tissue_on_black(rgb, mask):
    source = np.asarray(rgb).copy()
    active = mask != 0
    faded = np.zeros_like(source)
    faded[active] = source[active]
    return faded


def map_overlay(ax, rgb, mask, tiles, title, alpha=.82):
    shown = tissue_on_black(rgb, mask)
    thumb = Image.fromarray(shown)
    thumb.thumbnail((1800, 1800), Image.Resampling.LANCZOS)
    shown = np.asarray(thumb)
    ax.imshow(shown)
    sx, sy = shown.shape[1] / rgb.shape[1], shown.shape[0] / rgb.shape[0]
    norm = mpl.colors.Normalize(.82, .99)
    cmap = mpl.colormaps["magma"]
    for row in tiles.itertuples():
        ax.add_patch(Rectangle((row.x*sx, row.y*sy), 256*sx, 256*sy,
                               facecolor=cmap(norm(row.angular_entropy)), edgecolor="none", alpha=alpha))
    ax.set_title(title, color=WHITE, pad=4)
    ax.axis("off")
    return norm, cmap


def entropy_grid(tiles, nx=110, ny=70):
    x = tiles.x.to_numpy(float) / 1000
    y = tiles.y.to_numpy(float) / 1000
    z = tiles.angular_entropy.to_numpy(float)
    gx, gy = np.mgrid[x.min():x.max():complex(nx), y.min():y.max():complex(ny)]
    gz = griddata((x, y), z, (gx, gy), method="linear")
    return gx, gy, gz


def terrain(ax, tiles, title, view=(36, -60)):
    gx, gy, gz = entropy_grid(tiles)
    surface = ax.plot_surface(gx, gy, gz, cmap="magma", linewidth=0, antialiased=True,
                              rstride=1, cstride=1, vmin=.82, vmax=.99)
    ax.view_init(*view)
    ax.set_facecolor(BG)
    ax.xaxis.pane.fill = ax.yaxis.pane.fill = ax.zaxis.pane.fill = False
    ax.xaxis.pane.set_edgecolor("#101217"); ax.yaxis.pane.set_edgecolor("#101217"); ax.zaxis.pane.set_edgecolor("#101217")
    ax.grid(False)
    ax.set_xticks([]); ax.set_yticks([])
    ax.set_zlim(.80, 1.0)
    ax.set_zticks([.82, .90, .98]); ax.tick_params(colors=MUTED, labelsize=6)
    ax.set_zlabel("angular entropy", color=WHITE, labelpad=2)
    ax.set_title(title, color=WHITE, pad=0)
    return surface


def polar_spectrum(ax, tile):
    gray = np.asarray(Image.fromarray(tile).convert("L"), dtype=float)
    gray -= gray.mean()
    window = np.outer(np.hanning(gray.shape[0]), np.hanning(gray.shape[1]))
    power = np.log1p(np.abs(np.fft.fftshift(np.fft.fft2(gray * window)))**2)
    n = gray.shape[0]
    yy, xx = np.mgrid[:n, :n] - n/2
    theta = np.mod(np.arctan2(yy, xx), np.pi)
    radius = np.hypot(xx, yy) / (n/2)
    abins = np.linspace(0, np.pi, 73)
    rbins = np.linspace(.04, .92, 42)
    field = np.zeros((len(rbins)-1, len(abins)-1))
    for ri in range(len(rbins)-1):
        for ai in range(len(abins)-1):
            sel = (radius >= rbins[ri]) & (radius < rbins[ri+1]) & (theta >= abins[ai]) & (theta < abins[ai+1])
            field[ri, ai] = power[sel].mean() if sel.any() else np.nan
    th, rr = np.meshgrid(abins, rbins)
    ax.grid(False)
    ax.pcolormesh(th, rr, field, cmap="magma", shading="auto")
    ax.set_thetamin(0); ax.set_thetamax(180)
    ax.set_xticks(np.deg2rad([0,30,60,90,120,150,180])); ax.set_xticklabels(["0°","30°","60°","90°","120°","150°","180°"], color=MUTED, fontsize=6)
    ax.set_yticks([])
    ax.set_facecolor(BG)
    ax.set_title("Axial spectral fingerprint", color=WHITE, pad=9)


def orientation_field(ax, rgb, mask, tiles):
    shown = tissue_on_black(rgb, mask)
    thumb = Image.fromarray(shown); thumb.thumbnail((1600,1600), Image.Resampling.LANCZOS); shown=np.asarray(thumb)
    ax.imshow(shown, alpha=.72)
    sx, sy = shown.shape[1]/rgb.shape[1], shown.shape[0]/rgb.shape[0]
    step = max(1, len(tiles)//55)
    for row in tiles.iloc[::step].itertuples():
        angle=np.deg2rad(row.orientation_degrees); length=70*(.25+row.anisotropy)
        cx=(row.x+128)*sx; cy=(row.y+128)*sy
        dx=np.cos(angle)*length*sx; dy=np.sin(angle)*length*sy
        ax.plot([cx-dx,cx+dx],[cy-dy,cy+dy],color=GOLD,alpha=.72,lw=.8)
    ax.axis("off");ax.set_title("Local axial orientation field",color=WHITE,pad=4)


def figure1():
    rgb, mask, tiles = base.load("076")
    whole = tissue_on_black(rgb, mask)
    fig = plt.figure(figsize=(7.2, 8.2), facecolor=BG)
    gs = GridSpec(4, 12, figure=fig, height_ratios=[1.05, 2.25, 2.45, 2.0], hspace=.18, wspace=.25)
    head=fig.add_subplot(gs[0,:]);head.axis("off")
    head.text(.01,.78,"A human osteochondral section becomes a spatial phenotype",fontsize=16,fontweight="bold",color=WHITE)
    head.text(.01,.48,"Repository-derived microscopy · physical scale · local Fourier architecture · participant-level inference",fontsize=9,color=MUTED)
    steps=[("TISSUE","Safranin-O"),("COMPARTMENTS","cartilage · interface · bone"),("LOCAL FIELD","440 × 440 µm"),("PHENOTYPE","angular entropy")]
    for i,(a,b) in enumerate(steps):
        x=.01+i*.245;head.text(x,.13,a,fontsize=7,color=GOLD,fontweight="bold");head.text(x,.01,b,fontsize=7,color=WHITE)
        if i<3:head.add_patch(FancyArrowPatch((x+.19,.08),(x+.23,.08),arrowstyle='-|>',mutation_scale=8,color="#50606B",lw=.8))
    a=fig.add_subplot(gs[1,:]);thumb=Image.fromarray(whole);thumb.thumbnail((2400,1300),Image.Resampling.LANCZOS);a.imshow(np.asarray(thumb));a.axis('off');a.set_title('Whole human cartilage–bone specimen · P076',loc='left',color=WHITE,pad=3);panel(a,'a')
    a.text(.10,.18,'articular cartilage',transform=a.transAxes,color=WHITE,fontsize=8,bbox=dict(facecolor=BG,alpha=.72,edgecolor='none',pad=1.5));a.text(.70,.66,'trabecular bone',transform=a.transAxes,color=WHITE,fontsize=8,bbox=dict(facecolor=BG,alpha=.72,edgecolor='none',pad=1.5))
    b=fig.add_subplot(gs[2,:6]);norm,cmap=map_overlay(b,rgb,mask,tiles,'Measured entropy field');panel(b,'b')
    c=fig.add_subplot(gs[2,6:],projection='3d');terrain(c,tiles,'The same field as a data terrain');panel(c,'c')
    chosen=tiles.iloc[(tiles.angular_entropy-tiles.angular_entropy.median()).abs().argmin()];tile=rgb[int(chosen.y):int(chosen.y)+256,int(chosen.x):int(chosen.x)+256]
    d=fig.add_subplot(gs[3,:5],projection='polar');polar_spectrum(d,tile);panel(d,'d')
    e=fig.add_subplot(gs[3,5:]);orientation_field(e,rgb,mask,tiles);panel(e,'e')
    b.text(.03,.04,'low',transform=b.transAxes,color=MUTED,fontsize=6);b.text(.88,.04,'high',transform=b.transAxes,color=WHITE,fontsize=6)
    save(fig,'figure_1_mega')


def figure2():
    rgb1,m1,t1=base.load('076',1);rgb2,m2,t2=base.load('076',2)
    pairs=pd.read_csv(ROOT/'outputs'/'flagship'/'adjacent_replication'/'table_adjacent_section_pairs.csv')
    fig=plt.figure(figsize=(7.2,8.0),facecolor=BG);gs=GridSpec(4,12,figure=fig,height_ratios=[.65,1.75,2.5,2.2],hspace=.2,wspace=.28)
    h=fig.add_subplot(gs[0,:]);h.axis('off');h.text(.01,.62,'The spatial phenotype survives a new physical section',fontsize=16,fontweight='bold');h.text(.01,.20,'Untouched serial-section confirmation · frozen selection · explicit failures',fontsize=9,color=MUTED)
    a=fig.add_subplot(gs[1,:6]);a.imshow(tissue_on_black(rgb1,m1));a.axis('off');a.set_title('Serial section 1',color=WHITE);panel(a,'a')
    b=fig.add_subplot(gs[1,6:]);b.imshow(tissue_on_black(rgb2,m2));b.axis('off');b.set_title('Serial section 2',color=WHITE);panel(b,'b')
    c=fig.add_subplot(gs[2,:6],projection='3d');terrain(c,t1,'Section 1 terrain',(33,-58));panel(c,'c')
    d=fig.add_subplot(gs[2,6:],projection='3d');terrain(d,t2,'Section 2 terrain',(33,-58));panel(d,'d')
    e=fig.add_subplot(gs[3,:]);dark(e);panel(e,'e')
    med=pairs[pairs.replication_site=='Medial'].sort_values('angular_entropy_median_rank1')
    lat=pairs[pairs.replication_site=='Lateral'].sort_values('angular_entropy_median_rank1')
    for q,color,yoff,label in [(med,TEAL,.03,'medial · ICC 0.883'),(lat,PURPLE,-.03,'lateral · ICC 0.872')]:
        order=np.arange(len(q));x1=q.angular_entropy_median_rank1.to_numpy();x2=q.angular_entropy_median_rank2.to_numpy()
        for i,(u,v) in enumerate(zip(x1,x2)):
            e.plot([u,v],[i+yoff,i+yoff],color=color,alpha=.32,lw=.7)
            e.scatter([u,v],[i+yoff,i+yoff],s=4,color=color,alpha=.65)
        e.plot([],[],color=color,lw=2,label=label)
    e.set_xlabel('Section entropy · paired participants');e.set_ylabel('Participants ordered by section 1');e.set_yticks([]);e.legend(frameon=False,ncol=2,loc='upper center',labelcolor=WHITE);e.set_title('Every line connects the same participant across sections',color=WHITE,pad=7)
    save(fig,'figure_2_mega')


def radial_evidence(ax, data):
    order=['hhgs_safo_loss','hhgs_structure','oarsi_grade','oarsi_stage','hhgs_cells','hhgs_tidemark','plm_superficial_disorganization','plm_deep_disorganization','plm_total_disorganization']
    labels=['SafO loss','Structure','Grade','Stage','Cells','Tidemark','PLM superficial','PLM deep','PLM total']
    data=data[data.feature=='angular_entropy_median'].copy();data['ring']=data.site.str[:3]+' '+data.section_rank.astype(str)
    rings=['Med 1','Med 2','Lat 1','Lat 2'];mat=data.pivot(index='component',columns='ring',values='spearman_rho').reindex(order)[rings]
    theta=np.linspace(0,2*np.pi,len(order)+1);r=np.arange(len(rings)+1)
    z=np.vstack([mat.T.to_numpy(),mat.T.to_numpy()[:1,:]]) if False else mat.T.to_numpy()
    th,rr=np.meshgrid(theta,np.arange(len(rings)+1))
    mesh=ax.pcolormesh(th,rr,z,cmap=mpl.colors.LinearSegmentedColormap.from_list('ev',[TEAL,'#171A20',RED]),vmin=-.5,vmax=.5,shading='flat')
    ax.set_ylim(0,4);ax.set_yticks(np.arange(4)+.5,rings,color=MUTED,fontsize=6);ax.set_xticks(theta[:-1],labels,color=WHITE,fontsize=6.2)
    ax.tick_params(pad=3);ax.grid(color='#39414A',alpha=.45,lw=.5);ax.set_facecolor(BG);ax.set_title('Radial evidence map · Spearman ρ',color=WHITE,pad=18)
    return mesh


def figure3():
    rgb,mask,tiles=base.load('076');plm=np.asarray(Image.open(Path(r'<DATA_ROOT>\data\annotations\images\076_Medial_PLM_PLM.png')).convert('RGB'))
    data=pd.read_csv(ROOT/'outputs'/'flagship'/'mechanistic'/'table_mechanistic_associations.csv')
    fig=plt.figure(figsize=(7.2,8.0),facecolor=BG);gs=GridSpec(3,12,figure=fig,height_ratios=[.7,2.25,3.9],hspace=.24,wspace=.26)
    h=fig.add_subplot(gs[0,:]);h.axis('off');h.text(.01,.62,'A spectral phenotype with a biological address',fontsize=16,fontweight='bold');h.text(.01,.18,'Structure and cellular pathology dominate; stain loss and horizontal extent do not',fontsize=9,color=MUTED)
    a=fig.add_subplot(gs[1,:6]);a.imshow(tissue_on_black(rgb,mask));a.axis('off');a.set_title('Safranin-O bright-field',color=WHITE);panel(a,'a')
    b=fig.add_subplot(gs[1,6:]);black=np.zeros_like(plm);lum=np.asarray(Image.fromarray(plm).convert('L'));active=lum>8;black[active]=plm[active];b.imshow(black);b.axis('off');b.set_title('Polarized-light microscopy',color=WHITE);panel(b,'b')
    c=fig.add_subplot(gs[2,:7],projection='polar');mesh=radial_evidence(c,data);panel(c,'c')
    d=fig.add_subplot(gs[2,8:]);d.set_facecolor(BG);d.axis('off');panel(d,'d')
    d.text(.03,.94,'Working mechanism',fontsize=12,fontweight='bold',color=WHITE)
    nodes=[(.10,.76,'surface\nfissures',RED),(.55,.76,'cell\nclusters',GOLD),(.10,.43,'aligned lesion\nboundaries',PURPLE),(.55,.43,'concentrated\nFourier power',TEAL)]
    for x,y,text,color in nodes:
        d.add_patch(Circle((x+.12,y),.105,facecolor=color,alpha=.20,edgecolor=color,lw=1.2));d.text(x+.12,y,text,ha='center',va='center',fontsize=8,color=WHITE)
    for start,end in [((.22,.76),(.55,.76)),((.22,.43),(.55,.43)),((.22,.70),(.55,.49)),((.67,.68),(.67,.54))]:d.add_patch(FancyArrowPatch(start,end,arrowstyle='-|>',mutation_scale=9,color='#7E8B95',lw=.9))
    d.text(.03,.17,'Supported',fontsize=8,fontweight='bold',color=TEAL);d.text(.03,.10,'structural · cellular · superficial PLM convergence',fontsize=7,color=WHITE)
    d.text(.03,.01,'Not established: collagen specificity · causality · mechanics',fontsize=7,color=RED)
    c.text(.50,-.12,'teal = inverse association   ·   red = positive association',transform=c.transAxes,ha='center',color=MUTED,fontsize=6)
    save(fig,'figure_3_mega')


def figure4():
    # Preserve the dense validation figure on white for print legibility.
    mpl.rcParams.update({'text.color':base.INK,'axes.labelcolor':base.INK,'axes.edgecolor':'#88949D',
                         'xtick.color':'#5E6870','ytick.color':'#5E6870'})
    base.figure4()
    path=OUT/'figure_4_mega.png'
    # The analytical validation panel intentionally retains a white background for print legibility.


if __name__ == '__main__':
    figure1(); figure2(); figure3(); figure4()
