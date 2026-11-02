"""Aggregate employer-attested software wages from DOL LCA disclosure data.

Source: Department of Labor, Office of Foreign Labor Certification quarterly LCA
disclosure files. Every row is an employer's legal attestation of the wage it
will pay for a named role at a named worksite.

Reads the workbook once and writes two files:
  salaries.json  — wage aggregates by seniority, occupation, metro and employer
  variance.json  — how much of the wage spread each factor explains

Emits aggregates only. Every personal column in the source (employer and
attorney contact details) is discarded on read and reaches no output.

  python3 analyse.py LCA_Disclosure_Data_FY2026_Q1.xlsx salaries.json variance.json
"""
import sys, json, collections, statistics
import openpyxl
from common import (SOC_KEEP, CORE_SOC, PLAUSIBLE_USD, level_of, txt, annual_wage,
                    pctile, summarise, omega_sq)

# A factor's categories must each clear this to enter the variance comparison,
# so that one-off employers and tiny towns don't dominate.
MIN_GROUP_N = 30

SOURCE = {
    "name": "US Department of Labor, Office of Foreign Labor Certification — "
            "LCA Disclosure Data FY2026 Q1",
    "url": "https://www.dol.gov/agencies/eta/foreign-labor/performance",
    "file": "LCA_Disclosure_Data_FY2026_Q1.xlsx",
    "published": "2025-12-18",
    "what_each_row_is": "An employer's legal attestation of the wage it will pay for "
                        "one named role at one named worksite.",
}

NOTES = [
    "Hourly filings are annualised at 2080 hours per year.",
    "WAGE_RATE_OF_PAY_FROM is the bottom of the attested range — the figure the "
    "employer is legally bound to meet. It is a floor, not a midpoint.",
    "Seniority is inferred from the employer's own job title text, not from any "
    "standardised level. 'unlabelled' means the title carried no seniority word.",
    "Manager and director titles are a separate track from the individual "
    "contributor ladder; they are reported but are not a rung above 'staff'.",
    "These are base wages. Equity and bonus are not part of an LCA attestation, so "
    "these figures are not comparable to survey numbers that include them.",
    "H-1B filings skew toward larger employers, tech-dense metros, and roles "
    "companies choose to sponsor. This is not a sample of all US software jobs.",
    "All personal columns in the source file are discarded on read.",
]

NEED = ["CASE_STATUS", "VISA_CLASS", "SOC_CODE", "JOB_TITLE", "FULL_TIME_POSITION",
        "EMPLOYER_NAME", "WORKSITE_CITY", "WORKSITE_STATE", "WAGE_RATE_OF_PAY_FROM",
        "WAGE_UNIT_OF_PAY", "PREVAILING_WAGE", "PW_UNIT_OF_PAY"]


def read(path):
    wb = openpyxl.load_workbook(path, read_only=True, data_only=True)
    ws = wb[wb.sheetnames[0]]
    rows = ws.iter_rows(values_only=True)
    hdr = {h: i for i, h in enumerate(next(rows))}
    missing = [c for c in NEED if c not in hdr]
    if missing:
        sys.exit(f"missing columns: {missing}")
    ix = {c: hdr[c] for c in NEED}

    recs, dropped, units = [], collections.Counter(), collections.Counter()
    data_rows = blank = 0
    for r in rows:
        # The sheet is padded with ~960k entirely empty rows after the real data.
        if r[ix["CASE_STATUS"]] is None and r[ix["VISA_CLASS"]] is None:
            blank += 1
            continue
        data_rows += 1
        if txt(r[ix["CASE_STATUS"]]) != "Certified":
            dropped["not certified"] += 1; continue
        if txt(r[ix["VISA_CLASS"]]) != "H-1B":
            dropped["not H-1B"] += 1; continue
        # SOC_CODE carries an O*NET detail suffix (15-1252.00); match the base code.
        soc = txt(r[ix["SOC_CODE"]]).split(".")[0]
        if soc not in SOC_KEEP:
            dropped["non-software SOC"] += 1; continue
        if txt(r[ix["FULL_TIME_POSITION"]]).upper() != "Y":
            dropped["not full time"] += 1; continue
        wage = annual_wage(r[ix["WAGE_RATE_OF_PAY_FROM"]], r[ix["WAGE_UNIT_OF_PAY"]])
        if wage is None:
            dropped["unknown unit or implausible annualised wage"] += 1; continue

        units[txt(r[ix["WAGE_UNIT_OF_PAY"]])] += 1
        title = txt(r[ix["JOB_TITLE"]])
        city, st = txt(r[ix["WORKSITE_CITY"]]).title(), txt(r[ix["WORKSITE_STATE"]]).upper()
        recs.append({
            "w": wage, "soc": soc, "lvl": level_of(title),
            "title": " ".join(title.lower().split()),
            "emp": txt(r[ix["EMPLOYER_NAME"]]).upper(),
            "city": f"{city}, {st}" if city and st else "",
            "pw": annual_wage(r[ix["PREVAILING_WAGE"]], r[ix["PW_UNIT_OF_PAY"]]),
        })
    return recs, {"data_rows": data_rows, "blank_padding_rows": blank,
                  "rows_kept": len(recs), "dropped": dict(dropped.most_common()),
                  "wage_units_seen": dict(units)}


def group(recs, key, min_n=1):
    d = collections.defaultdict(list)
    for x in recs:
        if x[key]:
            d[x[key]].append(x["w"])
    return {k: v for k, v in d.items() if len(v) >= min_n}


def top(d, n, min_n):
    out = []
    for k, v in sorted(d.items(), key=lambda kv: -len(kv[1])):
        s = summarise(v, min_n)
        if s:
            out.append({"key": k, **s})
        if len(out) >= n:
            break
    return out


def main(path, out_sal, out_var):
    recs, counts = read(path)
    core = [x for x in recs if x["soc"] in CORE_SOC]
    allw = [x["w"] for x in recs]
    print(f"read {counts['data_rows']:,} data rows "
          f"({counts['blank_padding_rows']:,} blank padding), kept {len(recs):,}")
    print(f"core software (SOC {'/'.join(sorted(CORE_SOC))}): {len(core):,}")

    gaps = [x["w"] - x["pw"] for x in recs if x["pw"] is not None]
    json.dump({
        "source": SOURCE,
        "filters": {"case_status": "Certified", "visa_class": "H-1B",
                    "full_time_only": True, "soc_codes": sorted(SOC_KEEP),
                    "annualised_range_usd": list(PLAUSIBLE_USD)},
        "counts": counts,
        "overall_all_software_soc": summarise(allw, 1),
        "overall_core_soc": summarise([x["w"] for x in core], 1),
        "by_seniority_all_software_soc": {
            k: summarise(v) for k, v in group(recs, "lvl").items() if summarise(v)},
        "by_seniority_core_soc": {
            k: summarise(v) for k, v in group(core, "lvl").items() if summarise(v)},
        "by_soc_title": {
            SOC_KEEP[k]: summarise(v) for k, v in group(recs, "soc").items()
            if summarise(v)},
        "top_metros": top(group(recs, "city"), 25, 100),
        "top_employers": top(group(recs, "emp"), 30, 100),
        "attested_minus_prevailing": (
            {"n": len(gaps), "median": round(pctile(gaps, 50)),
             "p25": round(pctile(gaps, 25)), "p75": round(pctile(gaps, 75)),
             "share_at_or_below_prevailing": round(
                 sum(1 for g in gaps if g <= 0) / len(gaps), 4)} if gaps else None),
        "methodology_notes": NOTES,
    }, open(out_sal, "w"), indent=2)

    # Variance: every factor scored on one identical set of rows, so that the
    # comparison is a comparison. A row survives only if its employer AND its
    # city each clear MIN_GROUP_N.
    ec = collections.Counter(x["emp"] for x in core)
    cc = collections.Counter(x["city"] for x in core)
    sub = [x for x in core
           if ec[x["emp"]] >= MIN_GROUP_N and cc[x["city"]] >= MIN_GROUP_N]
    omega, ngroups = {}, {}
    for label, key in [("seniority_in_title", "lvl"), ("worksite_city", "city"),
                       ("employer", "emp")]:
        g = group(sub, key)
        omega[label], ngroups[label] = omega_sq(g), len(g)
        print(f"  omega2 {label:<20} {omega[label]:>7}  ({len(g):,} groups)")

    sse = [x for x in core if "senior software engineer" in x["title"]]
    w = sorted(x["w"] for x in sse)
    byemp = collections.defaultdict(list)
    for x in sse:
        byemp[x["emp"]].append(x["w"])
    big = sorted(((k, v) for k, v in byemp.items() if len(v) >= 15),
                 key=lambda kv: statistics.median(kv[1]))
    bylvl = group(core, "lvl")

    json.dump({
        "source": SOURCE,
        "method": "omega-squared, all factors scored on one identical set of rows",
        "core_n": len(core), "subset_n": len(sub),
        "min_group_n": MIN_GROUP_N,
        "omega_squared": omega, "group_counts": ngroups,
        "seniority_medians": {
            k: {"n": len(v), "median": round(pctile(v, 50))}
            for k, v in sorted(bylvl.items(), key=lambda kv: -pctile(kv[1], 50))},
        "title_held_constant": {
            "match": "job title contains 'senior software engineer'",
            "n": len(w), "min": round(w[0]), "max": round(w[-1]),
            "percentiles": {f"p{p}": round(pctile(w, p)) for p in (10, 25, 50, 75, 90)},
            "p90_over_p10": round(pctile(w, 90) / pctile(w, 10), 3),
            "by_employer_min_15": [
                {"employer": k, "n": len(v), "median": round(statistics.median(v))}
                for k, v in big],
        },
        "methodology_notes": NOTES,
    }, open(out_var, "w"), indent=2)
    print(f"wrote {out_sal} and {out_var}")


if __name__ == "__main__":
    main(*sys.argv[1:4])
