import json
sel=json.load(open('openaq/selected.json')); ser=json.load(open('openaq/series.json'))
out=[]
for x in sel:
    lid=str(x['id']); s=ser.get(lid)
    if not s: continue
    pts=[(int(k[:4]),int(k[5:7]),v) for k,v,c in s if v is not None and v>=0 and v<1000]
    if not pts: continue
    pts.sort(); y,m,v=pts[-1]
    if (y,m)<(2026,9): continue
    base=[p[2] for p in pts if p[1]==m and y-5<=p[0]<=y-1]
    prev=[p[2] for p in pts if p[0]==y-1 and p[1]==m]
    name=x['name'] or f"OpenAQ {lid}"
    out.append(dict(id=lid,net='OpenAQ',name=name[:60],country=x['country']['name'],provider=(x.get('provider') or {}).get('name'),lat=round(x['coordinates']['latitude'],4),lon=round(x['coordinates']['longitude'],4),
        latest=[y,m,round(v,1)],anom=round(v-sum(base)/len(base),1) if len(base)>=3 else None,yoy=round(v-prev[0],1) if prev else None,nbase=len(base),series=[[a,b,round(c,1)] for a,b,c in pts]))
json.dump(out,open('aq.json','w'),separators=(',',':'))
import os; print(len(out),'sites,',sum(1 for o in out if o['anom'] is not None),'with anomaly,',os.path.getsize('aq.json'),'bytes')
