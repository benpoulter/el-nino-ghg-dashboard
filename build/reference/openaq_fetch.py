import requests, json, time, os
K=open('openaq.txt').read().strip(); H={'X-API-Key':K}
sel=json.load(open('openaq/selected.json'))
out={}
if os.path.exists('openaq/series.json'): out=json.load(open('openaq/series.json'))
for i,x in enumerate(sel):
    lid=str(x['id'])
    if lid in out: continue
    sid=[s['id'] for s in x['sensors'] if s['parameter']['id']==2][0]
    for t in range(3):
        r=requests.get(f'https://api.openaq.org/v3/sensors/{sid}/days/monthly',params=dict(limit=100,date_from='2019-01-01'),headers=H)
        if r.status_code==200:
            res=r.json().get('results',[])
            out[lid]=[(m['period']['datetimeFrom']['local'][:7],(round(m['value'],1) if m['value'] is not None else None),m['coverage']['percentComplete'] if m.get('coverage') else None) for m in res]
            break
        elif r.status_code==429: time.sleep(10)
        else: out[lid]=[]; break
    rem=int(r.headers.get('x-ratelimit-remaining',10))
    time.sleep(1.05 if rem>5 else 10)
    if i%50==0: json.dump(out,open('openaq/series.json','w')); print(i,len(out),flush=True)
json.dump(out,open('openaq/series.json','w')); print('DONE',len(out))
