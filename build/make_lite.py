"""Make the reduced copy for the claude.ai artifact (16 MB publishing limit) from dashboard-single.html:
same code and data, with the image basemaps re-encoded smaller.  Usage: python3 make_lite.py <in.html> <out.html>"""
import re, sys, io, base64
from PIL import Image
Image.MAX_IMAGE_PIXELS = None
src, dst = sys.argv[1], sys.argv[2]
t = open(src).read()
# family: (max width, WebP quality); the latest MODIS month keeps a little more detail
PLAN = {'ndvi': (1440, 42), 's3': (1080, 38), 'sst': (900, 42), 'chl': (900, 40), 'pchl': (900, 40),
        'pndvi': (900, 40), 'glwd': (1080, 40), 'tc': (1080, 50)}
for fam, (w, q) in PLAN.items():
    n = len(re.findall(rf'<script id="{fam}-img-\d+"', t))
    def conv(m):
        i = int(m.group(1)); im = Image.open(io.BytesIO(base64.b64decode(m.group(2).split(',', 1)[1]))).convert('RGBA')
        ww, qq = (2880, 55) if (fam == 'ndvi' and i == n - 1) else (w, q)
        if im.width > ww: im = im.resize((ww, round(ww * im.height / im.width)), Image.BILINEAR)
        o = io.BytesIO(); im.save(o, 'WEBP', quality=qq, method=4)
        return f'<script id="{fam}-img-{i}" type="text/plain">data:image/webp;base64,{base64.b64encode(o.getvalue()).decode()}</script>'
    t = re.sub(rf'<script id="{fam}-img-(\d+)" type="text/plain">(.*?)</script>', conv, t, flags=re.S)
t = t.replace("Shown at ${c.res===0.05?'native 0.05° (~5 km)':'0.125° (~14 km)'}",
              "Shown at reduced resolution in this copy; the GitHub Pages site shows full resolution")
open(dst, 'w').write(t); print('%s: %.1f MB' % (dst, len(t) / 1e6))
