"""Sentinel-3 (CLMS) NDVI 300 m 10-daily v3 anomalies from the CDSE S3 store (needs AWS_* keys)."""
import boto3, rasterio, numpy as np, json, os, datetime as dt
from PIL import Image
OUT='data/s3ndvi'; os.makedirs(OUT,exist_ok=True)
s3=boto3.client('s3',endpoint_url='https://eodata.dataspace.copernicus.eu',region_name='default')
PFX='CLMS/bio-geophysical/vegetation_indices/ndvi_global_300m_10daily_v3/'
def find(y,m,d):
    for o in s3.list_objects_v2(Bucket='eodata',Prefix=f"{PFX}{y}/{m:02d}/{d:02d}/").get('Contents',[]):
        if 'NDVI300-NDVI_' in o['Key'] and o['Key'].endswith('.tiff'): return o['Key']
def read(y,m,d):
    k=find(y,m,d)
    if not k: return None
    with rasterio.open('/vsis3/eodata/'+k) as ds: a=ds.read(1,out_shape=(ds.height//32,ds.width//32))
    return np.where(a<=250,a*0.004-0.08,np.nan).astype(np.float32)
def colorize(a,lim=0.2):
    t=np.clip(a/lim,-1,1); neg=np.array([140,81,10]); mid=np.array([245,245,245]); pos=np.array([1,102,60])
    rgb=np.where(t[...,None]<0,mid+(neg-mid)*(-t)[...,None],mid+(pos-mid)*t[...,None]); al=np.where(np.isnan(a),0,210).astype(np.uint8)
    return np.dstack([np.nan_to_num(rgb,nan=0).astype(np.uint8),al])
# last 12 dekads that exist
today=dt.date.today(); deks=[]; d=dt.date(today.year,today.month,1)
while len(deks)<12:
    for dd in (21,11,1):
        c=dt.date(d.year,d.month,dd)
        if c<today and find(c.year,c.month,dd): deks.append((c.year,c.month,dd))
        if len(deks)>=12: break
    d=(d.replace(day=1)-dt.timedelta(days=1)).replace(day=1)
meta=[]
for y,m,dd in deks:
    cur=read(y,m,dd); base=[b for b in (read(yy,m,dd) for yy in range(y-5,y)) if b is not None]
    an=cur-np.nanmean(np.stack(base),axis=0)
    fn=f"anom_{y}-{m:02d}-{dd:02d}.png"; Image.fromarray(colorize(an),'RGBA').resize((1512,588),Image.BILINEAR).quantize(colors=128,method=Image.Quantize.FASTOCTREE).save(f"{OUT}/{fn}",optimize=True)
    meta.append(dict(date=f"{y}-{m:02d}-{dd:02d}",baseline=f"{y-5}–{y-1} ({len(base)} yrs)",mean=float(np.nanmean(an)),file=fn)); print(y,m,dd,flush=True)
json.dump(meta[::-1],open(f'{OUT}/meta.json','w'))
