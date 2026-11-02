"""Aggregate employer-attested software wages from DOL LCA disclosure data.

Source: Department of Labor, Office of Foreign Labor Certification quarterly
LCA disclosure files. Every row is an employer's legal attestation of the wage
it will pay for a named role at a named worksite.

Emits aggregates only. All contact/attorney/personal columns are discarded on
read and never reach the output.
"""
import json, re, statistics, sys, collections
import openpyxl

# Software engineering occupations (SOC 2018)
SOC_KEEP = {
    "15-1252": "Software Developers",
    "15-1251": "Computer Programmers",
    "15-1253": "Software QA Analysts and Testers",
    "15-1211": "Computer Systems Analysts",
    "15-1221": "Computer and Information Research Scientists",
    "15-1299": "Computer Occupations, All Other",
    "15-1243": "Database Architects",
    "15-1242": "Database Administrators",
    "15-1244": "Network and Computer Systems Administrators",
    "15-1241": "Computer Network Architects",
    "15-1232": "Computer User Support Specialists",
    "15-1231": "Computer Network Support Specialists",
    "15-2051": "Data Scientists",
}
CORE_SOC = {"15-1252", "15-1251", "15-1253"}  # the "software engineer" core

PER_YEAR = {"Year": 1.0, "Hour": 2080.0, "Week": 52.0, "Bi-Weekly": 26.0, "Month": 12.0}

# Seniority is inferred from the employer's own job title text. Order matters:
# the first pattern that matches wins, so the most senior labels come first.
LEVELS = [
    ("principal",  r"\bprincipal\b|\bdistinguished\b|\bfellow\b"),
    ("staff",      r"\bstaff\b"),
    ("lead",       r"\blead\b|\bleader\b|\btech lead\b"),
    ("manager",    r"\bmanager\b|\bdirector\b|\bhead of\b|\bvp\b|\bvice president\b"),
    ("architect",  r"\barchitect\b"),
    ("senior",     r"\bsenior\b|\bsr\.?\b|\bsenior-level\b|\biii\b|\b3\b"),
    ("mid",        r"\bii\b|\bintermediate\b|\b2\b"),
    ("junior",     r"\bjunior\b|\bjr\.?\b|\bentry\b|\bassociate\b|\bi\b|\bgraduate\b|\bnew grad\b"),
]
LEVEL_RE = [(name, re.compile(pat, re.I)) for name, pat in LEVELS]


def level_of(title):
    t = title or ""
    for name, rx in LEVEL_RE:
        if rx.search(t):
            return name
    return "unlabelled"


def txt(v):
    """Coerce a cell to clean text. Some text columns arrive as ints."""
    return "" if v is None else str(v).strip()


def pct(vals, p):
    if not vals:
        return None
    s = sorted(vals)
    if len(s) == 1:
        return float(s[0])
    k = (len(s) - 1) * (p / 100.0)
    lo, hi = int(k), min(int(k) + 1, len(s) - 1)
    return float(s[lo] + (s[hi] - s[lo]) * (k - lo))


def summarise(vals, min_n=30):
    if len(vals) < min_n:
        return None
    return {
        "n": len(vals),
        "p10": round(pct(vals, 10)), "p25": round(pct(vals, 25)),
        "median": round(pct(vals, 50)),
        "p75": round(pct(vals, 75)), "p90": round(pct(vals, 90)),
        "mean": round(statistics.fmean(vals)),
    }


def main(path, out):
    wb = openpyxl.load_workbook(path, read_only=True, data_only=True)
    ws = wb[wb.sheetnames[0]]
    rows = ws.iter_rows(values_only=True)
    hdr = {h: i for i, h in enumerate(next(rows))}

    need = ["CASE_STATUS", "VISA_CLASS", "SOC_CODE", "SOC_TITLE", "JOB_TITLE",
            "FULL_TIME_POSITION", "EMPLOYER_NAME", "WORKSITE_CITY", "WORKSITE_STATE",
            "WAGE_RATE_OF_PAY_FROM", "WAGE_UNIT_OF_PAY", "PREVAILING_WAGE",
            "PW_UNIT_OF_PAY", "BEGIN_DATE"]
    missing = [c for c in need if c not in hdr]
    if missing:
        sys.exit(f"missing columns: {missing}")
    ix = {c: hdr[c] for c in need}

    by_level = collections.defaultdict(list)
    by_level_core = collections.defaultdict(list)
    by_metro = collections.defaultdict(list)
    by_employer = collections.defaultdict(list)
    by_soc = collections.defaultdict(list)
    prevailing_gap = []
    unit_counts = collections.Counter()
    total = kept = blank = 0
    dropped = collections.Counter()

    for r in rows:
        # The sheet is padded with ~960k entirely empty rows after the real data.
        if r[ix["CASE_STATUS"]] is None and r[ix["VISA_CLASS"]] is None:
            blank += 1
            continue
        total += 1
        if txt(r[ix["CASE_STATUS"]]) != "Certified":
            dropped["not certified"] += 1; continue
        if txt(r[ix["VISA_CLASS"]]) != "H-1B":
            dropped["not H-1B"] += 1; continue
        soc = txt(r[ix["SOC_CODE"]]).split(".")[0]
        if soc not in SOC_KEEP:
            dropped["non-software SOC"] += 1; continue
        if txt(r[ix["FULL_TIME_POSITION"]]).upper() != "Y":
            dropped["not full time"] += 1; continue

        unit = txt(r[ix["WAGE_UNIT_OF_PAY"]])
        mult = PER_YEAR.get(unit)
        if not mult:
            dropped[f"unknown wage unit: {unit!r}"] += 1; continue
        try:
            wage = float(r[ix["WAGE_RATE_OF_PAY_FROM"]])
        except (TypeError, ValueError):
            dropped["unparseable wage"] += 1; continue
        annual = wage * mult
        # Guard against unit-of-pay mislabelling, which does occur in these filings.
        if not (20_000 <= annual <= 2_000_000):
            dropped["annualised wage out of plausible range"] += 1; continue

        unit_counts[unit] += 1
        kept += 1
        title = txt(r[ix["JOB_TITLE"]])
        lvl = level_of(title)
        by_level[lvl].append(annual)
        if soc in CORE_SOC:
            by_level_core[lvl].append(annual)
        by_soc[SOC_KEEP[soc]].append(annual)

        city = txt(r[ix["WORKSITE_CITY"]]).title()
        st = txt(r[ix["WORKSITE_STATE"]]).upper()
        if city and st:
            by_metro[f"{city}, {st}"].append(annual)

        emp = txt(r[ix["EMPLOYER_NAME"]]).upper()
        if emp:
            by_employer[emp].append(annual)

        try:
            pw = float(r[ix["PREVAILING_WAGE"]])
            pwm = PER_YEAR.get(txt(r[ix["PW_UNIT_OF_PAY"]]))
            if pwm:
                pwa = pw * pwm
                if 20_000 <= pwa <= 2_000_000:
                    prevailing_gap.append(annual - pwa)
        except (TypeError, ValueError):
            pass

    def top(d, n, min_n):
        out = []
        for k, v in sorted(d.items(), key=lambda kv: -len(kv[1])):
            s = summarise(v, min_n)
            if s:
                out.append({"key": k, **s})
            if len(out) >= n:
                break
        return out

    allw = [w for v in by_level.values() for w in v]
    result = {
        "source": {
            "name": "US Department of Labor, Office of Foreign Labor Certification — "
                    "LCA Disclosure Data FY2026 Q1",
            "url": "https://www.dol.gov/agencies/eta/foreign-labor/performance",
            "file": "LCA_Disclosure_Data_FY2026_Q1.xlsx",
            "published": "2025-12-18",
            "what_each_row_is": "An employer's legal attestation of the wage it will pay "
                                "for one named role at one named worksite.",
        },
        "filters": {
            "case_status": "Certified", "visa_class": "H-1B",
            "full_time_only": True, "soc_codes": sorted(SOC_KEEP),
            "annualised_range_usd": [20000, 2000000],
        },
        "counts": {"data_rows": total, "blank_padding_rows": blank, "rows_kept": kept,
                   "dropped": dict(dropped.most_common()),
                   "wage_units_seen": dict(unit_counts)},
        "overall": summarise(allw, 1),
        "by_seniority_all_software_soc": {k: summarise(v) for k, v in sorted(by_level.items())
                                          if summarise(v)},
        "by_seniority_core_soc": {k: summarise(v) for k, v in sorted(by_level_core.items())
                                  if summarise(v)},
        "by_soc_title": {k: summarise(v) for k, v in sorted(by_soc.items()) if summarise(v)},
        "top_metros": top(by_metro, 25, 100),
        "top_employers": top(by_employer, 30, 100),
        "attested_minus_prevailing": (
            {"n": len(prevailing_gap), "median": round(pct(prevailing_gap, 50)),
             "p25": round(pct(prevailing_gap, 25)), "p75": round(pct(prevailing_gap, 75)),
             "share_at_or_below_prevailing": round(
                 sum(1 for g in prevailing_gap if g <= 0) / len(prevailing_gap), 4)}
            if prevailing_gap else None),
        "methodology_notes": [
            "Wages are annualised with 2080 hours per year for hourly filings.",
            "WAGE_RATE_OF_PAY_FROM is the bottom of the attested range; it is the "
            "figure the employer is legally bound to meet, so it is a floor, not a midpoint.",
            "Seniority is inferred from the employer's own JOB_TITLE text, not from any "
            "standardised level. 'unlabelled' means the title carried no seniority word.",
            "These are base wages. Equity and bonus are not part of an LCA attestation, "
            "so totals here are not comparable to survey figures that include them.",
            "H-1B filings skew toward larger employers and tech-dense metros, and toward "
            "roles companies choose to sponsor. This is not a sample of all US software jobs.",
            "All personal columns in the source file (employer and attorney contacts) are "
            "discarded on read and appear nowhere in this output.",
        ],
    }
    with open(out, "w") as f:
        json.dump(result, f, indent=2)
    print(f"read {total:,} data rows ({blank:,} blank padding), kept {kept:,}")
    print(f"wrote {out}")


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
