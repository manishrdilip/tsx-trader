"""Extract annual (10-K, FY) facts from SEC companyfacts.zip -> sec_annual.csv.gz (point-in-time via 'filed')."""
import json, zipfile, gzip, csv
from datetime import date
TAGS = {'NetIncomeLoss': 'ni', 'Revenues': 'rev', 'RevenueFromContractWithCustomerExcludingAssessedTax': 'rev2',
        'SalesRevenueNet': 'rev3', 'StockholdersEquity': 'eq', 'Assets': 'assets', 'Liabilities': 'liab',
        'AssetsCurrent': 'ca', 'LiabilitiesCurrent': 'cl', 'LongTermDebt': 'ltd',
        'NetCashProvidedByUsedInOperatingActivities': 'cfo', 'PaymentsToAcquirePropertyPlantAndEquipment': 'capex'}
tick = json.load(open('company_tickers.json'))
cik2t = {}
for v in tick.values(): cik2t.setdefault(int(v['cik_str']), v['ticker'])
z = zipfile.ZipFile('companyfacts.zip')
out = gzip.open('lab/sec/sec_annual.csv.gz', 'wt', newline=''); w = csv.writer(out)
w.writerow(['ticker', 'cik', 'field', 'fy_end', 'filed', 'value']); n = 0
for name in z.namelist():
    try: cik = int(name[3:13])
    except ValueError: continue
    if cik not in cik2t: continue
    g = json.loads(z.read(name)).get('facts', {}).get('us-gaap', {})
    for tag, f in TAGS.items():
        for r in g.get(tag, {}).get('units', {}).get('USD', []):
            if r.get('form') not in ('10-K', '10-K/A') or r.get('fp') != 'FY': continue
            if 'start' in r and not 330 <= (date.fromisoformat(r['end']) - date.fromisoformat(r['start'])).days <= 400: continue
            w.writerow([cik2t[cik], cik, f, r['end'], r['filed'], r['val']]); n += 1
out.close(); print('rows', n)
