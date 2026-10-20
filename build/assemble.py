import json, base64
D='data/'; t=open('/home/claude/template2.html').read()
st=json.load(open(D+'stations.json'))
about=open('/home/claude/about_block.html').read().replace('__AQCOUNT__',f"{len(st['aq']):,}")
b64=lambda p,mt: f"data:{mt};base64,"+base64.b64encode(open(p,'rb').read()).decode()
ndvi=json.load(open(D+'ndvi/anom_meta.json'))
for m in ndvi: m['src']=b64(D+'ndvi/'+m['file'],'image/png'); del m['file']
s3n=json.load(open(D+'s3ndvi/meta.json'))
for m in s3n: m['src']=b64(D+'s3ndvi/'+m['file'],'image/png'); del m['file']
rep={'/*__LEAFLET_CSS__*/':open(D+'leaflet.css').read(),'__ABOUT__':about,'__LOGO__':b64(D+'spark-logo.png','image/png'),'__SNAPSHOT__':'18 Oct 2026',
 '__STATIONS__':open(D+'stations.json').read(),'__LAND__':open(D+'land_min.json').read(),'__OCO2__':open(D+'oco2_fwd.json').read(),
 '__NDVI__':json.dumps(ndvi),'__S3NDVI__':json.dumps(s3n),'__FIRES__':open(D+'fires.json').read(),'__PM__':open(D+'pm.json').read()}
for k,v in rep.items(): assert k in t,k; t=t.replace(k,v.replace('</script','<\\/script'))
open('/mnt/user-data/outputs/el-nino-ghg-dashboard.html','w').write(t); print(len(t)/1e6,'MB')
