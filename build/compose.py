"""Compose the dashboard from its source and its data.

  src/page.html   the page code (HTML, CSS, JavaScript): edit this to change the dashboard
  src/data/       hand-maintained site lists (d-other, d-paf, d-saeon, d-lsce) - edit these
  data/           every other data block (d-*.json, *-img-N.webp|png), produced by the pipeline and published on gh-pages

Usage: python3 compose.py [repo root]   -> writes dashboard-single.html (self-contained) and index.html (Pages shell)
       python3 compose.py --extract     -> one-off: (re)create src/page.html from dashboard-single.html
"""
import os, re, sys, gzip, base64
ROOT = next((a for a in sys.argv[1:] if not a.startswith('--')), os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))
SRC, DATA = os.path.join(ROOT, 'src', 'page.html'), os.path.join(ROOT, 'data')
BLOCK = re.compile(r'<script id="([^"]+)" type="(application/json|text/plain)"( data-gz="1")?>(.*?)</script>', re.S)

def extract():
    t = open(os.path.join(ROOT, 'dashboard-single.html')).read()
    code = BLOCK.sub(lambda m: f'<script id="{m.group(1)}" type="{m.group(2)}"{m.group(3) or ""}></script>', t)
    open(SRC, 'w').write(code); print('src/page.html: %.2f MB' % (len(code) / 1e6))

def body(id_, kind, gz):
    for ext, mime in (('json', None), ('webp', 'image/webp'), ('png', 'image/png')):
        f = next((c for c in (os.path.join(ROOT, 'src', 'data', f'{id_}.{ext}'), os.path.join(DATA, f'{id_}.{ext}')) if os.path.exists(c)), None)
        if not f: continue
        if mime: return f'data:{mime};base64,' + base64.b64encode(open(f, 'rb').read()).decode()
        raw = open(f, encoding='utf-8').read()
        return base64.b64encode(gzip.compress(raw.encode(), 9, mtime=0)).decode() if gz else raw.replace('</script', '<\\/script')
    raise SystemExit(f'compose: no data file for block {id_}')

def compose():
    code = open(SRC).read(); missing = []
    def fill(m):
        try: return f'<script id="{m.group(1)}" type="{m.group(2)}"{m.group(3) or ""}>{body(m.group(1), m.group(2), m.group(3))}</script>'
        except SystemExit as e: missing.append(str(e)); return m.group(0)
    single = BLOCK.sub(fill, code)
    if missing: raise SystemExit('\n'.join(missing))
    shell = re.sub(BLOCK.pattern + r'\n?', '', code, flags=re.S)   # the Pages copy loads every block from data/
    open(os.path.join(ROOT, 'dashboard-single.html'), 'w').write(single)
    open(os.path.join(ROOT, 'index.html'), 'w').write(shell)
    print('dashboard-single.html %.1f MB, index.html %.2f MB, %d data blocks' % (len(single) / 1e6, len(shell) / 1e6, len(BLOCK.findall(code))))

if __name__ == '__main__':
    extract() if '--extract' in sys.argv else compose()
