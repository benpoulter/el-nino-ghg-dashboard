"""Build d-cards.json for the four headline indicator cards (global temperature, CO2, CH4, N2O growth).
Sources: Copernicus Climate Pulse ERA5 daily global 2 m temperature; NOAA GML global marine-surface monthly
CO2/CH4/N2O and Mauna Loa weekly CO2.  Usage: python3 cards.py <dir with the csv files> <out.json>"""
import sys, json, datetime as dt, statistics as stx
src, out = sys.argv[1], sys.argv[2]
def rows(f):
    for line in open(f):
        if line.startswith('#') or not line.strip() or line[0].isalpha(): continue
        yield line.strip().split(',')
# --- ERA5 daily global 2m temperature anomaly (vs 1991-2020)
t=[(r[0],float(r[3]),r[4]) for r in rows(f'{src}/t2m.csv') if r[0]>='2014-01-01']
vals=[round(a*1000) for _,a,_ in t]
m30=sum(a for _,a,_ in t[-30:])/30
temp=dict(start=t[0][0],last=t[-1][0],status=t[-1][2],daily=round(t[-1][1],3),m30=round(m30,3),offset_pi=0.88,v=vals)
# --- gases: 12-month growth of the deseasonalised trend, anomaly vs 2015-2024 mean growth
def gas(name,unit,dp):
    R=[(int(r[0]),int(r[1]),float(r[3]),float(r[5])) for r in rows(f'{src}/{name}_gl.csv') if float(r[5])>0]
    g=[(R[i][0],R[i][1],R[i][3]-R[i-12][3]) for i in range(12,len(R)) if (R[i][0]-R[i-12][0])*12+R[i][1]-R[i-12][1]==12]
    base=stx.mean(x[2] for x in g if 2015<=x[0]<=2024)
    s=[x for x in g if x[0]>=2014]
    y,m,last=s[-1]
    return dict(unit=unit,dp=dp,last=f'{y}-{m:02d}',growth=round(last,3),base=round(base,3),anom=round(last-base,3),value=round(R[-1][2],2),
                g=[[f'{a}-{b:02d}',round(c,3)] for a,b,c in s])
co2=gas('co2','ppm',2); ch4=gas('ch4','ppb',1); n2o=gas('n2o','ppb',2)
# --- Mauna Loa weekly: 12-month change, 4-week mean (near-real-time extension for CO2)
W=[(f'{r[0]}-{int(r[1]):02d}-{int(r[2]):02d}',float(r[4]),float(r[6])) for r in rows(f'{src}/co2_wk_mlo.csv') if float(r[4])>0 and float(r[6])>0]
last4=W[-4:]; co2['mlo']=dict(last=W[-1][0],value=W[-1][1],growth4=round(sum(a-b for _,a,b in last4)/len(last4),2))
json.dump(dict(built=dt.date.today().isoformat(),temp=temp,co2=co2,ch4=ch4,n2o=n2o),open(out,'w'),separators=(',',':'))
print('temp',temp['last'],temp['m30'],'| co2',co2['last'],co2['growth'],co2['anom'],'mlo',co2['mlo'],'| ch4',ch4['last'],ch4['growth'],ch4['anom'],'| n2o',n2o['last'],n2o['growth'],n2o['anom'])
