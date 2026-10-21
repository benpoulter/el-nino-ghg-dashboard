import os as _os, json as _json, datetime as _dt
_MJ=_os.environ.get('MONTHS_JSON')
import subprocess, os, re, json, base64, datetime as dt, calendar, numpy as np
from PIL import Image
from concurrent.futures import ThreadPoolExecutor
W='https://gibs.earthdata.nasa.gov/wms/epsg4326/best/wms.cgi?SERVICE=WMS&REQUEST=GetMap&VERSION=1.3.0&CRS=EPSG:4326&BBOX=-90,-180,90,180&FORMAT=image/png'
def get(layer,date,w,h,path):
    if os.path.exists(path) and os.path.getsize(path)>500: return path
    for k in range(3):
        r=subprocess.run(['curl','-s','-L','-m','300','--retry','2','-A','Mozilla/5.0 (dashboard-build)','-o',path,'-w','%{http_code}',f"{W}&LAYERS={layer}&WIDTH={w}&HEIGHT={h}&TIME={date}"],capture_output=True,text=True)
        if os.path.exists(path) and os.path.getsize(path)>500: return path
        if k==2: print('GIBS fail',layer[:30],date,'http',r.stdout,flush=True)
    return None
months=[tuple(x) for x in _json.loads(_MJ)] if _MJ else [(2025,10),(2025,11),(2025,12)]+[(2026,m) for m in range(1,11)]
# ---------- fires: sampled days -> 1deg counts ----------
def fire_days(y,m):
    nd=calendar.monthrange(y,m)[1]
    if (y,m)==months[-1]: nd=max(1,_dt.date.today().day-1)
    return [dt.date(y,m,d) for d in range(1,nd+1,3)]
jobs=[]
for y,m in months:
    for yy in list(range(y-5,y))+[y]:
        for d in fire_days(yy,m): jobs.append(('fire',d))
def fire_grid(d):
    p=get('VIIRS_SNPP_Thermal_Anomalies_375m_All',str(d),2880,1440,f"firesm/f_{d}.png")
    if not p: return None
    try: a=np.array(Image.open(p).convert('RGBA'))
    except Exception: os.remove(p); return None
    m=a[...,3]>0
    ys,xs=np.nonzero(m); g=np.zeros((180,360),np.int32); np.add.at(g,(ys//8,xs//8),1); os.remove(p); return g
import time as _time
_T0=float(_os.environ.get('BUILD_START',_time.time())); _B=float(_os.environ.get('BUILD_BUDGET_MIN','150'))*60
def _ok(): return _time.time()-_T0<_B-30*60
def run_fire(j):
    _,d=j; out=f"firesm/g_{d}.npy"
    if os.path.exists(out) or not _ok(): return
    g=fire_grid(d)
    if g is not None: np.save(out,g)
with ThreadPoolExecutor(8) as ex: list(ex.map(run_fire,jobs))
print('fires done',flush=True)
# ---------- AIRS CO monthly (500 hPa VMR) ----------
ents=re.findall(r'<ColorMapEntry rgb="(\d+),(\d+),(\d+)"[^>]*value="\[([-+A-Za-z\d.e]+),([-+A-Za-z\d.e]+)[\)\]]"',open('airs/cmap.xml').read())
lk={}
for r,g,b,lo,hi in ents:
    lo=float(lo.replace('INF','1e9')); hi=float(hi.replace('INF','1e9'))
    if lo<-1e8: lo=hi
    if hi>1e8: hi=lo
    lk[int(r)*65536+int(g)*256+int(b)]=(lo+hi)/2
def decode(p):
    im=np.array(Image.open(p).convert('RGBA')); c=im[...,:3].reshape(-1,3).astype(np.int32); keys=c[:,0]*65536+c[:,1]*256+c[:,2]
    u,inv=np.unique(keys,return_inverse=True); v=np.array([lk.get(int(x),np.nan) for x in u])[inv].reshape(im.shape[:2]); v[im[...,3]<128]=np.nan; return v
L='AIRS_L3_Carbon_Monoxide_500hPa_Volume_Mixing_Ratio_Monthly_Day'; LD='AIRS_L3_Carbon_Monoxide_500hPa_Volume_Mixing_Ratio_Daily_Day'
def airs_month(y,m):
    out=f"airs/a_{y}-{m:02d}.npy"
    if os.path.exists(out): return np.load(out)
    if not _ok(): return None
    if (y,m) in months[-2:]:
        nd=calendar.monthrange(y,m)[1] if (y,m)!=months[-1] else max(1,_dt.date.today().day-3); vs=[]
        for d in range(1,nd+1,2):
            p=get(LD,f"{y}-{m:02d}-{d:02d}",720,360,f"airs/d_{y}-{m:02d}-{d:02d}.png")
            if p:
                try: vs.append(decode(p))
                except Exception: pass
        v=np.nanmean(np.stack(vs),axis=0) if vs else None
    else:
        p=get(L,f"{y}-{m:02d}-01",720,360,f"airs/m_{y}-{m:02d}.png")
        try: v=decode(p) if p else None
        except Exception: v=None
    if v is not None: np.save(out,v)
    return v
ajobs=[(yy,m) for y,m in months for yy in list(range(y-5,y))+[y]]
with ThreadPoolExecutor(6) as ex: list(ex.map(lambda j:airs_month(*j),ajobs))
print('airs done',flush=True)
