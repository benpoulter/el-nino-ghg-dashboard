"""Monthly NOAA observatory check (run on the 10th by .github/workflows/noaa-monthly.yml).

Reports, for each NOAA baseline observatory, the last month of the official annual release, the last month from the
near-real-time (NRT) hourly files, and how far behind the NRT data are. Writes a Markdown table to the GitHub job
summary and a warning annotation for any site whose NRT data are more than two months old.
Usage: python3 noaa_check.py <dashboard-single.html> [data dir]"""
import os, re, sys, json, gzip, base64, datetime as dt
page = sys.argv[1]; D = sys.argv[2] if len(sys.argv) > 2 else 'data'
t = open(page).read()
m = re.search(r'<script id="d-st" type="application/json" data-gz="1">(.*?)</script>', t, re.S)
st = json.loads(gzip.decompress(base64.b64decode(m.group(1))))
today = dt.date.today(); ym = lambda y, mo: f'{y}-{mo:02d}'
def months_behind(y, mo): return (today.year - y) * 12 + today.month - mo
def nrt_last(site):
    f = f'{D}/noaa_obs/nrt_co2_{site}.txt'
    if not os.path.exists(f): return None
    last = None
    for line in open(f):
        if line[:3] == site:
            p = line.split(); last = p[7][:10]
    return last
rows, warn = [], []
for s in sorted(st.get('noaaobs', []), key=lambda x: x['id']):
    for gas, d in s['vars'].items():
        y, mo, v = d['latest']; pf = d.get('prelimFrom')
        off = [x for x in d['series'] if not pf or ym(x[0], x[1]) < pf]
        off_end = ym(*off[-1][:2]) if off else '—'
        lag = months_behind(y, mo)
        rows.append(f"| {s['id']} | {s['name']} | {gas.upper()} | {off_end} | {ym(y, mo)} | {v} | {d.get('anom')} | {lag} | "
                    f"{nrt_last(s['id']) if gas == 'co2' else 'no NRT release'} |")
        if gas == 'co2' and lag > 2: warn.append(f"{s['id']} CO2 latest month {ym(y, mo)} is {lag} months old")
md = ['## NOAA baseline observatories — monthly check, ' + today.isoformat(), '',
      '| Site | Name | Gas | Official release to | Latest month shown | Value | vs 5-yr mean | Months behind | Last NRT hour |',
      '|---|---|---|---|---|---|---|---|---|'] + rows + ['', ('**Warnings:** ' + '; '.join(warn)) if warn else 'All CO₂ series are within two months of today.']
out = '\n'.join(md); print(out)
if os.environ.get('GITHUB_STEP_SUMMARY'): open(os.environ['GITHUB_STEP_SUMMARY'], 'a').write(out + '\n')
for w in warn: print(f'::warning::{w}')
