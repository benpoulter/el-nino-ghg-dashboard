import os as _os, json as _json, datetime as _dt
_MJ=_os.environ.get('MONTHS_JSON')
import subprocess, numpy as np, datetime as dt, os, calendar
from concurrent.futures import ThreadPoolExecutor
V1='https://opendap.nccs.nasa.gov/dods/gmao/geos-cf/assim/aqc_tavg_1hr_g1440x721_v1.dods'
V2H='https://opendap.nccs.nasa.gov/dods/gmao/geos-cf/v2/ana/aqc_tavg_1hr_glo_L1440x721_slv.dods'
NY,NX=91,180
def parse(path,nt):
    b=open(path,'rb').read(); i=b.find(b'\nData:\n'); d=b[i+7:]
    n=nt*NY*NX; return np.frombuffer(d[8:8+4*n],dtype='>f4').reshape(nt,NY,NX).astype(np.float32)
def fetch(url,var,i0,i1,path,tries=5):
    nt=(i1-i0)//6+1
    q=f"{url}?{var}%5B{i0}:6:{i1}%5D%5B0%5D%5B0:8:720%5D%5B0:8:1439%5D"
    for k in range(tries):
        r=subprocess.run(['curl','-s','-m','240','-o',path,'-w','%{http_code}',q],capture_output=True,text=True)
        if r.stdout=='200' and os.path.exists(path) and os.path.getsize(path)>4*nt*NY*NX:
            try: return parse(path,nt)
            except Exception: pass
    return None
def v1_index(d): return int((d-dt.datetime(2018,1,1,0,30)).total_seconds()//3600)
def v2h_index(d): return int((d-dt.datetime(2025,8,4,9,30)).total_seconds()//3600)
_cur=[tuple(x) for x in _json.loads(_MJ)][-2:] if _MJ else [(2026,9),(2026,10)]
months=[('v1',y,m,calendar.monthrange(y,m)[1]) for y in range(2021,2026) for m in range(1,13)]+[('v2h',y,m,calendar.monthrange(y,m)[1] if (y,m)!=_cur[-1] else max(1,_dt.date.today().day-1)) for y,m in _cur]
import time as _time
_T0=float(_os.environ.get('BUILD_START',_time.time())); _B=float(_os.environ.get('BUILD_BUDGET_MIN','150'))*60
def run(j):
    src,y,m,nd=j; out=f"geoscf/{src}_{y}-{m:02d}.npy"
    if os.path.exists(out): return
    if _time.time()-_T0>_B-40*60: return
    url,var,idx=(V1,'pm25_rh35_gcc',v1_index) if src=='v1' else (V2H,'pm25_rh35',v2h_index)
    i0=idx(dt.datetime(y,m,1,0,30)); chunks=[]
    for c in range(0,nd*4,8):
        a=fetch(url,var,i0+c*6,i0+min(c+8,nd*4)*6-6,f"geoscf/tmp_{src}_{y}-{m:02d}_{c}.dods")
        if a is None: print('FAIL',out,c,flush=True); return
        chunks.append(a)
    for f in os.listdir('geoscf'):
        if f.startswith(f"tmp_{src}_{y}-{m:02d}_"): os.remove('geoscf/'+f)
    np.save(out,np.nanmean(np.concatenate(chunks),axis=0)); print('ok',out,flush=True)
with ThreadPoolExecutor(4) as ex: list(ex.map(run,months))
print('DONE')
