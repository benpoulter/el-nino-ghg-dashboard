"""Split the single-file dashboard into a light shell (index.html) + data/ files for GitHub Pages.
Usage: python3 split_page.py <single.html> <out_dir>
The page's loaders already fall back to fetch('data/<id>.json') and data/<img>.webp|png when the inline blocks are absent."""
import re, sys, os, gzip, base64
src, out = sys.argv[1], sys.argv[2]
t=open(src).read(); os.makedirs(os.path.join(out,'data'),exist_ok=True)
def put(name,data,mode='w'): open(os.path.join(out,'data',name),mode).write(data)
# JSON blocks (gzipped or plain)
def repl_json(m):
    id_,gz,body=m.group(1),m.group(2),m.group(3)
    raw=gzip.decompress(base64.b64decode(body)).decode() if gz else body.replace('<\\/script','</script>')
    put(id_+'.json',raw); return ''
t=re.sub(r'<script id="(d-[a-z0-9]+)" type="application/json"( data-gz="1")?>(.*?)</script>\n?',repl_json,t,flags=re.S)
# image blocks
def repl_img(m):
    id_,body=m.group(1),m.group(2); mt=re.match(r'data:image/(\w+);base64,(.*)',body,re.S)
    ext={'webp':'webp','png':'png'}[mt.group(1)]; put(id_+'.'+ext,base64.b64decode(mt.group(2)),'wb'); return ''
t=re.sub(r'<script id="((?:ndvi|s3|sst|chl|glwd)-img-\d+)" type="text/plain">(.*?)</script>\n?',repl_img,t,flags=re.S)
# the s3 images are PNG but the loader expects data/s3-img-N.png, ndvi webp -> both handled by extension
open(os.path.join(out,'index.html'),'w').write(t)
print('shell %.2f MB, data files %d'%(os.path.getsize(os.path.join(out,'index.html'))/1e6,len(os.listdir(os.path.join(out,'data')))))
