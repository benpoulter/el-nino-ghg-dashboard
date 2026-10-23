"""GLWD v2 (static) -> wetland-fraction and dominant-class WebP images + 0.25 deg value grids (glwd.json).
Download GLWD_v2_0_combined_classes_tif.zip from https://doi.org/10.6084/m9.figshare.28519994, extract
GLWD_v2_0_area_pct.tif and GLWD_v2_0_main_class.tif, then run this script. Code as used on 23 Oct 2026."""

import rasterio, numpy as np, json, base64, os
from rasterio.enums import Resampling
from PIL import Image
W,H=5760,2240
with rasterio.open('GLWD_v2_0_combined_classes/GLWD_v2_0_area_pct.tif') as ds: pct=np.ma.filled(ds.read(1,out_shape=(H,W),resampling=Resampling.average,masked=True).astype(np.float32),np.nan)
with rasterio.open('GLWD_v2_0_combined_classes/GLWD_v2_0_main_class.tif') as ds: cls=np.ma.filled(ds.read(1,out_shape=(H,W),resampling=Resampling.mode,masked=True),255).astype(np.uint8)
GROUP={1:'Lakes & reservoirs',2:'Lakes & reservoirs',3:'Lakes & reservoirs',6:'Lakes & reservoirs',4:'Rivers & streams',5:'Rivers & streams',7:'Rivers & streams',8:'Lacustrine wetlands',9:'Lacustrine wetlands',10:'Riverine wetlands',11:'Riverine wetlands',12:'Riverine wetlands',13:'Riverine wetlands',14:'Riverine wetlands',15:'Riverine wetlands',16:'Palustrine wetlands',17:'Palustrine wetlands',18:'Palustrine wetlands',19:'Palustrine wetlands',20:'Ephemeral wetlands',21:'Ephemeral wetlands',22:'Peatlands',23:'Peatlands',24:'Peatlands',25:'Peatlands',26:'Peatlands',27:'Peatlands',28:'Coastal wetlands',29:'Coastal wetlands',30:'Coastal wetlands',31:'Coastal wetlands',32:'Salt pans',33:'Rice paddies'}
GCOL={'Lakes & reservoirs':(31,120,180),'Rivers & streams':(8,48,107),'Lacustrine wetlands':(102,194,165),'Riverine wetlands':(27,158,119),'Palustrine wetlands':(166,216,84),'Ephemeral wetlands':(255,217,47),'Peatlands':(140,81,10),'Coastal wetlands':(231,138,195),'Salt pans':(160,160,160),'Rice paddies':(173,255,47)}
names={int(l.split(',')[0]):l.split(',',1)[1].strip().strip('"') for l in open('GLWD_Legend_v2_0.csv').read().splitlines()[1:] if l.strip()}
f=np.nan_to_num(pct,nan=0)/100.0; stops=np.array([[222,235,247],[158,202,225],[66,146,198],[8,69,148]],float)
t=np.clip(f,0,1)*3; i=np.clip(np.floor(t),0,2).astype(int); fr=(t-i)[...,None]; rgb=stops[i]*(1-fr)+stops[np.minimum(i+1,3)]*fr
al=np.clip(f*255*1.6,0,235).astype(np.uint8); al[np.isnan(pct)|(f<0.02)]=0
Image.fromarray(np.dstack([rgb.astype(np.uint8),al]),'RGBA').save('frac.webp','WEBP',quality=70,method=6)
col=np.zeros((H,W,3),np.uint8); a2=np.zeros((H,W),np.uint8)
for c,g in GROUP.items(): m=cls==c; col[m]=GCOL[g]; a2[m]=225
Image.fromarray(np.dstack([col,a2]),'RGBA').save('class.webp','WEBP',quality=75,method=6)
f4=np.nanmean(pct.reshape(560,4,1440,4),axis=(1,3)); fr8=np.where(np.isnan(f4),255,np.clip(np.round(f4),0,100)).astype(np.uint8)
blk=cls.reshape(560,4,1440,4).transpose(0,2,1,3).reshape(560,1440,16); dom=np.full((560,1440),255,np.uint8); best=None
for k in range(1,34):
    cnt=(blk==k).sum(axis=2)
    if best is None: best=cnt.copy(); dom=np.where(cnt>0,1,255).astype(np.uint8)
    else: better=cnt>best; dom=np.where(better,k,dom); best=np.maximum(best,cnt)
json.dump(dict(ny=560,nx=1440,latTop=84,latBot=-56,names=names,groups={str(k):v for k,v in GROUP.items()},gcol=GCOL,frac=base64.b64encode(fr8.tobytes()).decode(),dom=base64.b64encode(dom.tobytes()).decode()),open('glwd.json','w'))
