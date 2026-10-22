import subprocess, os, calendar, json, base64, numpy as np, netCDF4 as nc
from concurrent.futures import ThreadPoolExecutor
from PIL import Image
TOK=os.environ.get('EARTHDATA_TOKEN','').strip(); os.makedirs('chl',exist_ok=True)
import json as _j; _MJ=os.environ.get('MONTHS_JSON'); months=[tuple(x) for x in _j.loads(_MJ)][:-1] if _MJ else [(2025,10),(2025,11),(2025,12)]+[(2026,m) for m in range(1,10)]
need=sorted(set((yy,m) for y,m in months for yy in range(y-5,y+1)))
def get(ym):
    y,m=ym; nd=calendar.monthrange(y,m)[1]; out=f'chl/{y}-{m:02d}.nc'
    if os.path.exists(out) and os.path.getsize(out)>1e6: return out
    for suf in ('','.NRT'):
        f=f'JPSS1_VIIRS.{y}{m:02d}01_{y}{m:02d}{nd}.L3m.MO.CHL.chlor_a.9km{suf}.nc'
        r=subprocess.run(['curl','-s','-L','-m','300','-H',f'Authorization: Bearer {TOK}','-o',out,'-w','%{http_code}',f'https://oceandata.sci.gsfc.nasa.gov/ob/getfile/{f}'],capture_output=True,text=True)
        if r.stdout=='200' and os.path.getsize(out)>1e6: return out
    if os.path.exists(out): os.remove(out)
    return None
with ThreadPoolExecutor(6) as ex: files=dict(zip(need,ex.map(get,need)))
print('got',sum(1 for v in files.values() if v),'of',len(need))
def load(ym):
    f=files.get(ym)
    if not f: return None
    d=nc.Dataset(f); a=np.ma.filled(d.variables['chlor_a'][:].astype(np.float32),np.nan); d.close()
    # 9km grid 2160x4320 -> 0.25 deg (720x1440) by block mean of log10
    la=np.log10(a); la=np.nanmean(la.reshape(720,3,1440,3),axis=(1,3)); return la
def colorize(a,lim=0.3):  # log10 ratio anomaly: brown(-) .. green(+)? use purple(-) to green(+)
    stops=np.array([[94,60,153],[178,171,210],[247,247,247],[166,219,160],[0,136,55]],float)
    nan=np.isnan(a); t=np.clip((np.nan_to_num(a)+lim)/(2*lim),0,1)*4; i=np.clip(np.floor(t),0,3).astype(int); f=(t-i)[...,None]
    rgb=stops[i]*(1-f)+stops[np.minimum(i+1,4)]*f; al=np.where(nan,0,220).astype(np.uint8); return np.dstack([rgb.astype(np.uint8),al])
out=[]
for y,m in months:
    cur=load((y,m)); base=[b for b in (load((yy,m)) for yy in range(y-5,y)) if b is not None]
    if cur is None or len(base)<3: print('skip',y,m); continue
    an=cur-np.nanmean(np.stack(base),axis=0)   # log10 ratio
    fn=f'chl/anom_{y}-{m:02d}.webp'; Image.fromarray(colorize(an),'RGBA').save(fn,'WEBP',quality=70,method=6)
    a2=np.nanmean(an.reshape(90,8,180,8),axis=(1,3))
    out.append(dict(date=f'{y}-{m:02d}',nbase=len(base),mean=float(np.nanmean(an)),img=os.path.basename(fn),b64=base64.b64encode(np.where(np.isnan(a2),-128,np.clip(np.round(np.nan_to_num(a2,nan=-9)*100),-127,127)).astype(np.int8).tobytes()).decode()))
    print(y,m,len(base),round(float(np.nanmean(an)),3),os.path.getsize(fn))
json.dump(dict(ny=90,nx=180,scale=100,months=out),open('chl.json','w'))
