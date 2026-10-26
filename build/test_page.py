"""Headless smoke test: load the page, exercise every basemap and a station, fail on JS errors.
Usage: python3 test_page.py <path-or-url>"""
import sys, subprocess
try: from playwright.sync_api import sync_playwright
except ImportError:
    subprocess.run([sys.executable,'-m','pip','install','-q','playwright'],check=True); subprocess.run([sys.executable,'-m','playwright','install','chromium'],check=True)
    from playwright.sync_api import sync_playwright
target=sys.argv[1]
url=target if target.startswith('http') else 'file://'+__import__('os').path.abspath(target)
errs=[]
with sync_playwright() as p:
    b=p.chromium.launch(); pg=b.new_page(viewport={'width':1400,'height':860})
    pg.on('pageerror',lambda e:errs.append('pageerror: '+str(e))); pg.on('console',lambda m: errs.append('console: '+m.text[:200]) if m.type=='error' else None)
    pg.goto(url); pg.wait_for_function("()=>!document.getElementById('splash')",timeout=60000)
    pg.evaluate("()=>{const b=document.getElementById('box');b.classList.remove('hidden');b.classList.add('open');}")
    pg.click('#tabs button[data-tab=bases]')
    for v in ['oco2','ndvi','s3','pm','co','firem','none']:
        pg.click(f'input[name=base][value={v}]'); pg.wait_for_timeout(600); pg.click('#map',position={'x':640,'y':430}); pg.wait_for_timeout(200)
    pg.evaluate("()=>{document.querySelectorAll('.leaflet-marker-icon')[3].click()}"); pg.wait_for_timeout(800)
    n=pg.evaluate("()=>document.querySelectorAll('#asofT tr').length")
    if n<10: errs.append(f'data-as-of table has only {n} rows')
    for v in ['oco2','pm','co','firem']:
        empty=pg.evaluate(f"()=>{{const s=document.getElementById({{oco2:'ocoSl',pm:'pmSl',co:'coSl',firem:'fmSl'}}['{v}']);return +s.max<3}}")
        if empty: errs.append(f'{v} layer has too few dates')
    # registry layers: every site must be drawn (cluster counts + single markers >= site count)
    pg.evaluate("()=>{const b=document.getElementById('box');b.classList.remove('hidden');b.classList.add('open');}")
    pg.click('#tabs button[data-tab=sites]')
    counts=pg.evaluate("()=>({F:JSON.parse(document.getElementById('d-flux')?'[]':'[]')})")
    for net in ['FLUXNET2015','FLUXNET-CH4','TCCON','COCCON','BGC','OTHER','PAF','SAEON','LSCE']:
        try:
            pg.click(f'.fluxCk[data-net="{net}"]'); pg.wait_for_timeout(700)
            exp=pg.evaluate(f"()=>{{const t=document.querySelector('.fluxCk[data-net=\"{net}\"]').closest('.hd').querySelector('small').textContent;return parseInt(t)||0}}")
            got=pg.evaluate("()=>{let t=0;document.querySelectorAll('.fxc').forEach(e=>t+=+e.textContent);const singles=document.querySelectorAll('.leaflet-stations-pane svg path.leaflet-interactive').length+[...document.querySelectorAll('.leaflet-stations-pane .leaflet-marker-icon')].filter(e=>!e.querySelector('.fxc')&&e.innerHTML.includes('rotate(45 7 7)')).length;return t+singles}")
            if exp and got<exp: errs.append(f'{net}: only {got} of {exp} sites rendered')
            pg.click(f'.fluxCk[data-net="{net}"]'); pg.wait_for_timeout(200)
        except Exception as e: errs.append(f'{net} layer check failed: {str(e)[:80]}')
    # with a chart open, the bottom controls must stay clickable (not covered by the chart panel)
    pg.click('#tLayers') if pg.evaluate("()=>!document.getElementById('box').classList.contains('hidden')") else None
    pg.evaluate("()=>{const m=document.querySelectorAll('.leaflet-stations-pane .leaflet-marker-icon');m[3]&&m[3].click()}"); pg.wait_for_timeout(800)
    cov=pg.evaluate("()=>{const c=document.getElementById('chart').getBoundingClientRect();return ['#searchBox','#statsBtn'].filter(s=>{const r=document.querySelector(s).getBoundingClientRect();return r.bottom>c.top+2&&r.top<c.bottom&&getComputedStyle(document.querySelector(s)).display!=='none'})}")
    if cov: errs.append(f'covered by the chart panel: {cov}')
    pg.evaluate("()=>document.getElementById('cClose').click()")
    # NOAA observatories must be drawn above the flask triangles
    z=pg.evaluate("()=>{const ms=[...document.querySelectorAll('.leaflet-stations-pane .leaflet-marker-icon')];const o=ms.filter(e=>e.innerHTML.includes('M9 16 16.4'));return o.length?Math.min(...o.map(e=>+e.style.zIndex))-Math.max(...ms.filter(e=>!e.innerHTML.includes('M9 16 16.4')).map(e=>+e.style.zIndex||0)):null}")
    if z is not None and z<0: errs.append('NOAA observatory markers drawn below other stations')
    # a stale saved panel position must not push the panel off screen
    pg.evaluate("()=>localStorage.setItem('layersPos',JSON.stringify({l:'9999px',t:'-50px'}))"); pg.reload(); pg.wait_for_function("()=>!document.getElementById('splash')",timeout=60000); pg.click('#tLayers'); pg.wait_for_timeout(300)
    r=pg.evaluate("()=>{const b=document.getElementById('box');const q=b.getBoundingClientRect();return [q.left,q.top,q.right,innerWidth,getComputedStyle(b).display]}")
    if r[4]!='block' or r[0]<0 or r[2]>r[3]+1 or r[1]<50: errs.append(f'Layers panel off screen with stale saved position: {r}')
    pg.evaluate("()=>localStorage.removeItem('layersPos')")
    b.close()
if errs:
    print('PAGE TEST FAILED'); [print(' ',e) for e in errs]; sys.exit(1)
print('page test passed')
