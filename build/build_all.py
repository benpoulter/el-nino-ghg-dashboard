#!/usr/bin/env python3
"""Single-file orchestrator for the El Niño GHG Dashboard data snapshot.

Usage: python3 build_all.py <step>   (see run_all.sh for the order)
All outputs land in ./data ; `assemble` writes ../index.html from template.html + data.
The slow/large steps (oco2, s3ndvi, openaq, gibs) are resumable: rerun to continue.
This consolidates code that was first run interactively; the individual helper scripts
(icos_ch4.py, openaq_fetch.py, geoscf_fetch2.py, bg_fetch.py, ndvi_hi.py, build_stations.py,
build_aq.py, assemble.py) are kept alongside as references.
"""
import os, sys, re, io, csv, json, glob, gzip, base64, html, calendar, subprocess, datetime as dt
import numpy as np
D='data'; os.makedirs(D,exist_ok=True)
def _months(n=13):
    t=dt.date.today(); out=[]
    for k in range(n-1,-1,-1):
        y,m=t.year,t.month-k
        while m<1: m+=12; y-=1
        out.append((y,m))
    return out
MONTHS=_months()                       # last 13 calendar months ending in the current (partial) month
os.environ['MONTHS_JSON']=json.dumps(MONTHS)
SNAPSHOT=dt.date.today().strftime('%-d %b %Y')
def sh(cmd): subprocess.run(cmd,shell=True,check=True)
import time
_T0=float(os.environ.get('BUILD_START',time.time())); _BUDGET=float(os.environ.get('BUILD_BUDGET_MIN','150'))*60
def over_budget(reserve_min=25):
    """True when less than reserve_min minutes of the run budget remain (leaves time for assemble/test/split)."""
    return time.time()-_T0 > _BUDGET-reserve_min*60
def metrics(pts):
    pts=sorted(pts); y,m,v=pts[-1]
    base=[p[2] for p in pts if p[1]==m and y-5<=p[0]<=y-1]; prev=[p[2] for p in pts if p[0]==y-1 and p[1]==m]
    return dict(latest=[y,m,v],anom=round(v-sum(base)/len(base),2) if len(base)>=3 else None,yoy=round(v-prev[0],2) if prev else None,nbase=len(base),series=[list(p) for p in pts])

# ---------------- NOAA GGRN flasks (CO2, CH4) + Mauna Loa preliminary ----------------
def step_noaa():
    for gas in ('co2','ch4'):
        os.makedirs(f'{D}/noaa_{gas}',exist_ok=True)
        base=f'https://gml.noaa.gov/aftp/data/trace_gases/{gas}/flask/surface/txt/'
        lst=subprocess.run(f'curl -s {base}',shell=True,capture_output=True,text=True).stdout
        for f in sorted(set(re.findall(rf'{gas}_[a-z0-9]+_surface-flask_1_ccgg_month\.txt',lst))):
            sh(f'curl -s -o {D}/noaa_{gas}/{f} {base}{f}')
    sh(f'curl -s "https://gml.noaa.gov/dv/site/?program=ccgg" -o {D}/noaa_sites.html')
    sh(f'curl -s -o {D}/co2_mm_mlo.csv https://gml.noaa.gov/webdata/ccgg/trends/co2/co2_mm_mlo.csv')

# ---------------- ICOS (CO2, CH4) via SPARQL + anonymous /cpb ----------------
Q_ST='''prefix cpmeta: <http://meta.icos-cp.eu/ontologies/cpmeta/>
select ?id ?name ?lat ?lon ?elev ?country where { ?st a cpmeta:AS . ?st cpmeta:hasStationId ?id ; cpmeta:hasName ?name ; cpmeta:hasLatitude ?lat ; cpmeta:hasLongitude ?lon .
 optional{?st cpmeta:hasElevation ?elev} optional{?st cpmeta:countryCode ?country} }'''
def Q_OBJ(gas):
    G=gas.capitalize()
    return f'''prefix cpmeta: <http://meta.icos-cp.eu/ontologies/cpmeta/>
prefix prov: <http://www.w3.org/ns/prov#>
select ?dobj ?specLabel ?stId ?samplingHeight ?timeStart ?timeEnd where {{
 values ?spec {{<http://meta.icos-cp.eu/resources/cpmeta/atc{G}NrtGrowingDataObject> <http://meta.icos-cp.eu/resources/cpmeta/atc{G}L2DataObject>}}
 ?dobj cpmeta:hasObjectSpec ?spec . ?spec rdfs:label ?specLabel .
 ?dobj cpmeta:wasAcquiredBy ?acq . ?acq prov:wasAssociatedWith ?st . ?st cpmeta:hasStationId ?stId .
 optional {{?acq cpmeta:hasSamplingHeight ?samplingHeight}}
 ?dobj cpmeta:hasStartTime|(cpmeta:wasAcquiredBy/prov:startedAtTime) ?timeStart .
 ?dobj cpmeta:hasEndTime|(cpmeta:wasAcquiredBy/prov:endedAtTime) ?timeEnd .
 filter not exists {{[] cpmeta:isNextVersionOf ?dobj}} }}'''
def sparql(q):
    import requests
    r=requests.post('https://meta.icos-cp.eu/sparql',data={'query':q},headers={'Accept':'text/csv'}); r.raise_for_status()
    return list(csv.DictReader(io.StringIO(r.text)))
def step_icos():
    import urllib.request, collections
    from icoscp_core.icos import meta
    from icoscp_core.cpb import TableRequest, codec_from_dobj_meta
    smeta={r['id']:r for r in sparql(Q_ST)}
    H={"Accept":"application/octet-stream","Content-Type":"application/json","User-Agent":"Mozilla/5.0","Referer":"https://data.icos-cp.eu/portal/","Origin":"https://data.icos-cp.eu"}
    out={}
    for gas in ('co2','ch4'):
        rows=sparql(Q_OBJ(gas)); by=collections.defaultdict(list)
        for r in rows: by[r['stId']].append(r)
        for sid,objs in by.items():
            if sid not in smeta: continue
            h=max(float(o['samplingHeight'] or 0) for o in objs); sel=[o for o in objs if float(o['samplingHeight'] or 0)==h]
            monthly={}
            for o in sorted(sel,key=lambda o:('NRT' in o['specLabel'],o['timeStart'])):
                try:
                    dobj=meta.get_dobj_meta(o['dobj']); codec=codec_from_dobj_meta(dobj,TableRequest(['TIMESTAMP',gas],None,None))
                    req=urllib.request.Request("https://data.icos-cp.eu/cpb",data=json.dumps(codec.json_payload).encode(),headers=H,method="POST")
                    arr=codec.parse_cpb_response(io.BytesIO(urllib.request.urlopen(req,timeout=90).read()),False)
                except Exception as e: print('fail',sid,gas,e); continue
                isL2='Release' in o['specLabel']; ts=arr['TIMESTAMP'].astype('datetime64[M]'); v=arr[gas].astype(float); ok=~np.isnan(v)
                for mo in np.unique(ts[ok]):
                    vv=v[ok&(ts==mo)]; key=str(mo)
                    if key in monthly and monthly[key][2] and not isL2: continue
                    if key in monthly and monthly[key][2]==isL2: s,n,_=monthly[key]; monthly[key]=(s+vv.sum(),n+len(vv),isL2)
                    else: monthly[key]=(vv.sum(),len(vv),isL2)
            ser=sorted((k,round(s/n,2)) for k,(s,n,_) in monthly.items() if n>=120)
            if not ser: continue
            sm=smeta[sid]; st=out.setdefault(sid,dict(id=sid,net='ICOS',name=sm['name'],country=sm['country'],lat=float(sm['lat']),lon=float(sm['lon']),elev=float(sm['elev']) if sm['elev'] else None,height=h,vars={}))
            st['vars'][gas]=metrics([(int(k[:4]),int(k[5:7]),v) for k,v in ser]); print(sid,gas,ser[-1],flush=True)
    json.dump(out,open(f'{D}/icos.json','w'))

# ---------------- OpenAQ ----------------
def step_openaq():
    import requests, time, math
    K=os.environ['OPENAQ_API_KEY']; H={'X-API-Key':K}
    allr=[]
    for page in range(1,30):
        r=requests.get('https://api.openaq.org/v3/locations',params=dict(parameters_id=2,monitor='true',limit=1000,page=page),headers=H); r.raise_for_status()
        res=r.json()['results']; allr+=res
        if len(res)<1000: break
        time.sleep(1.2)
    cutoff=(dt.datetime.utcnow()-dt.timedelta(days=30)).strftime('%Y-%m-%d')
    rec=[x for x in allr if x.get('datetimeLast') and x['datetimeLast']['utc']>=cutoff and x.get('coordinates')]
    cells={}
    for x in rec:
        k=(math.floor(x['coordinates']['latitude']/0.75),math.floor(x['coordinates']['longitude']/0.75)); first=(x.get('datetimeFirst') or {}).get('utc','9999')
        if k not in cells or first<cells[k][0]: cells[k]=(first,x)
    sel=[v[1] for v in cells.values()]
    sp=f'{D}/openaq_series.json'; ser=json.load(open(sp)) if os.path.exists(sp) else {}
    for i,x in enumerate(sel):
        lid=str(x['id'])
        if lid in ser: continue
        if over_budget(60): print('OpenAQ: budget reached, remaining sites deferred'); break
        sid=[s['id'] for s in x['sensors'] if s['parameter']['id']==2][0]
        for t in range(3):
            r=requests.get(f'https://api.openaq.org/v3/sensors/{sid}/days/monthly',params=dict(limit=100,date_from='2019-01-01'),headers=H)
            if r.status_code==200: ser[lid]=[(m['period']['datetimeFrom']['local'][:7],m['value']) for m in r.json().get('results',[])]; break
            elif r.status_code==429: time.sleep(10)
            else: ser[lid]=[]; break
        time.sleep(1.05)
        if i%50==0: json.dump(ser,open(sp,'w')); print(i,len(sel),flush=True)
    json.dump(ser,open(sp,'w'))
    out=[]
    for x in sel:
        s=ser.get(str(x['id']))
        if not s: continue
        pts=sorted((int(k[:4]),int(k[5:7]),round(v,1)) for k,v in s if v is not None and 0<=v<1000)
        if not pts or pts[-1][0]<MONTHS[-1][0]: continue
        st=dict(id=str(x['id']),net='OpenAQ',name=(x['name'] or f"OpenAQ {x['id']}")[:60],country=x['country']['name'],provider=(x.get('provider') or {}).get('name'),lat=round(x['coordinates']['latitude'],4),lon=round(x['coordinates']['longitude'],4),vars={'pm25':metrics(pts)})
        out.append(st)
    json.dump(out,open(f'{D}/aq.json','w'))

def step_stations():
    s=open(f'{D}/noaa_sites.html').read(); meta={}
    for r in re.findall(r'<tr[^>]*>(.*?)</tr>',s,re.S):
        c=[html.unescape(re.sub('<[^>]+>','',x)).strip() for x in re.findall(r'<td[^>]*>(.*?)</td>',r,re.S)]
        if len(c)>=6:
            try: meta[c[0].rstrip('*')]=dict(name=c[1],country=c[2],lat=float(c[3]),lon=float(c[4]),elev=float(c[5]) if c[5] else None)
            except: pass
    noaa={}
    for gas in ('co2','ch4'):
        for f in glob.glob(f'{D}/noaa_{gas}/{gas}_*_month.txt'):
            code=os.path.basename(f).split('_')[1].upper(); pts=[]
            for line in open(f):
                if line.startswith('#'): continue
                p=line.split()
                if len(p)==4: pts.append((int(p[1]),int(p[2]),float(p[3])))
            pts=[p for p in pts if p[0]>=2015]
            if not pts or pts[-1][0]<MONTHS[-1][0]-2 or code not in meta: continue
            noaa.setdefault(code,dict(id=code,net='NOAA',**meta[code],vars={}))['vars'][gas]=metrics(pts)
    # Mauna Loa preliminary extension
    if 'MLO' in noaa and 'co2' in noaa['MLO']['vars']:
        d=noaa['MLO']['vars']['co2']; last=tuple(d['series'][-1][:2]); add=[]
        for line in open(f'{D}/co2_mm_mlo.csv'):
            p=line.strip().split(',')
            if p[0].isdigit() and (int(p[0]),int(p[1]))>last: add.append([int(p[0]),int(p[1]),float(p[3])])
        if add:
            d.update(metrics([tuple(x) for x in d['series']+add])); d['prelimFrom']=f"{add[0][0]}-{add[0][1]:02d}"
    icos=json.load(open(f'{D}/icos.json')); aq=json.load(open(f'{D}/aq.json'))
    json.dump(dict(icos=list(icos.values()),noaa=list(noaa.values()),aq=aq),open(f'{D}/stations.json','w'))

# ---------------- OCO-2 Fwd_FP / Lite 16-day windows ----------------
def step_oco2():
    import netCDF4 as nc
    TOK=os.environ.get('EARTHDATA_TOKEN','').strip()
    if len(TOK)<200: raise SystemExit('EARTHDATA_TOKEN missing or truncated (%d chars); set the repository secret'%len(TOK))
    B='https://oco2.gesdisc.eosdis.nasa.gov/data/OCO2_DATA/'
    def listing(prod,year):
        out=subprocess.run(f'curl -s {B}{prod}/{year}/',shell=True,capture_output=True,text=True).stdout
        return {m[11:17]:m for m in set(re.findall(r'oco2_(?:Fw|Lt)CO2_\d{6}_B[0-9A-Za-z]+_[0-9s]+\.nc4',out))}
    yrs=sorted(set(y for y,m in MONTHS)|{MONTHS[0][0]-1}); files={}
    for prod in ('OCO2_L2_Fwd_FP.11.3','OCO2_L2_Fwd_FP.11.2','OCO2_L2_Lite_FP.11.3r'):
        for y in yrs:
            for k,f in listing(prod,y).items(): files.setdefault(k,(prod,f))
    ends=[dt.date(y,m,15) for y,m in MONTHS]; NY,NX=720,1440; out=[]
    os.makedirs(f'{D}/oco2dl',exist_ok=True)
    os.makedirs(f'{D}/oco2grid',exist_ok=True)
    for e in ends:
        cp=f'{D}/oco2grid/{e}.json'
        if os.path.exists(cp) and e<dt.date.today()-dt.timedelta(days=3): out.append(json.load(open(cp))); print(e,'cached'); continue
        if over_budget(): print('OCO-2: budget reached, remaining windows deferred to the next run'); break
        S=np.zeros((NY,NX)); N=np.zeros((NY,NX)); n=0; ok=0; srcs=set()
        todo=[]
        for i in range(16):
            d=e-dt.timedelta(days=i); k=d.strftime('%y%m%d')
            if k in files: todo.append((d,)+files[k])
        from concurrent.futures import ThreadPoolExecutor
        def _dl(item):
            d,prod,fn=item; path=f'{D}/oco2dl/{fn}'
            subprocess.run(f'curl -s -L -m 600 -H "Authorization: Bearer {TOK}" -o {path} {B}{prod}/{d.year}/{fn}',shell=True); return item,path
        with ThreadPoolExecutor(6) as ex: dls=list(ex.map(_dl,todo))
        for (d,prod,fn),path in dls:
            if not os.path.exists(path): continue
            head=open(path,'rb').read(8)
            if not head.startswith(b'\x89HDF'):
                msg=open(path,'rb').read(300).decode('utf-8','ignore')
                if '401' in msg or 'Unauthorized' in msg or 'urs.earthdata' in msg: raise SystemExit('GES DISC rejected the Earthdata token (401). Regenerate it at urs.earthdata.nasa.gov and update the EARTHDATA_TOKEN secret.')
                os.remove(path); print('not a NetCDF file, skipped',fn); continue
            try:
                ds=nc.Dataset(path); x=np.array(ds.variables['xco2'][:],float); q=np.array(ds.variables['xco2_quality_flag'][:]); la=np.array(ds.variables['latitude'][:]); lo=np.array(ds.variables['longitude'][:]); ds.close()
            except Exception: os.remove(path); continue
            g=(q==0)&np.isfinite(x)&(x>350)&(x<500); x,la,lo=x[g],la[g],lo[g]
            iy=np.clip(((90-la)*4).astype(int),0,NY-1); ix=np.clip(((lo+180)*4).astype(int),0,NX-1)
            np.add.at(S,(iy,ix),x); np.add.at(N,(iy,ix),1); n+=len(x); ok+=1; srcs.add(prod); os.remove(path)
        if ok==0: continue
        g=np.where(N>0,S/np.maximum(N,1),np.nan)
        rec=dict(end=str(e),start=str(e-dt.timedelta(days=15)),days=ok,n=n,cells=int((N>0).sum()),mean=float(np.nanmean(g)),src=sorted(srcs),b64=base64.b64encode(np.where(np.isnan(g),-32768,np.round(g*10)).astype(np.int16).tobytes()).decode())
        json.dump(rec,open(cp,'w')); out.append(rec); print(e,ok,n,flush=True)
    print('windows built',len(out),'of',len(ends),'; daily files found',len(files))
    if not out: raise SystemExit('OCO-2: no windows built')
    json.dump(dict(res=0.25,ny=NY,nx=NX,cycles=out),open(f'{D}/oco2_fwd.json','w'))

# ---------------- remaining steps delegate to the reference scripts ----------------
def step_modis():  sh('python3 ndvi_hi.py')          # writes ndvi_hi/anom_*.png + meta.json
def step_geoscf(): sh('python3 geoscf_fetch2.py')    # PM2.5 monthly npy, then pm.json via assemble helper
def step_gibs():   sh('python3 bg_fetch.py')         # AIRS CO + monthly VIIRS fire grids
def step_s3ndvi():
    print('Sentinel-3 NDVI: see README step 7; the interactive code is reproduced in s3ndvi.py'); sh('python3 s3ndvi.py')
def step_enso():
    os.makedirs(f'{D}/enso',exist_ok=True)
    for u,f in [('https://www.cpc.ncep.noaa.gov/data/indices/wksst9120.for','wksst.txt'),('https://www.cpc.ncep.noaa.gov/data/indices/oni.ascii.txt','oni.txt'),('https://gml.noaa.gov/webdata/ccgg/trends/co2/co2_mm_gl.csv','co2_mm_gl.csv'),('https://gml.noaa.gov/webdata/ccgg/trends/co2/co2_gr_gl.csv','co2_gr_gl.csv')]:
        sh(f'curl -s -o {D}/enso/{f} {u}')
    wk=[]
    for line in open(f'{D}/enso/wksst.txt'):
        m=re.match(r'\s*(\d{2}[A-Z]{3}\d{4})\s+([\d.]+)\s*([-\d.]+)\s+([\d.]+)\s*([-\d.]+)\s+([\d.]+)\s*([-\d.]+)\s+([\d.]+)\s*([-\d.]+)',line)
        if m:
            d=dt.datetime.strptime(m.group(1),'%d%b%Y').date()
            if d.year>=2014: wk.append([d.isoformat(),float(m.group(6)),float(m.group(7))])
    oni=[[p[0],int(p[1]),float(p[3])] for line in open(f'{D}/enso/oni.txt') for p in [line.split()] if len(p)==4 and p[1].isdigit() and int(p[1])>=2014]
    gl=[[int(p[0]),int(p[1]),float(p[3]),float(p[5])] for line in open(f'{D}/enso/co2_mm_gl.csv') for p in [line.strip().split(',')] if p[0].isdigit() and int(p[0])>=2014]
    gr=[[int(p[0]),float(p[1])] for line in open(f'{D}/enso/co2_gr_gl.csv') for p in [line.strip().split(',')] if p[0].isdigit()]
    phase='El Niño' if oni[-1][2]>=0.5 else 'La Niña' if oni[-1][2]<=-0.5 else 'Neutral'
    json.dump(dict(weekly=wk,oni=oni,global_co2=gl,growth=gr,latest=dict(week=wk[-1],oni=oni[-1],phase=phase)),open(f'{D}/enso.json','w'))
def step_fires():
    pts=[]
    for u in ('https://firms.modaps.eosdis.nasa.gov/data/active_fire/suomi-npp-viirs-c2/csv/SUOMI_VIIRS_C2_Global_24h.csv','https://firms.modaps.eosdis.nasa.gov/data/active_fire/noaa-20-viirs-c2/csv/J1_VIIRS_C2_Global_24h.csv'):
        sh(f'curl -s -o {D}/f24.csv {u}')
        for r in csv.DictReader(open(f'{D}/f24.csv')):
            if r['confidence']=='low': continue
            pts.append((float(r['latitude']),float(r['longitude']),float(r['frp']),r['daynight']=='D',r['acq_date']))
    a=np.empty((len(pts),3),np.int16); a[:,0]=np.round([p[0]*100 for p in pts]); a[:,1]=np.round([p[1]*100 for p in pts]); a[:,2]=np.clip(np.round([p[2] for p in pts]),0,32000)
    json.dump(dict(n=len(pts),dates=sorted(set(p[4] for p in pts)),b64=base64.b64encode(a.tobytes()).decode(),day=int(sum(p[3] for p in pts))),open(f'{D}/fires.json','w'))

# ---------------- grid JSONs from the npy outputs of the reference scripts ----------------
def _b16(a): return base64.b64encode(np.where(np.isnan(a),-32768,np.clip(np.round(a*10),-32000,32000)).astype(np.int16).tobytes()).decode()
def step_grids():
    # GEOS-CF PM2.5: v2m_/v2h_ (current) and v1_ (baseline) npy from geoscf_fetch2.py in geoscf/
    def _stack(fs): return np.nanmean(np.stack([np.load(f) for f in fs]),axis=0) if fs else None
    base={m:_stack([f'geoscf/v1_{y}-{m:02d}.npy' for y in range(2021,2026) if os.path.exists(f'geoscf/v1_{y}-{m:02d}.npy')]) for m in range(1,13)}
    out=[]
    for y,m in MONTHS:
        f=next((f for f in (f'geoscf/v2m_{y}-{m:02d}.npy',f'geoscf/v2h_{y}-{m:02d}.npy') if os.path.exists(f)),None)
        if not f or base[m] is None: continue
        a=np.load(f)[::-1]; an=a-base[m][::-1]
        out.append(dict(date=f'{y}-{m:02d}',src='v2',partial=(y,m)==MONTHS[-1],mean=float(np.nanmean(a)),manom=float(np.nanmean(an)),abs=_b16(a),anom=_b16(an)))
    if out: json.dump(dict(ny=91,nx=180,months=out),open(f'{D}/pm.json','w'))
    print('pm',len(out))
    # AIRS CO (airs/a_*.npy, 360x720) -> 1.5 deg
    def co_m(y,m):
        f=f'airs/a_{y}-{m:02d}.npy'
        return np.nanmean(np.load(f).reshape(120,3,240,3),axis=(1,3)) if os.path.exists(f) else None
    co=[]
    for y,m in MONTHS:
        cur=co_m(y,m); bl=[b for b in (co_m(yy,m) for yy in range(y-5,y)) if b is not None]
        if cur is None or len(bl)<3: continue
        an=cur-np.nanmean(np.stack(bl),axis=0)
        co.append(dict(date=f'{y}-{m:02d}',partial=(y,m)>=MONTHS[-2],mean=float(np.nanmean(cur)),manom=float(np.nanmean(an)),nbase=len(bl),abs=base64.b64encode(np.where(np.isnan(cur),0,np.clip(np.round(cur),1,255)).astype(np.uint8).tobytes()).decode(),anom=base64.b64encode(np.where(np.isnan(an),-128,np.clip(np.round(an),-127,127)).astype(np.int8).tobytes()).decode()))
    if co: json.dump(dict(ny=120,nx=240,months=co),open(f'{D}/co.json','w'))
    print('co',len(co))
    # monthly fires (firesm/g_YYYY-MM-DD.npy, 180x360 counts) -> 2 deg, scaled to full month
    def fm(y,m):
        fs=sorted(glob.glob(f'firesm/g_{y}-{m:02d}-*.npy'))
        if not fs: return None
        nd=calendar.monthrange(y,m)[1]; g=sum(np.load(f) for f in fs).astype(float)*(nd/len(fs))
        return g.reshape(90,2,180,2).sum(axis=(1,3))
    fo=[]
    for y,m in MONTHS:
        cur=fm(y,m); bl=[b for b in (fm(yy,m) for yy in range(y-5,y)) if b is not None]
        if cur is None or len(bl)<3: continue
        an=cur-np.mean(bl,axis=0); enc=lambda a: base64.b64encode(np.clip(np.round(a),-32000,32000).astype(np.int16).tobytes()).decode()
        fo.append(dict(date=f'{y}-{m:02d}',partial=(y,m)==MONTHS[-1],total=int(cur.sum()),manom=float(an.mean()),abs=enc(cur),anom=enc(an)))
    if fo: json.dump(dict(ny=90,nx=180,months=fo),open(f'{D}/firem.json','w'))
    print('firem',len(fo))
def _requality_hires(page,q):
    from PIL import Image
    meta_file='ndvi_hi/meta.json'
    if not os.path.exists(meta_file): return
    meta=json.load(open(meta_file)); i=len(meta)-1; src=os.path.join('ndvi_hi',meta[i]['file'])
    w=src.replace('.png',f'_q{q}.webp'); Image.open(src).convert('RGBA').save(w,'WEBP',quality=q,method=6)
    b='data:image/webp;base64,'+base64.b64encode(open(w,'rb').read()).decode()
    t=open(page).read(); t=re.sub(rf'<script id="ndvi-img-{i}" type="text/plain">.*?</script>',lambda m:f'<script id="ndvi-img-{i}" type="text/plain">{b}</script>',t,flags=re.S); open(page,'w').write(t); print('requality',q)
def replace_image_blocks(page):
    """Swap the MODIS (ndvi_hi/) and Sentinel-3 (data/s3ndvi/) anomaly images and their meta into the page."""
    from PIL import Image
    t=open(page).read()
    def b64img(path,webp):
        if webp:
            w=path.replace('.png','.webp')
            if not os.path.exists(w): Image.open(path).convert('RGBA').save(w,'WEBP',quality=75,method=4)
            return 'data:image/webp;base64,'+base64.b64encode(open(w,'rb').read()).decode()
        return 'data:image/png;base64,'+base64.b64encode(open(path,'rb').read()).decode()
    for meta_file,folder,sid,did,webp in (('ndvi_hi/meta.json','ndvi_hi','ndvi-img','d-ndvi',True),(f'{D}/s3ndvi/meta.json',f'{D}/s3ndvi','s3-img','d-s3',False)):
        if not os.path.exists(meta_file): print('missing',meta_file); continue
        meta=json.load(open(meta_file)); keep=[]
        cur=len(re.findall(rf'<script id="{sid}-\d+"',t))
        if len(meta)<min(6,cur): print(f'{sid}: only {len(meta)} months built (page has {cur}); keeping existing images'); continue
        t=re.sub(rf'<script id="{sid}-\d+" type="text/plain">.*?</script>\n?','',t,flags=re.S)
        blocks=[]
        for i,m in enumerate(meta):
            blocks.append(f'<script id="{sid}-{i}" type="text/plain">{b64img(os.path.join(folder,m["file"]),webp)}</script>')
            keep.append({k:v for k,v in m.items() if k!='file'})
        t=re.sub(rf'<script id="{did}" type="application/json">.*?</script>',lambda mm:f'<script id="{did}" type="application/json">'+json.dumps(keep)+'</script>\n'+'\n'.join(blocks),t,flags=re.S)
    open(page,'w').write(t)

PAGE='../dashboard-single.html' if os.path.exists('../dashboard-single.html') else '../index.html'
def step_assemble():
    print('Assemble: run assemble.py (template placeholders) then apply the interactive page patches; '
          'in practice the easiest path is to keep index.html as the page and replace only its <script id="d-*"> data blocks '
          '(gzip+base64 for data-gz="1" blocks). See replace_data_blocks() below.')
    step_grids()
    replace_data_blocks(PAGE)
    replace_image_blocks(PAGE)
    # keep the page under the 16 MB artifact limit by lowering the hi-res NDVI WebP quality if needed
    for q in (62,52,42):
        if os.path.getsize(PAGE)<15.9e6: break
        _requality_hires(PAGE,q)
    print('%s %.2f MB'%(PAGE,os.path.getsize(PAGE)/1e6))
def replace_data_blocks(page):
    t=open(page).read()
    def gz(obj): return base64.b64encode(gzip.compress(json.dumps(obj,separators=(',',':')).encode(),9)).decode()
    blocks={'d-st':f'{D}/stations.json','d-oco2':f'{D}/oco2_fwd.json','d-enso':f'{D}/enso.json','d-fires':f'{D}/fires.json','d-pm':f'{D}/pm.json','d-co':f'{D}/co.json','d-firem':f'{D}/firem.json','d-ndvi2':f'{D}/ndvi2.json'}
    for id_,f in blocks.items():
        if not os.path.exists(f): print('missing',f); continue
        obj=json.load(open(f)); main=obj.get('cycles') or obj.get('months') or (obj if isinstance(obj,list) else obj)
        if isinstance(main,(list,dict)) and len(main)==0: print('empty, skipped',f); continue
        t=re.sub(rf'<script id="{id_}" type="application/json" data-gz="1">.*?</script>',lambda m:f'<script id="{id_}" type="application/json" data-gz="1">'+gz(obj)+'</script>',t,flags=re.S)
    t=re.sub(r'(Snapshot )\d+ \w+ \d{4}',rf'\g<1>{SNAPSHOT}',t)
    open(page,'w').write(t); print('wrote',page)
def step_test():
    sh(f'{sys.executable} test_page.py {PAGE}')
def step_split():
    # GitHub Pages copy: shell + data/.  The single-file page is kept as ../dashboard-single.html for the claude.ai artifact.
    if PAGE!='../dashboard-single.html':
        import shutil; shutil.copy('../index.html','../dashboard-single.html')
    sh(f'{sys.executable} split_page.py ../dashboard-single.html ..')
    sh(f'{sys.executable} test_page.py http://localhost:8765/index.html') if os.environ.get('TEST_SPLIT') else None
if __name__=='__main__':
    globals()['step_'+sys.argv[1]]()
