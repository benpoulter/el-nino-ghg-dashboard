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
    for v in ['oco2','ndvi','s3','pm','co','firem','none']:
        pg.click(f'input[name=base][value={v}]'); pg.wait_for_timeout(600); pg.click('#map',position={'x':640,'y':430}); pg.wait_for_timeout(200)
    pg.evaluate("()=>{document.querySelectorAll('.leaflet-marker-icon')[3].click()}"); pg.wait_for_timeout(800)
    n=pg.evaluate("()=>document.querySelectorAll('#asofT tr').length")
    if n<10: errs.append(f'data-as-of table has only {n} rows')
    for v in ['oco2','pm','co','firem']:
        empty=pg.evaluate(f"()=>{{const s=document.getElementById({{oco2:'ocoSl',pm:'pmSl',co:'coSl',firem:'fmSl'}}['{v}']);return +s.max<3}}")
        if empty: errs.append(f'{v} layer has too few dates')
    b.close()
if errs:
    print('PAGE TEST FAILED'); [print(' ',e) for e in errs]; sys.exit(1)
print('page test passed')
