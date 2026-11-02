"""Fair comparison: all three factors scored on one identical set of rows.

The first pass scored each factor on its own subset, which is not a comparison.
Here a row survives only if its employer AND its city each have at least MIN_N
filings, so every factor is measured on exactly the same wages.
"""
import sys, re, json, statistics, collections
import openpyxl

MIN_N = 30
PER_YEAR = {"Year": 1.0, "Hour": 2080.0, "Week": 52.0, "Bi-Weekly": 26.0, "Month": 12.0}
CORE = {"15-1252", "15-1251", "15-1253"}
LEVELS = [("principal", r"\bprincipal\b|\bdistinguished\b|\bfellow\b"), ("staff", r"\bstaff\b"),
          ("lead", r"\blead\b|\bleader\b"), ("manager", r"\bmanager\b|\bdirector\b|\bhead of\b|\bvp\b"),
          ("architect", r"\barchitect\b"), ("senior", r"\bsenior\b|\bsr\.?\b|\biii\b"),
          ("mid", r"\bii\b|\bintermediate\b"),
          ("junior", r"\bjunior\b|\bjr\.?\b|\bentry\b|\bassociate\b|\bgraduate\b")]
LR = [(n, re.compile(p, re.I)) for n, p in LEVELS]
def lvl(t):
    for n, rx in LR:
        if rx.search(t or ""): return n
    return "unlabelled"
def txt(v): return "" if v is None else str(v).strip()
def pctile(s, p):
    s = sorted(s); k = (len(s) - 1) * p / 100
    lo, hi = int(k), min(int(k) + 1, len(s) - 1)
    return s[lo] + (s[hi] - s[lo]) * (k - lo)

def omega_sq(groups):
    vals = [v for g in groups.values() for v in g]
    N, k = len(vals), len(groups)
    if k < 2 or N - k < 1: return None
    gm = statistics.fmean(vals)
    ss_b = sum(len(g) * (statistics.fmean(g) - gm) ** 2 for g in groups.values())
    ss_t = sum((v - gm) ** 2 for v in vals)
    ms_w = (ss_t - ss_b) / (N - k)
    den = ss_t + ms_w
    return round(max(0.0, (ss_b - (k - 1) * ms_w) / den), 4) if den else None

wb = openpyxl.load_workbook(sys.argv[1], read_only=True, data_only=True)
ws = wb[wb.sheetnames[0]]
rows = ws.iter_rows(values_only=True)
h = {c: i for i, c in enumerate(next(rows))}
recs = []
for r in rows:
    if r[h["CASE_STATUS"]] is None and r[h["VISA_CLASS"]] is None: continue
    if txt(r[h["CASE_STATUS"]]) != "Certified": continue
    if txt(r[h["VISA_CLASS"]]) != "H-1B": continue
    if txt(r[h["SOC_CODE"]]).split(".")[0] not in CORE: continue
    if txt(r[h["FULL_TIME_POSITION"]]).upper() != "Y": continue
    m = PER_YEAR.get(txt(r[h["WAGE_UNIT_OF_PAY"]]))
    if not m: continue
    try: w = float(r[h["WAGE_RATE_OF_PAY_FROM"]]) * m
    except (TypeError, ValueError): continue
    if not (20_000 <= w <= 2_000_000): continue
    recs.append({"w": w, "lvl": lvl(txt(r[h["JOB_TITLE"]])),
                 "emp": txt(r[h["EMPLOYER_NAME"]]).upper(),
                 "city": f'{txt(r[h["WORKSITE_CITY"]]).title()}, {txt(r[h["WORKSITE_STATE"]]).upper()}',
                 "title": " ".join(txt(r[h["JOB_TITLE"]]).lower().split())})

ec = collections.Counter(x["emp"] for x in recs)
cc = collections.Counter(x["city"] for x in recs)
sub = [x for x in recs if ec[x["emp"]] >= MIN_N and cc[x["city"]] >= MIN_N]

print(f"core software filings:        {len(recs):,}")
print(f"common subset (emp & city n>={MIN_N}): {len(sub):,}\n")

def g(key):
    d = collections.defaultdict(list)
    for x in sub: d[x[key]].append(x["w"])
    return d

print("SHARE OF WAGE VARIANCE EXPLAINED  (omega squared, identical rows)")
res = {}
for label, key in [("seniority in title", "lvl"), ("worksite city", "city"), ("employer", "emp")]:
    gg = g(key); res[label] = omega_sq(gg)
    print(f"  {label:<22} {res[label]:>7}   ({len(gg):,} groups)")

sse = [x for x in recs if "senior software engineer" in x["title"]]
w = sorted(x["w"] for x in sse)
print(f"\nTITLE HELD CONSTANT — title contains 'senior software engineer'   n={len(w):,}")
for p in (10, 25, 50, 75, 90):
    print(f"  p{p:<3} ${pctile(w, p):>10,.0f}")
print(f"  min  ${w[0]:>10,.0f}   max ${w[-1]:>10,.0f}   p90/p10 {pctile(w,90)/pctile(w,10):.2f}x")

byemp = collections.defaultdict(list)
for x in sse: byemp[x["emp"]].append(x["w"])
big = sorted(((k, v) for k, v in byemp.items() if len(v) >= 15),
             key=lambda kv: statistics.median(kv[1]))
print(f"\n  same title, employers with n>=15 ({len(big)} of them):")
for k, v in big:
    print(f"   {k[:44]:<44} n={len(v):<4} median ${statistics.median(v):>9,.0f}")

json.dump({"omega_squared": res, "subset_n": len(sub), "core_n": len(recs),
           "sse_percentiles": {f"p{p}": round(pctile(w, p)) for p in (10,25,50,75,90)},
           "sse_n": len(w), "sse_min": round(w[0]), "sse_max": round(w[-1])},
          open(sys.argv[2], "w"), indent=2)
