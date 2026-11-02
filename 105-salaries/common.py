"""Shared filters and statistics for the LCA salary analysis.

Both collect_salaries.py and variance.py import from here. They previously each
carried their own seniority classifier, which drifted: the same filing landed in
different bands depending on which script read it, so the two outputs disagreed.
One classifier, one set of numbers.
"""
import re, statistics

# Wage units as they appear in WAGE_UNIT_OF_PAY, converted to an annual figure.
PER_YEAR = {"Year": 1.0, "Hour": 2080.0, "Week": 52.0, "Bi-Weekly": 26.0, "Month": 12.0}

# Software engineering occupations (SOC 2018). CORE is the "software engineer"
# core used for seniority and variance work; SOC_KEEP is the wider computing set.
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
CORE_SOC = {"15-1252", "15-1251", "15-1253"}

# An annualised wage outside this range is treated as a mislabelled unit of pay,
# which does occur in these filings, rather than as a real salary.
PLAUSIBLE_USD = (20_000, 2_000_000)

# Seniority is inferred from the employer's own job title text. The first pattern
# that matches wins, so more senior and more specific labels come first:
# "Senior Staff Engineer" is staff, not senior.
#
# Bare \bi\b is deliberately NOT used for junior — a lone "i" appears in enough
# unrelated titles to misclassify. Roman-numeral I is matched only where it
# follows a role noun ("Software Engineer I").
_LEVELS = [
    ("principal", r"\bprincipal\b|\bdistinguished\b|\bfellow\b"),
    ("staff",     r"\bstaff\b"),
    ("manager",   r"\bmanager\b|\bdirector\b|\bhead of\b|\bvp\b|\bvice president\b"),
    ("architect", r"\barchitect\b"),
    ("lead",      r"\blead\b|\bleader\b"),
    ("senior",    r"\bsenior\b|\bsr\.?\b|\biii\b|\blevel\s*3\b|\bl3\b"),
    ("mid",       r"\bii\b|\bintermediate\b|\blevel\s*2\b|\bl2\b"),
    ("junior",    r"\bjunior\b|\bjr\.?\b|\bentry\b|\bassociate\b|\bgraduate\b"
                  r"|\bnew grad\b|\blevel\s*1\b|\bl1\b"
                  r"|\b(?:engineer|developer|programmer|analyst)\s+i\b"),
]
_LEVEL_RE = [(name, re.compile(pat, re.I)) for name, pat in _LEVELS]

# Manager and director titles are a separate track from the IC ladder. They are
# kept because they are real filings, but they are not a rung above "staff".
MANAGEMENT_BANDS = {"manager"}


def level_of(title):
    """Seniority band implied by an employer's job title text."""
    t = title or ""
    for name, rx in _LEVEL_RE:
        if rx.search(t):
            return name
    return "unlabelled"


def txt(v):
    """Coerce a cell to clean text. Some text columns arrive as ints."""
    return "" if v is None else str(v).strip()


def annual_wage(rate, unit):
    """Annualise a wage, or None if the unit is unknown or the result implausible."""
    mult = PER_YEAR.get(txt(unit))
    if not mult:
        return None
    try:
        w = float(rate) * mult
    except (TypeError, ValueError):
        return None
    lo, hi = PLAUSIBLE_USD
    return w if lo <= w <= hi else None


def pctile(vals, p):
    """Linear-interpolated percentile."""
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
    return {"n": len(vals),
            "p10": round(pctile(vals, 10)), "p25": round(pctile(vals, 25)),
            "median": round(pctile(vals, 50)),
            "p75": round(pctile(vals, 75)), "p90": round(pctile(vals, 90)),
            "mean": round(statistics.fmean(vals))}


def omega_sq(groups):
    """Share of variance attributable to a factor.

    omega-squared rather than eta-squared: these factors have very different
    numbers of levels (9 seniority bands against 119 employers) and eta-squared
    rises mechanically with level count. omega-squared penalises that.
    """
    vals = [v for g in groups.values() for v in g]
    N, k = len(vals), len(groups)
    if k < 2 or N - k < 1:
        return None
    gm = statistics.fmean(vals)
    ss_b = sum(len(g) * (statistics.fmean(g) - gm) ** 2 for g in groups.values())
    ss_t = sum((v - gm) ** 2 for v in vals)
    ms_w = (ss_t - ss_b) / (N - k)
    den = ss_t + ms_w
    return round(max(0.0, (ss_b - (k - 1) * ms_w) / den), 4) if den else None
