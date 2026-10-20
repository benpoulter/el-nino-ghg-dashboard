import json, glob, re, html
def metrics(pts):
    pts=sorted(pts); y,m,v=pts[-1]
    base=[p[2] for p in pts if p[1]==m and y-5<=p[0]<=y-1]; prev=[p[2] for p in pts if p[0]==y-1 and p[1]==m]
    return dict(latest=[y,m,v],anom=round(v-sum(base)/len(base),2) if len(base)>=3 else None,yoy=round(v-prev[0],2) if prev else None,nbase=len(base),series=[list(p) for p in pts])
# NOAA
s=open('noaa/sites.html').read(); meta={}
for r in re.findall(r'<tr[^>]*>(.*?)</tr>',s,re.S):
    c=[html.unescape(re.sub('<[^>]+>','',x)).strip() for x in re.findall(r'<td[^>]*>(.*?)</td>',r,re.S)]
    if len(c)>=6:
        try: meta[c[0].rstrip('*')]=dict(name=c[1],country=c[2],lat=float(c[3]),lon=float(c[4]),elev=float(c[5]) if c[5] else None)
        except: pass
noaa={}
for gas,d in [('co2','noaa'),('ch4','noaa_ch4')]:
    for f in glob.glob(f'{d}/{gas}_*_month.txt'):
        code=f.split('/')[-1].split('_')[1].upper(); pts=[]
        for line in open(f):
            if line.startswith('#'): continue
            p=line.split()
            if len(p)==4: pts.append((int(p[1]),int(p[2]),float(p[3])))
        pts=[p for p in pts if p[0]>=2015]
        if not pts or pts[-1][0]<2024 or code not in meta: continue
        st=noaa.setdefault(code,dict(id=code,net='NOAA',**meta[code],vars={}))
        st['vars'][gas]=metrics(pts)
# ICOS
old=json.load(open('icos.json')); ch4=json.load(open('icos_ch4.json'))
icos={}
for s_ in old:
    st=dict(id=s_['id'],net='ICOS',name=s_['name'],country=s_['country'],lat=s_['lat'],lon=s_['lon'],elev=s_['elev'],height=s_['height'],vars={})
    st['vars']['co2']=metrics([tuple(p) for p in s_['series']]); icos[s_['id']]=st
for sid,d in ch4.items():
    if sid not in icos:
        continue
    pts=[tuple(p) for p in d['series']]
    if pts[-1][0]<2026: continue
    icos[sid]['vars']['ch4']=metrics(pts)
# AQ
aq=json.load(open('aq.json')); aqo=[]
for a in aq:
    st={k:a[k] for k in ['id','net','name','country','provider','lat','lon']}; st['vars']={'pm25':{k:a[k] for k in ['latest','anom','yoy','nbase','series']}}; aqo.append(st)
json.dump(dict(icos=list(icos.values()),noaa=list(noaa.values()),aq=aqo),open('stations.json','w'),separators=(',',':'))
import os; print(len(icos),sum('ch4' in s['vars'] for s in icos.values()),len(noaa),sum('ch4' in s['vars'] for s in noaa.values()),len(aqo),os.path.getsize('stations.json'))
