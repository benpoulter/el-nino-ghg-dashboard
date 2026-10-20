import urllib.request, json, io, csv, collections, numpy as np, subprocess
from icoscp_core.icos import meta
from icoscp_core.cpb import TableRequest, codec_from_dobj_meta
rows=list(csv.DictReader(open('icos_ch4_objs.csv')))
stcsv=subprocess.run(['curl','-s','-H','Accept: text/csv','--data-urlencode','query@q1.rq','https://meta.icos-cp.eu/sparql'],capture_output=True,text=True).stdout
smeta={r['id']:r for r in csv.DictReader(io.StringIO(stcsv))}
by=collections.defaultdict(list)
for r in rows: by[r['stId']].append(r)
H={"Accept":"application/octet-stream","Content-Type":"application/json","User-Agent":"Mozilla/5.0","Referer":"https://data.icos-cp.eu/portal/","Origin":"https://data.icos-cp.eu"}
def fetch(uri):
    dobj=meta.get_dobj_meta(uri); codec=codec_from_dobj_meta(dobj, TableRequest(['TIMESTAMP','ch4'],None,None))
    req=urllib.request.Request("https://data.icos-cp.eu/cpb",data=json.dumps(codec.json_payload).encode(),headers=H,method="POST")
    return codec.parse_cpb_response(io.BytesIO(urllib.request.urlopen(req,timeout=90).read()), False)
import os
out=json.load(open('icos_ch4.json')) if os.path.exists('icos_ch4.json') else {}
for sid,objs in by.items():
    if sid not in smeta or sid in out: continue
    h=max(float(o['samplingHeight'] or 0) for o in objs); sel=[o for o in objs if float(o['samplingHeight'] or 0)==h]
    monthly={}
    for o in sorted(sel,key=lambda o:('NRT' in o['specLabel'], o['timeStart'])):
        try: arr=fetch(o['dobj'])
        except Exception as e: print('fail',sid,e,flush=True); continue
        isL2='Release' in o['specLabel']; ts=arr['TIMESTAMP'].astype('datetime64[M]'); v=arr['ch4'].astype(float); ok=~np.isnan(v)
        for mo in np.unique(ts[ok]):
            vv=v[ok&(ts==mo)]; key=str(mo)
            if key in monthly and monthly[key][2] and not isL2: continue
            if key in monthly and monthly[key][2]==isL2: s,n,_=monthly[key]; monthly[key]=(s+vv.sum(),n+len(vv),isL2)
            else: monthly[key]=(vv.sum(),len(vv),isL2)
    ser=sorted((k,round(s/n,1)) for k,(s,n,_) in monthly.items() if n>=120)
    if ser: out[sid]=dict(height=h,series=[[int(k[:4]),int(k[5:7]),v] for k,v in ser]); print(sid,h,ser[-1],flush=True); json.dump(out,open('icos_ch4.json','w'),separators=(',',':'))
json.dump(out,open('icos_ch4.json','w'),separators=(',',':')); print('DONE',len(out))
