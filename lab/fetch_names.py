"""Save symbol -> company name + type from the TSX/TSXV directory (runs on GitHub)."""
import json, urllib.request
URLS = {".TO": "https://www.tsx.com/json/company-directory/search/tsx/%5E*",
        ".V": "https://www.tsx.com/json/company-directory/search/tsxv/%5E*"}
out = {}
for suf, url in URLS.items():
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    data = json.loads(urllib.request.urlopen(req, timeout=60).read().decode())
    for co in data.get("results", []):
        for inst in co.get("instruments", []) or [{"symbol": co.get("symbol"), "name": co.get("name")}]:
            sym = (inst.get("symbol") or "").strip()
            if sym:
                out[sym.replace(".", "-") + suf] = {"name": inst.get("name") or co.get("name"),
                                                     "company": co.get("name")}
json.dump(out, open("universe_names.json", "w"), indent=0, sort_keys=True)
print(len(out), "names")
