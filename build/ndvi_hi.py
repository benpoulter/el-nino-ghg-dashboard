import os as _os, json as _json, datetime as _dt
_MJ=_os.environ.get('MONTHS_JSON')
import subprocess, os, re, json, numpy as np
from PIL import Image
from concurrent.futures import ThreadPoolExecutor
Image.MAX_IMAGE_PIXELS=None
W='https://gibs.earthdata.nasa.gov/wms/epsg4326/best/wms.cgi?SERVICE=WMS&REQUEST=GetMap&VERSION=1.3.0&LAYERS=MODIS_Terra_L3_NDVI_Monthly&CRS=EPSG:4326&BBOX=-90,-180,90,180&FORMAT=image/png'
ents=re.findall(r'<ColorMapEntry rgb="(\d+),(\d+),(\d+)"[^>]*value="\[([-\d.]+),([-\d.]+)[\)\]]"',open('ndvi/cmap.xml').read())
lk={int(r)*65536+int(g)*256+int(b):(float(lo)+float(hi))/2 for r,g,b,lo,hi in ents}
months=[tuple(x) for x in _json.loads(_MJ)][:-1] if _MJ else [(2025,m) for m in range(10,13)]+[(2026,m) for m in range(1,10)]  # MODIS monthly lags ~1 month
def get(y,m,w,h):
    f=f"ndvi_hi/n{w}_{y}-{m:02d}.png"
    if not os.path.exists(f) or os.path.getsize(f)<20000:
        for k in range(3):
            subprocess.run(['curl','-s','-m','300','-o',f,f"{W}&WIDTH={w}&HEIGHT={h}&TIME={y}-{m:02d}-01"])
            if os.path.exists(f) and os.path.getsize(f)>20000: break
    return f if os.path.exists(f) and os.path.getsize(f)>20000 else None
def dec(f):
    im=np.array(Image.open(f).convert('RGBA')); c=im[...,:3].reshape(-1,3).astype(np.int32); keys=c[:,0]*65536+c[:,1]*256+c[:,2]
    u,inv=np.unique(keys,return_inverse=True); v=np.array([lk.get(int(x),np.nan) for x in u],dtype=np.float32)[inv].reshape(im.shape[:2]); v[im[...,3]<128]=np.nan; return v
def colorize(a,lim=0.2):
    t=np.clip(a/lim,-1,1); neg=np.array([140,81,10]); mid=np.array([245,245,245]); pos=np.array([1,102,60])
    rgb=np.where(t[...,None]<0, mid+(neg-mid)*(-t)[...,None], mid+(pos-mid)*t[...,None]); alpha=np.where(np.isnan(a),0,210).astype(np.uint8)
    return np.dstack([np.nan_to_num(rgb,nan=0).astype(np.uint8),alpha])
jobs=[(yy,m,2880,1440) for y,m in months for yy in range(y-5,y+1)]+[(yy,months[-1][1],7200,3600) for yy in range(months[-1][0]-5,months[-1][0]+1)]
with ThreadPoolExecutor(6) as ex: list(ex.map(lambda j:get(*j),jobs))
print('downloaded',flush=True)
import time as _time
_T0=float(_os.environ.get('BUILD_START',_time.time())); _B=float(_os.environ.get('BUILD_BUDGET_MIN','150'))*60
meta=[]; g2=[]
os.makedirs('data',exist_ok=True)
for y,m in months:
    if _time.time()-_T0>_B-35*60: print('MODIS: budget reached'); break
    hi=(y,m)==months[-1]; w,h=(7200,3600) if hi else (2880,1440)
    out=f"ndvi_hi/anom_{y}-{m:02d}.png"
    cur=dec(get(y,m,w,h)); S=np.zeros_like(cur); N=np.zeros_like(cur)
    for yy in range(y-5,y):
        f=get(yy,m,w,h)
        if not f: continue
        b=dec(f); ok=~np.isnan(b); S[ok]+=b[ok]; N[ok]+=1; del b
    an=cur-np.where(N>0,S/np.maximum(N,1),np.nan); an[N<1]=np.nan
    img=Image.fromarray(colorize(an),'RGBA').quantize(colors=128,method=Image.Quantize.FASTOCTREE); img.save(out,optimize=True)
    meta.append(dict(date=f"{y}-{m:02d}",baseline=f"{y-5}–{y-1} ({int(N.max())} yrs)",mean=float(np.nanmean(an)),file=os.path.basename(out),res=0.05 if hi else 0.125))
    fy=an.shape[0]//90; fx=an.shape[1]//180; a2=np.nanmean(an[:90*fy,:180*fx].reshape(90,fy,180,fx),axis=(1,3))
    g2.append(dict(date=f"{y}-{m:02d}",b64=__import__('base64').b64encode(np.where(np.isnan(a2),-128,np.clip(np.round(a2*200),-127,127)).astype(np.int8).tobytes()).decode()))
    print(y,m,os.path.getsize(out),flush=True)
json.dump(meta,open('ndvi_hi/meta.json','w'))
json.dump(dict(ny=90,nx=180,scale=200,months=g2),open('data/ndvi2.json','w'))
